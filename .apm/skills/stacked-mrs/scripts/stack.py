#!/usr/bin/env python3
"""Ship a plan as a stack of small merge requests, with the same rules every time.

Workflow:
  start PLAN [--base B]          begin a stack from the current (base) branch
  save PLAN T1                   commit the working tree as task T1's diff
  save PLAN T2                   ... one `save` per task, in plan order
  publish --confirm              push and open the chained MRs/PRs (after user approval)

Other commands: host, message PLAN TASK, status.

Rules enforced in code: tasks are saved in plan order; one commit per task with the message
'<JIRA-KEY or task id>: <title>'; a diff over --max-lines (default 300, docs/epics excluded)
is refused; nothing is pushed without --confirm.

GitLab uses `glab stack`; GitHub uses one branch per task and chained `gh pr create --base`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from planlib import Plan, Task, parse_plan, set_task_field, validate_plan

STATE_FILE = "agent-hub-stack.json"
DEFAULT_MAX_LINES = 300
_NUMSTAT_EXCLUDE = ":(exclude)docs/epics"


class StackError(RuntimeError):
    """Raised when a stack rule is violated or a command fails."""


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise StackError(f"'{cmd[0]}' is not installed (see the connect-tools skill)") from exc
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise StackError(f"{' '.join(cmd[:3])} failed ({result.returncode}): {detail}")
    return result


def git(*args: str) -> str:
    """Run git and return stripped stdout."""
    return _run(["git", *args]).stdout.strip()


def detect_host(override: str = "") -> str:
    """Return ``gitlab``, ``github`` or ``unknown`` from the ``origin`` remote URL."""
    if override:
        return override
    url = _run(["git", "remote", "get-url", "origin"], check=False).stdout.lower()
    if "gitlab" in url:
        return "gitlab"
    return "github" if "github" in url else "unknown"


def message_text(task: Task) -> str:
    """Canonical commit/MR title: '<KEY or Tn>: <title with a lowercase first letter>'."""
    title = task.title
    if len(title) > 1 and title[1].islower():
        title = title[0].lower() + title[1:]
    return f"{task.commit_prefix}: {title}"


def _branch_slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:30].strip("-")


def _state_path() -> Path:
    return Path(git("rev-parse", "--absolute-git-dir")) / STATE_FILE


def _load_state() -> dict:
    path = _state_path()
    if not path.exists():
        raise StackError("no stack started; run 'start PLAN' first")
    return json.loads(path.read_text())


def _load_plan(plan_path: Path) -> Plan:
    plan = parse_plan(plan_path.read_text())
    if errors := validate_plan(plan):
        raise StackError("plan is invalid: " + "; ".join(errors))
    return plan


def _find_task(plan: Plan, task_id: str) -> Task:
    for task in plan.tasks:
        if task.task_id == task_id:
            return task
    raise StackError(f"task {task_id} not in plan")


def start(plan_path: Path, base: str = "", host: str = "") -> dict:
    """Begin a stack. The current branch must be the base branch."""
    plan = _load_plan(plan_path)
    if _state_path().exists():
        raise StackError(f"a stack is already started; delete {_state_path()} to restart")
    current = git("branch", "--show-current")
    base = base or current
    if current != base:
        raise StackError(f"check out the base branch '{base}' first (on '{current}')")
    slug = plan_path.resolve().parent.name
    host = detect_host(host)
    if host == "unknown":
        raise StackError("cannot tell GitLab from GitHub; pass --host gitlab|github")
    if host == "gitlab":
        _run(["glab", "stack", "create", slug])
    state = {"slug": slug, "base": base, "host": host, "plan": str(plan_path), "tasks": []}
    _state_path().write_text(json.dumps(state, indent=2))
    return {"slug": slug, "base": base, "host": host, "tasks": len(plan.tasks)}


def changed_lines() -> int:
    """Lines added plus deleted in the staged diff, ignoring docs/epics."""
    out = git("diff", "--cached", "--numstat", "--", ".", _NUMSTAT_EXCLUDE)
    total = 0
    for line in out.splitlines():
        added, deleted, _ = line.split("\t", 2)
        total += (int(added) if added.isdigit() else 0) + (int(deleted) if deleted.isdigit() else 0)
    return total


def _check_save_order(state: dict, plan: Plan, task: Task) -> None:
    saved = {item["task"] for item in state["tasks"]}
    if task.task_id in saved:
        raise StackError(f"{task.task_id} is already saved")
    expected = next(t for t in plan.tasks if t.task_id not in saved)
    if expected.task_id != task.task_id:
        raise StackError(f"save tasks in plan order: next is {expected.task_id}")
    tip = state["tasks"][-1]["branch"] if state["tasks"] else state["base"]
    if (current := git("branch", "--show-current")) != tip:
        raise StackError(f"expected to be on '{tip}', but on '{current}'")


def _stage_and_check_size(max_lines: int, allow_large: bool) -> int:
    git("add", "-A")
    if _run(["git", "diff", "--cached", "--quiet"], check=False).returncode == 0:
        raise StackError("nothing to save: no changes")
    lines = changed_lines()
    if lines > max_lines and not allow_large:
        git("reset", "-q")
        raise StackError(
            f"diff is {lines} lines (limit {max_lines}); split the task or pass --allow-large"
        )
    return lines


def save(plan_path: Path, task_id: str, max_lines: int, allow_large: bool = False) -> dict:
    """Commit the working tree as one diff for ``task_id`` and mark the task done."""
    state, plan = _load_state(), _load_plan(plan_path)
    task = _find_task(plan, task_id)
    _check_save_order(state, plan, task)
    lines = _stage_and_check_size(max_lines, allow_large)
    original = plan_path.read_text()
    message = message_text(task)
    try:
        plan_path.write_text(set_task_field(original, task_id, "Status", "done"))
        git("add", "-A")
        if state["host"] == "gitlab":
            _run(["glab", "stack", "save", "-m", message])
        else:
            number = int(task_id[1:])
            git("checkout", "-b", f"{state['slug']}/{number}-{_branch_slug(task.title)}")
            git("commit", "-q", "-m", message)
    except StackError:
        plan_path.write_text(original)
        raise
    branch = git("branch", "--show-current")
    state["tasks"].append(
        {"task": task_id, "branch": branch, "message": message, "jira": task.jira}
    )
    _state_path().write_text(json.dumps(state, indent=2))
    return {"task": task_id, "branch": branch, "message": message, "lines": lines}


def _pr_body(index: int, total: int, jira: str) -> str:
    parts = [f"Part {index} of {total}."]
    if index > 1:
        parts.append("Depends on the previous PR in this stack; merge in order.")
    if re.fullmatch(r"[A-Z][A-Z0-9]+-\d+", jira):
        parts.append(f"Jira: {jira}")
    return "\n\n".join(parts)


def _publish_github(state: dict) -> list[str]:
    urls, parent = [], state["base"]
    total = len(state["tasks"])
    for index, item in enumerate(state["tasks"], start=1):
        branch = item["branch"]
        git("push", "-q", "-u", "origin", branch)
        existing = _run(["gh", "pr", "view", branch, "--json", "url", "-q", ".url"], check=False)
        if existing.returncode == 0 and existing.stdout.strip():
            urls.append(existing.stdout.strip())
        else:
            created = _run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--base",
                    parent,
                    "--head",
                    branch,
                    "--title",
                    item["message"],
                    "--body",
                    _pr_body(index, total, item["jira"]),
                ]
            )
            urls.append(created.stdout.strip().splitlines()[-1])
        parent = branch
    return urls


def publish(confirm: bool) -> dict:
    """Push the stack and open the chained merge requests."""
    if not confirm:
        raise StackError("refusing to push without --confirm (show the user the stack first)")
    state = _load_state()
    if not state["tasks"]:
        raise StackError("nothing to publish: no tasks saved")
    if state["host"] == "gitlab":
        output = _run(["glab", "stack", "sync"]).stdout.strip()
        return {"host": "gitlab", "output": output}
    return {"host": "github", "urls": _publish_github(state)}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("host").add_argument("--host", default="")
    sub.add_parser("status")
    sub.add_parser("publish").add_argument("--confirm", action="store_true")
    message = sub.add_parser("message")
    message.add_argument("plan", type=Path)
    message.add_argument("task")
    begin = sub.add_parser("start")
    begin.add_argument("plan", type=Path)
    begin.add_argument("--base", default="")
    begin.add_argument("--host", default="", choices=["", "gitlab", "github"])
    keep = sub.add_parser("save")
    keep.add_argument("plan", type=Path)
    keep.add_argument("task")
    keep.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    keep.add_argument("--allow-large", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "host":
            print(detect_host(args.host))
        elif args.command == "status":
            print(json.dumps(_load_state(), indent=2))
        elif args.command == "message":
            print(message_text(_find_task(_load_plan(args.plan), args.task)))
        elif args.command == "start":
            print(json.dumps(start(args.plan, args.base, args.host)))
        elif args.command == "save":
            print(json.dumps(save(args.plan, args.task, args.max_lines, args.allow_large)))
        else:
            print(json.dumps(publish(args.confirm)))
    except (StackError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
