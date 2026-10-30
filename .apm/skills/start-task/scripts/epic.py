#!/usr/bin/env python3
"""Create and track an epic workspace: docs/epics/<slug>/{design.md, plan.md}.

Commands (all print JSON unless noted):
  slug "<title>"          print the folder name for a title (plain text)
  init "<title>"          create docs/epics/<slug>/ with a design.md skeleton
  approve <slug>          mark design.md as approved (run after the user approves it)
  validate <slug>         check plan.md; exit 1 and list problems if invalid
  status <slug>           report the current phase and which agent runs next
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from planlib import next_task, parse_plan, validate_plan

DEFAULT_ROOT = Path("docs/epics")
MAX_SLUG_LENGTH = 40
_DESIGN_STATUS_RE = re.compile(r"^Status:\s*(\w+)\s*$", re.MULTILINE | re.IGNORECASE)

DESIGN_TEMPLATE = """\
# {title}

Status: draft

## Goal and scope
## Out of scope
## Current system (what exists today)
## Proposed design
## Data model changes
## Interfaces (APIs, events, UI)
## Non-functional requirements
## Rollout plan
## Decisions made (decision, options, reason)
## Risks
## Open questions
"""


def slugify(title: str) -> str:
    """Lowercase, hyphen-separated folder name, at most ``MAX_SLUG_LENGTH`` characters."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if len(slug) > MAX_SLUG_LENGTH:
        slug = slug[:MAX_SLUG_LENGTH].rsplit("-", 1)[0] or slug[:MAX_SLUG_LENGTH]
    if not slug:
        raise ValueError("title must contain letters or digits")
    return slug.strip("-")


def init_epic(title: str, root: Path) -> dict[str, str]:
    """Create the epic folder and design skeleton. Fails if the epic already exists."""
    slug = slugify(title)
    folder = root / slug
    if folder.exists():
        raise FileExistsError(f"{folder} already exists; run 'status {slug}' to resume it")
    folder.mkdir(parents=True)
    (folder / "design.md").write_text(DESIGN_TEMPLATE.format(title=title.strip()))
    return {"slug": slug, "dir": str(folder), "design": str(folder / "design.md")}


def design_status(design: Path) -> str:
    """Return the ``Status:`` value of design.md (``draft`` or ``approved``)."""
    match = _DESIGN_STATUS_RE.search(design.read_text())
    return match.group(1).lower() if match else "draft"


def approve_design(folder: Path) -> None:
    """Set design.md ``Status`` to approved."""
    design = folder / "design.md"
    text = design.read_text()
    if _DESIGN_STATUS_RE.search(text):
        text = _DESIGN_STATUS_RE.sub("Status: approved", text, count=1)
    else:
        title, _, rest = text.partition("\n")
        text = f"{title}\n\nStatus: approved\n{rest}"
    design.write_text(text)


def epic_status(folder: Path) -> dict[str, object]:
    """Work out which phase an epic is in and which agent should run next."""
    design, plan_file = folder / "design.md", folder / "plan.md"
    if not design.exists() or design_status(design) != "approved":
        return {"phase": "design", "next_agent": "architect", "reason": "design not approved"}
    if not plan_file.exists():
        return {"phase": "plan", "next_agent": "planner", "reason": "plan.md missing"}
    plan = parse_plan(plan_file.read_text())
    errors = validate_plan(plan)
    if errors:
        return {
            "phase": "plan",
            "next_agent": "planner",
            "reason": "plan invalid",
            "errors": errors,
        }
    if any(task.jira == "" for task in plan.tasks):
        return {"phase": "plan", "next_agent": "planner", "reason": "tickets not created"}
    done = sum(task.status == "done" for task in plan.tasks)
    counts = {"tasks_done": done, "tasks_total": len(plan.tasks)}
    upcoming = next_task(plan)
    if upcoming:
        return {"phase": "build", "next_agent": "builder", "next_task": upcoming.task_id, **counts}
    if done == len(plan.tasks):
        return {"phase": "done", "next_agent": None, **counts}
    return {"phase": "build", "next_agent": None, "reason": "remaining tasks are blocked", **counts}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="epics folder")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("slug", "init"):
        sub.add_parser(name).add_argument("title")
    for name in ("approve", "validate", "status"):
        sub.add_parser(name).add_argument("slug")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "slug":
            print(slugify(args.title))
        elif args.command == "init":
            print(json.dumps(init_epic(args.title, args.root)))
        else:
            return _run_existing(args)
    except (ValueError, FileExistsError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def _run_existing(args: argparse.Namespace) -> int:
    """Handle commands that act on an existing epic folder."""
    folder = args.root / args.slug
    if not folder.is_dir():
        raise FileNotFoundError(f"{folder} not found")
    if args.command == "approve":
        approve_design(folder)
        print(json.dumps({"slug": args.slug, "design": "approved"}))
    elif args.command == "validate":
        errors = validate_plan(parse_plan((folder / "plan.md").read_text()))
        print(json.dumps({"valid": not errors, "errors": errors}))
        return 1 if errors else 0
    else:
        print(json.dumps(epic_status(folder)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
