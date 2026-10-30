import json
from pathlib import Path

import env_status
import feature
import pytest


def test_detect_python_uv_project(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.ruff]\nline-length = 100\n[dependency-groups]\ndev = ["pytest"]\n'
    )
    (tmp_path / "uv.lock").write_text("name = 'pytest'\n")
    found = feature.detect(tmp_path)
    assert found["test"] == ["uv", "run", "pytest", "-q"]
    assert found["lint"] == ["uvx", "ruff", "check", "."]  # ruff configured, not installed


def test_detect_python_uses_project_ruff_when_locked(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
    (tmp_path / "uv.lock").write_text("name = 'ruff'\n")
    assert feature.detect(tmp_path)["lint"] == ["uv", "run", "ruff", "check", "."]


def test_detect_node_ignores_placeholder_test_script(tmp_path: Path) -> None:
    scripts = {"test": 'echo "Error: no test specified" && exit 1', "lint": "eslint ."}
    (tmp_path / "package.json").write_text(json.dumps({"scripts": scripts}))
    (tmp_path / "pnpm-lock.yaml").write_text("")
    found = feature.detect(tmp_path)
    assert found["test"] is None and found["lint"] == ["pnpm", "run", "lint"]


@pytest.mark.parametrize(
    ("marker", "language"), [("go.mod", "go"), ("Cargo.toml", "rust"), ("nothing", "unknown")]
)
def test_detect_other_languages(tmp_path: Path, marker: str, language: str) -> None:
    (tmp_path / marker).write_text("")
    assert feature.detect(tmp_path)["language"] == language


def test_detect_makefile_targets(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("test:\n\techo hi\n")
    found = feature.detect(tmp_path)
    assert found["test"] == ["make", "test"] and found["lint"] is None


def test_check_reports_pass_fail_and_not_run(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("test:\n\t@echo ok\n")
    report, code = feature.run_checks(tmp_path)
    assert code == 0
    assert [r["status"] for r in report["results"]] == ["passed", "not-run"]

    (tmp_path / "Makefile").write_text("test:\n\t@echo broken; exit 3\n")
    report, code = feature.run_checks(tmp_path)
    assert code == 1 and report["results"][0]["status"] == "failed"
    assert report["results"][0]["exit_code"] != 0  # make reports its own code, not the recipe's
    assert "broken" in report["results"][0]["output_tail"]


def test_check_never_claims_success_when_tests_cannot_run(tmp_path: Path) -> None:
    report, code = feature.run_checks(tmp_path)  # empty project
    assert code == 4
    assert all(r["status"] == "not-run" for r in report["results"])


def test_env_status_reports_names_never_secrets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# comment\nGH_TOKEN=ghp_SECRETVALUE123\nGITLAB_TOKEN=\nJIRA_SITE='acme.atlassian.net'\n"
        "JIRA_EMAIL=me@acme.com\nJIRA_API_TOKEN=\nJIRA_PROJECT_KEY=PAY\n"
    )
    assert env_status.main(["--env", str(env)]) == 0
    out = capsys.readouterr().out
    assert "SECRETVALUE" not in out and "me@acme.com" not in out
    report = json.loads(out)
    assert report["tools"]["github"]["ready"] is True
    assert report["tools"]["gitlab"] == {
        "ready": False,
        "missing": ["GITLAB_TOKEN"],
        "invalid": [],
    }
    assert report["tools"]["jira"]["missing"] == ["JIRA_API_TOKEN"]
    assert report["values"] == {"JIRA_PROJECT_KEY": "PAY"}


def test_env_status_require_and_missing_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("GH_TOKEN=x\n")
    assert env_status.main(["--env", str(env), "--require", "github"]) == 0
    assert env_status.main(["--env", str(env), "--require", "github,jira"]) == 1
    assert env_status.main(["--env", str(env), "--require", "bitbucket"]) == 2
    assert env_status.main(["--env", str(tmp_path / "missing")]) == 2


def test_check_output_tail_has_no_ansi_colours(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("test:\n\t@printf '\\033[31mred\\033[0m\\n'; exit 1\n")
    report, _ = feature.run_checks(tmp_path)
    tail = report["results"][0]["output_tail"]
    assert "red" in tail and not any("\x1b" in line for line in tail)


def _jira_report(
    tmp_path: Path, site: str, email: str = "me@acme.com", token: str = "t0k3n"
) -> dict:
    env = tmp_path / ".env"
    env.write_text(f"JIRA_SITE={site}\nJIRA_EMAIL={email}\nJIRA_API_TOKEN={token}\n")
    return env_status.build_report(env)["tools"]["jira"]


def test_template_placeholder_site_is_not_ready(tmp_path: Path) -> None:
    jira = _jira_report(tmp_path, "yourcompany.atlassian.net")
    assert jira["ready"] is False and jira["missing"] == []
    assert jira["invalid"] == [{"name": "JIRA_SITE", "reason": "still the template placeholder"}]


def test_real_site_is_ready_with_or_without_scheme(tmp_path: Path) -> None:
    for site in ("acme.atlassian.net", "https://acme.atlassian.net/"):
        assert _jira_report(tmp_path, site)["ready"] is True


def test_malformed_site_and_email_are_flagged_by_name(tmp_path: Path) -> None:
    jira = _jira_report(tmp_path, "not a site", email="no-at-sign")
    assert jira["ready"] is False
    assert {(i["name"], i["reason"]) for i in jira["invalid"]} == {
        ("JIRA_SITE", "not a hostname"),
        ("JIRA_EMAIL", "not an email address"),
    }


def test_placeholder_tokens_are_not_ready_and_never_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = tmp_path / ".env"
    env.write_text("GH_TOKEN=your-token-here\nJIRA_API_TOKEN=<paste token>\n")
    assert env_status.main(["--env", str(env), "--require", "github"]) == 1
    out = capsys.readouterr().out
    assert "your-token-here" not in out and "paste token" not in out
    report = json.loads(out)
    assert report["tools"]["github"]["invalid"][0]["name"] == "GH_TOKEN"


def test_require_fails_on_placeholder_site(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("JIRA_SITE=yourcompany.atlassian.net\nJIRA_EMAIL=a@b.co\nJIRA_API_TOKEN=x\n")
    assert env_status.main(["--env", str(env), "--require", "jira"]) == 1


def test_untouched_template_reports_nothing_ready(tmp_path: Path) -> None:
    template = Path(__file__).parent.parent / ".env.example"
    report = env_status.build_report(template)
    assert not any(tool["ready"] for tool in report["tools"].values())
