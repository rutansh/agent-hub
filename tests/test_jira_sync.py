from pathlib import Path

import jira_sync
import pytest
from conftest import write_fake_tool
from planlib import parse_plan

FAKE_ACLI = """
echo "$@" >> "$ACLI_LOG"
n=$(( $(cat "$ACLI_COUNT" 2>/dev/null || echo 100) + 1 ))
echo $n > "$ACLI_COUNT"
if [ -n "$ACLI_FAIL_AT" ] && [ "$n" = "$ACLI_FAIL_AT" ]; then echo "boom" >&2; exit 3; fi
echo "{\\"key\\": \\"PAY-$n\\", \\"parent\\": \\"PAY-1\\"}"
"""


@pytest.fixture
def acli(fake_bin: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    log = tmp_path / "acli.log"
    monkeypatch.setenv("ACLI_LOG", str(log))
    monkeypatch.setenv("ACLI_COUNT", str(tmp_path / "count"))
    write_fake_tool(fake_bin, "acli", FAKE_ACLI)
    return log


def test_description_has_fixed_layout(plan_text: str) -> None:
    plan = parse_plan(plan_text)
    text = jira_sync.ticket_description(plan.tasks[1], plan)
    assert text.startswith("Let users manage workspaces from the CLI.\n\nAcceptance criteria:")
    assert "- [ ] `workspace create` works" in text
    assert "Depends on: T1\n" in text and "Likely files: cli.py" in text


def test_preview_lists_epic_then_tasks_without_side_effects(plan_text: str) -> None:
    items = jira_sync.preview(parse_plan(plan_text))
    assert [i["type"] for i in items] == ["Epic", "Task", "Task"]
    assert items[0]["summary"] == "Team workspaces"


@pytest.mark.parametrize(
    ("output", "exclude", "expected"),
    [
        ('{"key": "PAY-9"}', "", "PAY-9"),
        ('{"key": "PAY-9", "parent": "PAY-1"}', "PAY-1", "PAY-9"),
        ("Parent PAY-1 -> created PAY-12", "PAY-1", "PAY-12"),
        ("Created work item PAY-7", "", "PAY-7"),
    ],
)
def test_extract_key(output: str, exclude: str, expected: str) -> None:
    assert jira_sync.extract_key(output, "PAY", exclude) == expected


def test_extract_key_fails_loudly_when_no_key() -> None:
    with pytest.raises(jira_sync.JiraError):
        jira_sync.extract_key("ok", "PAY")


def test_create_refuses_without_confirm(epic_dir: Path, acli: Path) -> None:
    code = jira_sync.main(["create", str(epic_dir / "plan.md"), "--project", "PAY"])
    assert code == 2
    assert not acli.exists()


def test_create_makes_epic_then_children_and_records_keys(epic_dir: Path, acli: Path) -> None:
    plan_path = epic_dir / "plan.md"
    args = ["create", str(plan_path), "--project", "PAY", "--confirm"]
    assert jira_sync.main(args) == 0

    plan = parse_plan(plan_path.read_text())
    assert plan.epic_jira == "PAY-101"
    assert [t.jira for t in plan.tasks] == ["PAY-102", "PAY-103"]

    calls = acli.read_text().splitlines()
    assert "--type Epic" in calls[0] and "--parent" not in calls[0]
    assert "--type Task" in calls[1] and "--parent PAY-101" in calls[1]
    assert (epic_dir / "tickets" / "T1.md").read_text().startswith("Store workspaces")


def test_rerun_after_failure_resumes_without_duplicates(
    epic_dir: Path, acli: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = epic_dir / "plan.md"
    args = ["create", str(plan_path), "--project", "PAY", "--confirm"]

    monkeypatch.setenv("ACLI_FAIL_AT", "103")  # epic=101, T1=102, T2 fails
    assert jira_sync.main(args) == 1
    plan = parse_plan(plan_path.read_text())
    assert (plan.epic_jira, plan.tasks[0].jira, plan.tasks[1].jira) == ("PAY-101", "PAY-102", "")

    monkeypatch.delenv("ACLI_FAIL_AT")
    assert jira_sync.main(args) == 0
    assert parse_plan(plan_path.read_text()).tasks[1].jira == "PAY-104"
    assert len(acli.read_text().splitlines()) == 4  # 3 + 1 retry, nothing re-created


def test_missing_acli_is_a_clear_error(
    epic_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(jira_sync, "ACLI", "acli-does-not-exist")
    args = ["create", str(epic_dir / "plan.md"), "--project", "PAY", "--confirm"]
    assert jira_sync.main(args) == 1
    assert "not installed" in capsys.readouterr().err


def test_invalid_plan_blocks_creation(epic_dir: Path, acli: Path) -> None:
    (epic_dir / "plan.md").write_text("# Plan: X\n")
    args = ["create", str(epic_dir / "plan.md"), "--project", "PAY", "--confirm"]
    assert jira_sync.main(args) == 1
    assert not acli.exists()


def test_export_markdown_fallback_marks_tasks_none(epic_dir: Path) -> None:
    assert jira_sync.main(["export-markdown", str(epic_dir / "plan.md")]) == 0
    assert "## T1: Add workspace data model" in (epic_dir / "tickets.md").read_text()
    plan = parse_plan((epic_dir / "plan.md").read_text())
    assert [t.jira for t in plan.tasks] == ["none", "none"]
    assert [t.commit_prefix for t in plan.tasks] == ["T1", "T2"]
