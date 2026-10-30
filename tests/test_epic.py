import json
from pathlib import Path

import epic
import pytest
from planlib import set_task_field


def run(root: Path, *args: str) -> int:
    return epic.main(["--root", str(root), *args])


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Team Workspaces!", "team-workspaces"),
        ("  Add   budgets & alerts  ", "add-budgets-alerts"),
        ("x" * 100, "x" * 40),
    ],
)
def test_slugify(title: str, expected: str) -> None:
    assert epic.slugify(title) == expected


def test_slugify_is_deterministic_and_truncates_on_word_boundary() -> None:
    title = "Add monthly budgets per category with overspend alerts and CSV export"
    assert epic.slugify(title) == epic.slugify(title) == "add-monthly-budgets-per-category-with"


def test_slugify_rejects_empty() -> None:
    with pytest.raises(ValueError):
        epic.slugify("!!!")


def test_init_creates_design_skeleton(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(tmp_path, "init", "Team workspaces") == 0
    info = json.loads(capsys.readouterr().out)
    assert info["slug"] == "team-workspaces"
    text = (tmp_path / "team-workspaces" / "design.md").read_text()
    assert text.startswith("# Team workspaces") and "Status: draft" in text


def test_init_refuses_to_overwrite(tmp_path: Path) -> None:
    assert run(tmp_path, "init", "Team workspaces") == 0
    assert run(tmp_path, "init", "Team workspaces") == 2


def test_status_walks_through_every_phase(tmp_path: Path, plan_text: str) -> None:
    folder = tmp_path / "e"
    folder.mkdir()
    assert epic.epic_status(folder)["next_agent"] == "architect"

    (folder / "design.md").write_text("# E\n\nStatus: draft\n")
    assert epic.epic_status(folder)["phase"] == "design"
    epic.approve_design(folder)
    assert epic.epic_status(folder)["reason"] == "plan.md missing"

    (folder / "plan.md").write_text("# Plan: E\n")
    assert epic.epic_status(folder)["reason"] == "plan invalid"

    (folder / "plan.md").write_text(plan_text)
    assert epic.epic_status(folder)["reason"] == "tickets not created"

    ticketed = set_task_field(
        set_task_field(plan_text, "T1", "Jira", "PAY-1"), "T2", "Jira", "none"
    )
    (folder / "plan.md").write_text(ticketed)
    status = epic.epic_status(folder)
    assert (status["phase"], status["next_agent"], status["next_task"]) == (
        "build",
        "builder",
        "T1",
    )

    finished = ticketed
    for task_id in ("T1", "T2"):
        finished = set_task_field(finished, task_id, "Status", "done")
    (folder / "plan.md").write_text(finished)
    assert epic.epic_status(folder) == {
        "phase": "done",
        "next_agent": None,
        "tasks_done": 2,
        "tasks_total": 2,
    }


def test_approve_adds_status_when_missing(tmp_path: Path) -> None:
    folder = tmp_path / "e"
    folder.mkdir()
    (folder / "design.md").write_text("# E\n\n## Goal\n")
    epic.approve_design(folder)
    assert epic.design_status(folder / "design.md") == "approved"


def test_validate_command_sets_exit_code(
    epic_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = epic_dir.parent
    assert run(root, "validate", "team-workspaces") == 0
    (epic_dir / "plan.md").write_text("# Plan: E\n\n## T1: One\n- Goal: g\n")
    assert run(root, "validate", "team-workspaces") == 1
    assert "acceptance" in capsys.readouterr().out


def test_unknown_epic_is_an_error(tmp_path: Path) -> None:
    assert run(tmp_path, "status", "nope") == 2
