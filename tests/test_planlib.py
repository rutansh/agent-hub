import pytest
from planlib import (
    PlanError,
    next_task,
    parse_plan,
    set_epic_jira,
    set_task_field,
    validate_plan,
)


def test_parse_reads_header_tasks_and_fields(plan_text: str) -> None:
    plan = parse_plan(plan_text)
    assert plan.title == "Team workspaces"
    assert [t.task_id for t in plan.tasks] == ["T1", "T2"]
    first, second = plan.tasks
    assert first.title == "Add workspace data model"
    assert first.depends_on == []
    assert second.depends_on == ["T1"]
    assert first.files == ["workspaces.py", "tests/test_workspaces.py"]
    assert first.acceptance == [
        (False, "A workspace can be created"),
        (False, "Members can be added"),
    ]
    assert first.jira == "" and first.status == "todo"


def test_valid_plan_has_no_errors(plan_text: str) -> None:
    assert validate_plan(parse_plan(plan_text)) == []


def test_empty_text_reports_missing_header_and_tasks() -> None:
    errors = validate_plan(parse_plan(""))
    assert any("header" in e for e in errors)
    assert any("no tasks" in e for e in errors)


def test_validation_catches_each_kind_of_problem(plan_text: str) -> None:
    broken = (
        plan_text.replace("## T2:", "## T5:")
        .replace("- Goal: Store workspaces and members.", "- Goal:")
        .replace("- Status: todo", "- Status: sleeping", 1)
    )
    errors = validate_plan(parse_plan(broken))
    assert any("T5" in e and "sequential" in e for e in errors)
    assert any("T1: missing 'Goal'" in e for e in errors)
    assert any("sleeping" in e for e in errors)


def test_forward_and_unknown_dependencies_are_rejected(plan_text: str) -> None:
    forward = plan_text.replace("- Depends on: none", "- Depends on: T2", 1)
    assert any("not an earlier task" in e for e in validate_plan(parse_plan(forward)))
    typo = plan_text.replace("- Depends on: T1", "- Depends on: t1")
    assert any("not an earlier task" in e for e in validate_plan(parse_plan(typo)))


def test_task_without_acceptance_criteria_is_rejected(plan_text: str) -> None:
    broken = plan_text.replace("  - [ ] `workspace create` works\n", "")
    assert any("acceptance" in e for e in validate_plan(parse_plan(broken)))


def test_jira_values_are_normalized(plan_text: str) -> None:
    text = set_task_field(plan_text, "T1", "Jira", "PAY-101")
    text = set_task_field(text, "T2", "Jira", "none")
    plan = parse_plan(text)
    assert plan.tasks[0].jira == "PAY-101" and plan.tasks[0].commit_prefix == "PAY-101"
    assert plan.tasks[1].jira == "none" and plan.tasks[1].commit_prefix == "T2"


def test_set_task_field_changes_only_that_task(plan_text: str) -> None:
    updated = set_task_field(plan_text, "T2", "Status", "done")
    plan = parse_plan(updated)
    assert [t.status for t in plan.tasks] == ["todo", "done"]
    assert updated.count("\n") == plan_text.count("\n")


def test_set_task_field_adds_missing_field() -> None:
    text = "# Plan: X\n\n## T1: One\n- Goal: g\n"
    assert "- Status: done" in set_task_field(text, "T1", "Status", "done")


def test_set_task_field_unknown_task_raises(plan_text: str) -> None:
    with pytest.raises(PlanError):
        set_task_field(plan_text, "T9", "Status", "done")


def test_set_epic_jira_replaces_and_inserts(plan_text: str) -> None:
    assert parse_plan(set_epic_jira(plan_text, "PAY-100")).epic_jira == "PAY-100"
    bare = "# Plan: X\n\n## T1: One\n- Goal: g\n"
    assert parse_plan(set_epic_jira(bare, "PAY-7")).epic_jira == "PAY-7"


def test_next_task_respects_dependencies_and_status(plan_text: str) -> None:
    plan = parse_plan(plan_text)
    assert next_task(plan).task_id == "T1"
    blocked = parse_plan(set_task_field(plan_text, "T1", "Status", "blocked"))
    assert next_task(blocked) is None
    done = parse_plan(set_task_field(plan_text, "T1", "Status", "done"))
    assert next_task(done).task_id == "T2"
    finished = parse_plan(
        set_task_field(set_task_field(plan_text, "T1", "Status", "done"), "T2", "Status", "done")
    )
    assert next_task(finished) is None
