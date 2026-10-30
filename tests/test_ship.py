import json
from pathlib import Path

import feature
import pytest
import ship
from conftest import git, write_fake_tool

FAKE_GH = """
echo "$@" >> "$GH_LOG"
if [ "$1 $2" = "pr view" ]; then
  grep -qx "$3" "$GH_PRS" 2>/dev/null && echo "https://example.test/pr/$3" && exit 0
  exit 1
fi
if [ "$1 $2" = "pr create" ]; then
  head=""; while [ $# -gt 0 ]; do [ "$1" = "--head" ] && head="$2"; shift; done
  echo "$head" >> "$GH_PRS"; echo "https://example.test/pr/$head"
fi
"""

FAKE_GLAB = """
echo "$@" >> "$GLAB_LOG"
echo "https://gitlab.test/mr/1"
"""

BRANCH = "feature/PAY-7-delete-a-task"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo on `main` with a passing `make test` and a local bare `origin`."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "Makefile").write_text("test:\n\t@echo ok\n")
    (root / "app.py").write_text("print('hi')\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    git(root, "remote", "add", "origin", str(origin))
    git(root, "push", "-q", "origin", "main")
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def gh(fake_bin: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GH_LOG", str(tmp_path / "gh.log"))
    monkeypatch.setenv("GH_PRS", str(tmp_path / "gh.prs"))
    write_fake_tool(fake_bin, "gh", FAKE_GH)
    return tmp_path / "gh.log"


def run_check(root: Path) -> None:
    assert feature.main(["--root", str(root), "check"]) == 0


def on_branch(repo: Path) -> Path:
    assert ship.main(["branch", "--ticket", "PAY-7", "--name", "Delete a task"]) == 0
    return repo


def edited(repo: Path) -> Path:
    """On the ticket branch with a passing check over an uncommitted change."""
    on_branch(repo)
    (repo / "delete.py").write_text("def delete(): ...\n")
    run_check(repo)
    return repo


def committed(repo: Path) -> Path:
    assert ship.main(["commit", "--summary", "Delete a task"]) == 0
    return repo


# --- branch ------------------------------------------------------------------------------------


def test_branch_is_named_after_the_ticket(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert ship.main(["branch", "--ticket", "PAY-7", "--name", "Delete a task!"]) == 0
    assert json.loads(capsys.readouterr().out) == {"branch": BRANCH, "base": "main"}
    assert git(repo, "branch", "--show-current") == BRANCH


def test_branch_refuses_a_missing_or_malformed_ticket(repo: Path) -> None:
    assert ship.main(["branch", "--ticket", "pay7", "--name", "x"]) == 2
    assert git(repo, "branch", "--show-current") == "main"


def test_branch_refuses_to_start_from_another_feature_branch(repo: Path) -> None:
    git(repo, "checkout", "-q", "-b", "feature/PAY-1-other")
    assert ship.main(["branch", "--ticket", "PAY-7", "--name", "Delete a task"]) == 2


def test_branch_is_idempotent_on_its_own_branch(repo: Path) -> None:
    on_branch(repo)
    assert ship.main(["branch", "--ticket", "PAY-7", "--name", "Delete a task"]) == 0
    assert git(repo, "branch", "--show-current") == BRANCH


# --- commit ------------------------------------------------------------------------------------


def test_commit_refuses_on_the_base_branch(repo: Path) -> None:
    (repo / "x.py").write_text("x")
    run_check(repo)
    assert ship.main(["commit", "--summary", "Whatever"]) == 2


def test_commit_refuses_without_a_check_receipt(repo: Path) -> None:
    on_branch(repo)
    (repo / "delete.py").write_text("x")
    assert ship.main(["commit", "--summary", "Delete a task"]) == 2
    assert git(repo, "rev-list", "--count", "main..HEAD") == "0"


def test_commit_refuses_when_code_changed_after_the_check(repo: Path) -> None:
    edited(repo)
    (repo / "delete.py").write_text("changed after the check\n")
    assert ship.main(["commit", "--summary", "Delete a task"]) == 2
    assert git(repo, "rev-list", "--count", "main..HEAD") == "0"


def test_commit_refuses_when_the_check_failed(repo: Path) -> None:
    on_branch(repo)
    (repo / "Makefile").write_text("test:\n\t@exit 1\n")
    assert feature.main(["--root", str(repo), "check"]) == 1
    assert ship.main(["commit", "--summary", "Delete a task"]) == 2


def test_commit_message_starts_with_the_ticket_key(repo: Path) -> None:
    committed(edited(repo))
    assert git(repo, "log", "-1", "--format=%s") == "PAY-7: delete a task"
    assert "delete.py" in git(repo, "show", "--name-only", "--format=")


def test_commit_refuses_to_include_an_env_file(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    on_branch(repo)
    (repo / ".env").write_text("TOKEN=secret\n")
    (repo / ".env.example").write_text("TOKEN=\n")  # templates are fine
    run_check(repo)
    assert ship.main(["commit", "--summary", "Delete a task"]) == 2
    assert ".env" in capsys.readouterr().err
    assert git(repo, "rev-list", "--count", "main..HEAD") == "0"
    assert git(repo, "diff", "--cached", "--name-only") == ""  # unstaged again


def test_commit_refuses_when_there_is_nothing_to_commit(repo: Path) -> None:
    on_branch(repo)
    run_check(repo)
    assert ship.main(["commit", "--summary", "Delete a task"]) == 2


# --- merge request -----------------------------------------------------------------------------


def test_mr_refuses_on_the_base_branch(repo: Path, gh: Path) -> None:
    assert ship.main(["mr", "--host", "github", "--confirm"]) == 2


def test_mr_refuses_with_uncommitted_changes(repo: Path, gh: Path) -> None:
    edited(repo)
    assert ship.main(["mr", "--host", "github", "--confirm"]) == 2
    assert not gh.exists()


def test_mr_refuses_when_the_committed_code_was_never_checked(repo: Path, gh: Path) -> None:
    on_branch(repo)
    (repo / "delete.py").write_text("x")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "PAY-7: sneaky")  # bypassed `ship.py commit`
    assert ship.main(["mr", "--host", "github", "--confirm"]) == 2
    assert not gh.exists()


def test_mr_refuses_with_no_commits(repo: Path, gh: Path) -> None:
    on_branch(repo)
    run_check(repo)
    assert ship.main(["mr", "--host", "github", "--confirm"]) == 2


def test_mr_without_confirm_previews_and_pushes_nothing(
    repo: Path, gh: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    committed(edited(repo))
    capsys.readouterr()  # drop output of the setup steps
    assert ship.main(["mr", "--host", "github"]) == 2
    preview = json.loads(capsys.readouterr().out)
    assert preview["created"] is False
    assert (preview["title"], preview["base"], preview["head"]) == (
        "PAY-7: delete a task",
        "main",
        BRANCH,
    )
    assert "PAY-7" in preview["body"] and "tests passed" in preview["body"].lower()
    assert not gh.exists()
    assert git(repo, "ls-remote", "origin", BRANCH) == ""


def test_mr_with_confirm_pushes_and_opens_a_pull_request(
    repo: Path, gh: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    committed(edited(repo))
    capsys.readouterr()  # drop output of the setup steps
    assert ship.main(["mr", "--host", "github", "--confirm"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"created": True, "url": f"https://example.test/pr/{BRANCH}"}
    assert BRANCH in git(repo, "ls-remote", "origin", BRANCH)
    call = gh.read_text()
    assert f"--base main --head {BRANCH} --title PAY-7: delete a task" in call


def test_mr_is_not_opened_twice(repo: Path, gh: Path) -> None:
    committed(edited(repo))
    assert ship.main(["mr", "--host", "github", "--confirm"]) == 0
    assert ship.main(["mr", "--host", "github", "--confirm"]) == 0
    assert gh.read_text().count("pr create") == 1


def test_mr_on_gitlab_uses_glab(repo: Path, fake_bin: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GLAB_LOG", str(tmp_path / "glab.log"))
    write_fake_tool(fake_bin, "glab", FAKE_GLAB)
    committed(edited(repo))
    assert ship.main(["mr", "--host", "gitlab", "--confirm"]) == 0
    call = (tmp_path / "glab.log").read_text()
    assert f"mr create --source-branch {BRANCH} --target-branch main" in call


def test_mr_refuses_when_the_host_is_unknown(repo: Path) -> None:
    committed(edited(repo))
    assert ship.main(["mr", "--confirm"]) == 2  # origin is a local path


# --- status ------------------------------------------------------------------------------------


def test_status_reports_where_the_flow_stands(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert ship.main(["status"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["ticket"] is None and first["on_base"] is True

    edited(repo)
    capsys.readouterr()
    assert ship.main(["status"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["ticket"] == "PAY-7" and second["branch"] == BRANCH
    assert second["dirty"] is True and second["checks"] == "passed"
    assert second["commits_ahead"] == 0

    (repo / "later.py").write_text("edited after the check")
    capsys.readouterr()
    ship.main(["status"])
    assert json.loads(capsys.readouterr().out)["checks"] == "stale"
