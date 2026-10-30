"""Deterministic git side of the small-feature flow: ticket -> branch -> commit -> merge request.

Commands (all print JSON):
  status                              where the flow stands (branch, ticket, checks, commits)
  branch --ticket PAY-7 --name "Delete a task"
                                      create feature/PAY-7-delete-a-task from the base branch
  commit --summary "Delete a task"    commit everything as "PAY-7: delete a task"
  mr [--confirm] [--host github|gitlab]
                                      preview the merge request, or push and open it

The rules are enforced here, not left to the agent:
  * a branch needs a Jira key, and commits and merge requests only work on a ticket branch
  * `commit` needs a passing `feature.py check` for these exact file contents
  * `.env` files are never committed
  * `mr` needs a clean tree, at least one commit, and a passing check on the committed code
  * `mr` only previews until the user approves it and the agent re-runs it with --confirm

Exit codes: 0 done, 1 a command failed, 2 refused (a rule above) or preview only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from receipt import passed_tree, read_receipt, tree_hash

KEY_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
BRANCH_RE = re.compile(r"^feature/([A-Z][A-Z0-9]+-\d+)-")
MAX_SLUG = 40
ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template")


class ShipError(RuntimeError):
    """A command failed."""


class Refusal(ShipError):
    """A flow rule was violated; nothing was changed."""


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise ShipError(f"'{cmd[0]}' is not installed (see the connect-tools skill)") from exc
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ShipError(f"{' '.join(cmd[:3])} failed ({result.returncode}): {detail}")
    return result


def git(*args: str) -> str:
    """Run git and return stripped stdout."""
    return _run(["git", *args]).stdout.strip()


def _root() -> Path:
    return Path(git("rev-parse", "--show-toplevel"))


def base_branch(override: str = "") -> str:
    """The branch merge requests target: --base, origin's default, then main or master."""
    if override:
        return override
    head = _run(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], check=False)
    if head.returncode == 0 and head.stdout.strip():
        return head.stdout.strip().removeprefix("origin/")
    for name in ("main", "master"):
        if _run(["git", "rev-parse", "--verify", "-q", name], check=False).returncode == 0:
            return name
    raise Refusal("cannot tell the base branch; pass --base")


def detect_host(override: str = "") -> str:
    """Return ``gitlab``, ``github`` or ``unknown`` from the ``origin`` remote URL."""
    if override:
        return override
    url = _run(["git", "remote", "get-url", "origin"], check=False).stdout.lower()
    if "gitlab" in url:
        return "gitlab"
    return "github" if "github" in url else "unknown"


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:MAX_SLUG].strip("-")
    if not slug:
        raise Refusal("the feature name must contain letters or digits")
    return slug


def start_branch(ticket: str, name: str, base: str = "") -> dict:
    """Create ``feature/<TICKET>-<slug>`` from the base branch (idempotent on that branch)."""
    if not KEY_RE.match(ticket):
        raise Refusal(f"{ticket!r} is not a Jira key like PAY-123; get a ticket first")
    base = base_branch(base)
    target = f"feature/{ticket}-{_slug(name)}"
    current = git("branch", "--show-current")
    if current != target:
        if current != base:
            raise Refusal(f"start from {base}, not from {current}")
        git("checkout", "-q", "-b", target)
    return {"branch": target, "base": base}


def _ticket_branch(base: str) -> tuple[str, str]:
    branch = git("branch", "--show-current")
    match = BRANCH_RE.match(branch)
    if branch == base or not match:
        raise Refusal(f"'{branch}' is not a ticket branch (feature/PAY-123-...); run 'branch'")
    return branch, match.group(1)


def _is_env_file(path: str) -> bool:
    name = Path(path).name
    is_env = name == ".env" or name.startswith(".env.")
    return is_env and not name.endswith(ENV_TEMPLATE_SUFFIXES)


def commit(summary: str, base: str = "") -> dict:
    """Commit all changes as '<KEY>: <summary>', if the checks passed on exactly this code."""
    _, ticket = _ticket_branch(base_branch(base))
    if passed_tree(_root()) is None:
        raise Refusal("no passing check for these exact contents; run feature.py check first")
    git("add", "-A")
    staged = git("diff", "--cached", "--name-only").splitlines()
    if not staged:
        git("reset", "-q")
        raise Refusal("nothing to commit")
    if secrets := [path for path in staged if _is_env_file(path)]:
        git("reset", "-q")
        raise Refusal(f"refusing to commit credential files: {', '.join(secrets)}")
    if len(summary) > 1 and summary[1].islower():
        summary = summary[0].lower() + summary[1:]
    message = f"{ticket}: {summary}"
    git("commit", "-q", "-m", message)
    return {"commit": git("rev-parse", "--short", "HEAD"), "message": message}


