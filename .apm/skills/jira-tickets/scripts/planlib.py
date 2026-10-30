"""Parse, validate and update the epic plan file written by the planner agent.

Format (one block per task)::

    # Plan: <epic title>
    - Epic Jira: PAY-100

    ## T1: <imperative title>
    - Jira: PAY-101
    - Depends on: none
    - Goal: <what and why>
    - Likely files: a.py, b.py
    - Acceptance criteria:
      - [ ] <verifiable item>
    - Tests: <what to cover>
    - Status: todo

``Jira`` is a ticket key, ``none`` (deliberately no ticket) or ``(filled in later)``.
``Status`` is one of ``todo``, ``in-progress``, ``done``, ``blocked``.

This file is vendored into several skills. Edit ``shared/planlib.py`` only, then run
``scripts/sync-shared.sh``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

STATUSES = ("todo", "in-progress", "done", "blocked")
MAX_TITLE_LENGTH = 80
NO_JIRA = "none"

JIRA_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
_PLAN_RE = re.compile(r"^# Plan:\s*(.+?)\s*$")
_TASK_RE = re.compile(r"^## (T\d+):\s*(.+?)\s*$")
_FIELD_RE = re.compile(r"^- ([A-Za-z][A-Za-z ]*):[ \t]*(.*?)\s*$")
_CRITERION_RE = re.compile(r"^\s+- \[([ xX])\]\s+(.+?)\s*$")
_TASK_ID_RE = re.compile(r"T\d+")


class PlanError(ValueError):
    """Raised when a plan cannot be updated."""


@dataclass
class Task:
    """One task in the plan; each task becomes one ticket and one merge request."""

    task_id: str
    title: str
    jira: str = ""
    depends_on: list[str] = field(default_factory=list)
    goal: str = ""
    files: list[str] = field(default_factory=list)
    acceptance: list[tuple[bool, str]] = field(default_factory=list)
    tests: str = ""
    status: str = "todo"

    @property
    def commit_prefix(self) -> str:
        """Jira key when the task has one, otherwise the task id."""
        return self.jira if JIRA_KEY_RE.fullmatch(self.jira) else self.task_id


@dataclass
class Plan:
    """A parsed plan file."""

    title: str = ""
    epic_jira: str = ""
    tasks: list[Task] = field(default_factory=list)


def _jira_value(raw: str) -> str:
    """Normalize a Jira field: a key, ``none``, or empty for 'not created yet'."""
    match = JIRA_KEY_RE.search(raw)
    if match:
        return match.group(0)
    return NO_JIRA if raw.strip().lower() == NO_JIRA else ""


def _apply_field(plan: Plan, task: Task | None, name: str, value: str) -> None:
    """Store one ``- Name: value`` line on the plan or the current task."""
    if task is None:
        if name == "epic jira":
            plan.epic_jira = _jira_value(value)
        return
    if name == "jira":
        task.jira = _jira_value(value)
    elif name == "depends on":
        ids = _TASK_ID_RE.findall(value)
        # Reason: keep unparseable text so validation reports it instead of ignoring it.
        task.depends_on = ids or ([] if value.strip().lower() in ("none", "") else [value])
    elif name == "goal":
        task.goal = value
    elif name == "likely files":
        task.files = [item.strip() for item in value.split(",") if item.strip()]
    elif name == "tests":
        task.tests = value
    elif name == "status":
        task.status = value.strip().lower()


def parse_plan(text: str) -> Plan:
    """Parse plan text into a ``Plan``. Never raises; use ``validate_plan`` to check it."""
    plan = Plan()
    task: Task | None = None
    in_criteria = False
    for line in text.splitlines():
        if task is None and not plan.title and (match := _PLAN_RE.match(line)):
            plan.title = match.group(1)
        elif match := _TASK_RE.match(line):
            task = Task(task_id=match.group(1), title=match.group(2))
            plan.tasks.append(task)
            in_criteria = False
        elif in_criteria and task and (match := _CRITERION_RE.match(line)):
            task.acceptance.append((match.group(1).lower() == "x", match.group(2)))
        elif match := _FIELD_RE.match(line):
            name = match.group(1).strip().lower()
            _apply_field(plan, task, name, match.group(2))
            in_criteria = task is not None and name == "acceptance criteria"
    return plan


def _validate_task(task: Task, index: int, tasks: list[Task]) -> list[str]:
    """Return the problems found in one task."""
    errors = []
    label = task.task_id
    if task.task_id != f"T{index}":
        errors.append(f"{label}: expected id T{index} (ids must be sequential from T1)")
    if len(task.title) > MAX_TITLE_LENGTH:
        errors.append(f"{label}: title is longer than {MAX_TITLE_LENGTH} characters")
    if not task.goal:
        errors.append(f"{label}: missing 'Goal'")
    if not task.acceptance:
        errors.append(f"{label}: needs at least one acceptance criterion '- [ ] ...'")
    if task.status not in STATUSES:
        errors.append(f"{label}: status '{task.status}' is not one of {', '.join(STATUSES)}")
    earlier = {item.task_id for item in tasks[: index - 1]}
    for dep in task.depends_on:
        if dep not in earlier:
            errors.append(f"{label}: depends on '{dep}', which is not an earlier task")
    return errors


def validate_plan(plan: Plan) -> list[str]:
    """Return a list of problems; an empty list means the plan is valid."""
    errors = []
    if not plan.title:
        errors.append("missing '# Plan: <title>' header")
    if not plan.tasks:
        return [*errors, "plan has no tasks ('## T1: <title>' blocks)"]
    for index, task in enumerate(plan.tasks, start=1):
        errors.extend(_validate_task(task, index, plan.tasks))
    return errors


def next_task(plan: Plan) -> Task | None:
    """First unfinished task whose dependencies are all done, or ``None``."""
    done = {task.task_id for task in plan.tasks if task.status == "done"}
    for task in plan.tasks:
        if task.status in ("todo", "in-progress") and all(d in done for d in task.depends_on):
            return task
    return None


def _task_span(lines: list[str], task_id: str) -> tuple[int, int]:
    """Return (heading index, end index) for a task block."""
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if (m := _TASK_RE.match(line)) and m.group(1) == task_id
        ),
        None,
    )
    if start is None:
        raise PlanError(f"task {task_id} not found in plan")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return start, end


def set_task_field(text: str, task_id: str, field_name: str, value: str) -> str:
    """Return ``text`` with ``- <field_name>: <value>`` set on one task (added if missing)."""
    lines = text.splitlines()
    start, end = _task_span(lines, task_id)
    label = f"- {field_name}:"
    for index in range(start + 1, end):
        if lines[index].startswith(label):
            lines[index] = f"{label} {value}"
            return "\n".join(lines) + "\n"
    lines.insert(start + 1, f"{label} {value}")
    return "\n".join(lines) + "\n"


def set_epic_jira(text: str, key: str) -> str:
    """Return ``text`` with the ``- Epic Jira:`` line set, before the first task."""
    lines = text.splitlines()
    first_task = next((i for i, line in enumerate(lines) if _TASK_RE.match(line)), len(lines))
    for index in range(first_task):
        if lines[index].startswith("- Epic Jira:"):
            lines[index] = f"- Epic Jira: {key}"
            return "\n".join(lines) + "\n"
    header = next((i for i, line in enumerate(lines) if _PLAN_RE.match(line)), None)
    if header is None:
        raise PlanError("plan has no '# Plan:' header")
    lines.insert(header + 1, f"- Epic Jira: {key}")
    return "\n".join(lines) + "\n"
