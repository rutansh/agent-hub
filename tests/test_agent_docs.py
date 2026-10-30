"""Keep the planner's plan.md template in sync with the parser the scripts use."""

import re
from pathlib import Path

import planlib

ROOT = Path(__file__).parent.parent
PLANNER = ROOT / ".apm" / "agents" / "planner.agent.md"


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


def test_skill_scripts_have_no_shebang() -> None:
    """Scripts are run as `python3 script.py`. A shebang on a non-executable file makes
    linters in consumer repos (which scan .agents/) report EXE001."""
    root = Path(__file__).parent.parent / ".apm" / "skills"
    offenders = [p.name for p in root.rglob("*.py") if p.read_text().startswith("#!")]
    assert offenders == []


def test_docs_do_not_mention_removed_commands() -> None:
    # Reason: branch creation moved from feature.py to ship.py; stale docs would send agents to
    # a command that no longer exists.
    for path in (ROOT / ".apm").rglob("*.md"):
        assert "feature.py branch" not in path.read_text(), path


def test_small_feature_is_routed_through_the_ship_skill() -> None:
    start = (ROOT / ".apm" / "skills" / "start-task" / "SKILL.md").read_text()
    assert "ship-small-feature" in start