def _commits_ahead(base: str) -> list[str]:
    return git("log", f"{base}..HEAD", "--reverse", "--format=%s").splitlines()


def _check_state(root: Path) -> str:
    saved = read_receipt(root)
    if saved is None:
        return "none"
    if not saved["passed"]:
        return "failed"
    return "passed" if saved["tree"] == tree_hash(root) else "stale"


def status(base: str = "") -> dict:
    """Describe where the flow stands."""
    base = base_branch(base)
    branch = git("branch", "--show-current")
    match = BRANCH_RE.match(branch)
    return {
        "branch": branch,
        "base": base,
        "on_base": branch == base,
        "ticket": match.group(1) if match else None,
        "dirty": bool(git("status", "--porcelain")),
        "checks": _check_state(_root()),
        "commits_ahead": 0 if branch == base else len(_commits_ahead(base)),
    }


def _merge_request_details(base: str) -> dict:
    branch, ticket = _ticket_branch(base)
    if git("status", "--porcelain"):
        raise Refusal("uncommitted changes; run 'commit' first")
    subjects = _commits_ahead(base)
    if not subjects:
        raise Refusal(f"no commits on {branch} yet")
    tree = passed_tree(_root())
    if tree is None or tree != git("rev-parse", "HEAD^{tree}"):
        raise Refusal("checks have not passed on the committed code; run feature.py check")
    title = subjects[0] if subjects[0].startswith(f"{ticket}:") else f"{ticket}: {subjects[0]}"
    body = "\n".join(
        [f"Jira: {ticket}", "", "Changes:", *[f"- {s}" for s in subjects], ""]
        + [f"Tests passed on this exact code (tree {tree[:10]})."]
    )
    return {"title": title, "body": body, "base": base, "head": branch}


def _open_github(details: dict) -> str:
    head = details["head"]
    existing = _run(["gh", "pr", "view", head, "--json", "url", "-q", ".url"], check=False)
    if existing.returncode == 0 and existing.stdout.strip():
        return existing.stdout.strip()
    created = _run(
        ["gh", "pr", "create", "--base", details["base"], "--head", head]
        + ["--title", details["title"], "--body", details["body"]]
    )
    return created.stdout.strip().splitlines()[-1]


def _open_gitlab(details: dict) -> str:
    created = _run(
        ["glab", "mr", "create", "--source-branch", details["head"]]
        + ["--target-branch", details["base"], "--title", details["title"]]
        + ["--description", details["body"], "--yes"]
    )
    return created.stdout.strip().splitlines()[-1]


def merge_request(confirm: bool, host: str = "", base: str = "") -> dict:
    """Preview the merge request, or (with ``confirm``) push the branch and open it."""
    details = _merge_request_details(base_branch(base))
    host = detect_host(host)
    if host not in ("github", "gitlab"):
        raise Refusal("cannot tell GitHub from GitLab; pass --host github or --host gitlab")
    if not confirm:
        return {"created": False, "host": host, **details}
    git("push", "-q", "-u", "origin", details["head"])
    url = _open_github(details) if host == "github" else _open_gitlab(details)
    return {"created": True, "url": url}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="", help="base branch (default: detected)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    branch = sub.add_parser("branch")
    branch.add_argument("--ticket", required=True)
    branch.add_argument("--name", required=True)
    sub.add_parser("commit").add_argument("--summary", required=True)
    mr = sub.add_parser("mr")
    mr.add_argument("--host", default="", choices=["", "github", "gitlab"])
    mr.add_argument("--confirm", action="store_true", help="user approved the preview")
    return parser


def _dispatch(args: argparse.Namespace) -> tuple[dict, int]:
    if args.command == "status":
        return status(args.base), 0
    if args.command == "branch":
        return start_branch(args.ticket, args.name, args.base), 0
    if args.command == "commit":
        return commit(args.summary, args.base), 0
    result = merge_request(args.confirm, args.host, args.base)
    if not result["created"]:
        print(
            "not opened: show the preview to the user, then re-run with --confirm", file=sys.stderr
        )
    return result, 0 if result["created"] else 2


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = _build_parser().parse_args(argv)
    try:
        result, code = _dispatch(args)
    except Refusal as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except ShipError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
