"""Keep the planner's plan.md template in sync with the parser the scripts use."""

import re
from pathlib import Path

import planlib

PLANNER = Path(__file__).parent.parent / ".apm" / "agents" / "planner.agent.md"


def _template() -> str:
    text = PLANNER.read_text()
    block = re.search(r"```\n\s*(# Plan:.*?)```", text, re.DOTALL)
    assert block, "planner.agent.md must contain the plan.md template"
    lines = [line.removeprefix("   ") for line in block.group(1).splitlines()]
    return "\n".join(line for line in lines if line.strip() != "...") + "\n"


def test_planner_template_parses_and_validates() -> None:
    plan = planlib.parse_plan(_template().replace("<", "").replace(">", ""))
    assert [t.task_id for t in plan.tasks] == ["T1", "T2"]
    assert plan.tasks[1].depends_on == ["T1"]
    # T2 is abbreviated in the template on purpose; T1 is complete and must be valid.
    assert [e for e in planlib.validate_plan(plan) if e.startswith("T1")] == []


def test_template_placeholders_mean_no_jira_yet() -> None:
    plan = planlib.parse_plan(_template())
    assert all(not task.jira.startswith("PAY") for task in plan.tasks)
