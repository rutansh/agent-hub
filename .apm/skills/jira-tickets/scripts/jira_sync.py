"""Turn plan.md into Jira tickets with the Atlassian CLI (acli), deterministically.

Commands:
  preview PLAN                      print the tickets that would be created (no side effects)
  create PLAN --project KEY --confirm
                                    create the epic and one child ticket per task, writing each
                                    new key back into PLAN. Skips tasks that already have a key,
                                    so it is safe to re-run after a failure.
  export-markdown PLAN              fallback when Jira is unavailable: write tickets.md next to
                                    PLAN and mark tasks 'Jira: none'

Creating tickets is visible to the whole team, so `create` refuses to run without --confirm.
Pass it only after the user has approved the output of `preview`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from planlib import (
    NO_JIRA,
    Plan,
    Task,
    parse_plan,
    set_epic_jira,
    set_task_field,
    validate_plan,
)

ACLI = "acli"


class JiraError(RuntimeError):
    """Raised when acli fails or its output cannot be understood."""


def ticket_description(task: Task, plan: Plan) -> str:
    """Build the ticket body from the plan fields, in a fixed layout."""
    keys = {t.task_id: t.jira for t in plan.tasks}
    lines = [task.goal, "", "Acceptance criteria:"]
    lines += [f"- [{'x' if done else ' '}] {text}" for done, text in task.acceptance]
    if task.depends_on:
        deps = [f"{d} ({keys[d]})" if keys.get(d) else d for d in task.depends_on]
        lines += ["", f"Depends on: {', '.join(deps)}"]
    if task.files:
        lines += ["", f"Likely files: {', '.join(task.files)}"]
    if task.tests:
        lines += ["", f"Tests: {task.tests}"]
    return "\n".join(lines) + "\n"


def preview(plan: Plan) -> list[dict[str, object]]:
    """Return the tickets that ``create`` would make, in creation order."""
    items: list[dict[str, object]] = [
        {"type": "Epic", "task_id": None, "summary": plan.title, "existing": plan.epic_jira or None}
    ]
    for task in plan.tasks:
        items.append(
            {
                "type": "Task",
                "task_id": task.task_id,
                "summary": task.title,
                "depends_on": task.depends_on,
                "existing": task.jira or None,
                "description": ticket_description(task, plan),
            }
        )
    return items


def extract_key(output: str, project: str, exclude: str = "") -> str:
    """Find the key of the ticket acli just created.

    Prefers the top-level ``key`` of JSON output; falls back to the first ``PROJECT-123``
    in the text that is not ``exclude`` (the parent, which acli may echo back).
    """
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict) and isinstance(data.get("key"), str):
        return data["key"]
    for match in re.finditer(rf"\b{re.escape(project)}-\d+\b", output):
        if match.group(0) != exclude:
            return match.group(0)
    raise JiraError(f"could not find a ticket key in acli output: {output.strip()[:200]!r}")


def _run_acli(args: list[str]) -> str:
    try:
        result = subprocess.run([ACLI, *args], capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise JiraError("acli is not installed (see the connect-tools skill)") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise JiraError(f"acli failed ({result.returncode}): {detail}")
    return result.stdout


def _create(project: str, issue_type: str, summary: str, body_file: Path, parent: str = "") -> str:
    args = ["jira", "workitem", "create", "--project", project, "--type", issue_type]
    args += ["--summary", summary, "--description-file", str(body_file), "--json"]
    if parent:
        args += ["--parent", parent]
    return extract_key(_run_acli(args), project, exclude=parent)


def create_tickets(plan_path: Path, project: str, task_type: str = "Task") -> list[str]:
    """Create the epic (if needed) and every task without a key. Returns the new keys."""
    text = plan_path.read_text()
    plan = parse_plan(text)
    if errors := validate_plan(plan):
        raise JiraError("plan is invalid: " + "; ".join(errors))
    folder = plan_path.parent
    (folder / "tickets").mkdir(exist_ok=True)
    created: list[str] = []
    epic = plan.epic_jira
    if not epic:
        design = folder / "design.md"
        epic_body = folder / "tickets" / "epic.md"
        epic_body.write_text(design.read_text() if design.exists() else plan.title + "\n")
        epic = _create(project, "Epic", plan.title, epic_body)
        plan_path.write_text(set_epic_jira(text, epic))
        created.append(epic)
    for task in plan.tasks:
        if task.jira:
            continue
        body = folder / "tickets" / f"{task.task_id}.md"
        body.write_text(ticket_description(task, parse_plan(plan_path.read_text())))
        key = _create(project, task_type, task.title, body, parent=epic)
        # Reason: persist after every ticket so a later failure never loses created keys.
        plan_path.write_text(set_task_field(plan_path.read_text(), task.task_id, "Jira", key))
        created.append(key)
    return created


def export_markdown(plan_path: Path) -> Path:
    """Write tickets.md for manual entry and mark un-ticketed tasks as 'Jira: none'."""
    text = plan_path.read_text()
    plan = parse_plan(text)
    if errors := validate_plan(plan):
        raise JiraError("plan is invalid: " + "; ".join(errors))
    out = [f"# Tickets: {plan.title}", "", "Not created in Jira. Paste these in manually.", ""]
    for task in plan.tasks:
        out += [f"## {task.task_id}: {task.title}", "", ticket_description(task, plan)]
        if not task.jira:
            text = set_task_field(text, task.task_id, "Jira", NO_JIRA)
    target = plan_path.parent / "tickets.md"
    target.write_text("\n".join(out))
    plan_path.write_text(text)
    return target


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preview", "create", "export-markdown"):
        sub.add_parser(name).add_argument("plan", type=Path)
    create = sub.choices["create"]
    create.add_argument("--project", required=True, help="Jira project key, e.g. PAY")
    create.add_argument("--task-type", default="Task")
    create.add_argument("--confirm", action="store_true", help="user approved the preview")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "preview":
            plan = parse_plan(args.plan.read_text())
            if errors := validate_plan(plan):
                raise JiraError("plan is invalid: " + "; ".join(errors))
            print(json.dumps(preview(plan), indent=2))
        elif args.command == "create":
            if not args.confirm:
                print(
                    "refusing to create tickets without --confirm (run 'preview' first and "
                    "get the user's approval)",
                    file=sys.stderr,
                )
                return 2
            print(json.dumps({"created": create_tickets(args.plan, args.project, args.task_type)}))
        else:
            print(json.dumps({"written": str(export_markdown(args.plan))}))
    except (JiraError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
