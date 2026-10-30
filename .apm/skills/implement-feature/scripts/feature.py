"""Deterministic helpers for implementing a feature in any repo.

Commands (all print JSON):
  detect                      how this project is tested and linted (from its files)
  branch "<name>" [--ticket PAY-1] [--dry-run]
                              create feature/<ticket>-<slug> (or just print the name)
  check                       run the detected test and lint commands and report each one

`check` never claims a check passed unless it ran and exited 0. Exit codes:
  0 all detected checks passed and tests ran, 1 a check failed, 4 tests could not be run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

Command = list[str] | None
_NO_TESTS_NPM = "no test specified"
MAX_BRANCH_SLUG = 40


def _python(root: Path) -> dict:
    text = (root / "pyproject.toml").read_text()
    lock = root / "uv.lock"
    run = ["uv", "run"] if lock.exists() else []
    test: Command = None
    if "pytest" in text or (root / "tests").is_dir() or (root / "pytest.ini").exists():
        test = [*run, "pytest", "-q"]
    lint: Command = None
    if "[tool.ruff" in text or (root / "ruff.toml").exists():
        # Reason: a project may configure ruff without depending on it; uvx always works.
        if lock.exists() and "ruff" not in lock.read_text():
            lint = ["uvx", "ruff", "check", "."]
        else:
            lint = [*run, "ruff", "check", "."]
    return {"language": "python", "test": test, "lint": lint}


def _node(root: Path) -> dict:
    scripts = json.loads((root / "package.json").read_text()).get("scripts", {})
    manager = "pnpm" if (root / "pnpm-lock.yaml").exists() else "npm"
    if (root / "yarn.lock").exists():
        manager = "yarn"
    test = lint = None
    if "test" in scripts and _NO_TESTS_NPM not in scripts["test"]:
        test = [manager, "test"]
    if "lint" in scripts:
        lint = [manager, "run", "lint"]
    return {"language": "node", "test": test, "lint": lint}


def _make(root: Path) -> dict:
    text = (root / "Makefile").read_text()
    test = ["make", "test"] if re.search(r"^test:", text, re.MULTILINE) else None
    lint = ["make", "lint"] if re.search(r"^lint:", text, re.MULTILINE) else None
    return {"language": "unknown", "test": test, "lint": lint}


def detect(root: Path) -> dict:
    """Detect the language and the test/lint commands from marker files."""
    if (root / "pyproject.toml").exists():
        return _python(root)
    if (root / "package.json").exists():
        return _node(root)
    if (root / "go.mod").exists():
        return {"language": "go", "test": ["go", "test", "./..."], "lint": ["go", "vet", "./..."]}
    if (root / "Cargo.toml").exists():
        return {"language": "rust", "test": ["cargo", "test"], "lint": ["cargo", "clippy"]}
    if (root / "Makefile").exists():
        return _make(root)
    return {"language": "unknown", "test": None, "lint": None}


def branch_name(name: str, ticket: str = "") -> str:
    """Return ``feature/<TICKET-><slug>``."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:MAX_BRANCH_SLUG].strip("-")
    if not slug:
        raise ValueError("branch name must contain letters or digits")
    return f"feature/{ticket + '-' if ticket else ''}{slug}"


def create_branch(name: str, ticket: str = "", dry_run: bool = False) -> str:
    """Create the branch from the current HEAD (unless ``dry_run``) and return its name."""
    branch = branch_name(name, ticket)
    if not dry_run:
        result = subprocess.run(
            ["git", "checkout", "-b", branch], capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
    return branch


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _run_check(label: str, command: Command, root: Path) -> dict:
    if command is None:
        return {"check": label, "status": "not-run", "reason": "no command detected"}
    if shutil.which(command[0]) is None:
        return {
            "check": label,
            "command": command,
            "status": "not-run",
            "reason": f"'{command[0]}' is not installed",
        }
    # Reason: tools colour their output on some terminals; the agent reads plain text
    env = {**os.environ, "NO_COLOR": "1"}
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, env=env, check=False)
    outcome = {
        "check": label,
        "command": command,
        "exit_code": result.returncode,
        "status": "passed" if result.returncode == 0 else "failed",
    }
    if result.returncode != 0:
        text = _ANSI_RE.sub("", result.stdout + result.stderr)
        outcome["output_tail"] = text.strip().splitlines()[-15:]
    return outcome


def run_checks(root: Path) -> tuple[dict, int]:
    """Run test and lint commands. Returns (report, exit code)."""
    found = detect(root)
    results = [_run_check("test", found["test"], root), _run_check("lint", found["lint"], root)]
    statuses = {item["check"]: item["status"] for item in results}
    if "failed" in statuses.values():
        code = 1
    else:
        code = 0 if statuses["test"] == "passed" else 4
    return {"language": found["language"], "results": results, "exit_code": code}, code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."), help="project folder")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("detect")
    sub.add_parser("check")
    branch = sub.add_parser("branch")
    branch.add_argument("name")
    branch.add_argument("--ticket", default="")
    branch.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "detect":
            print(json.dumps(detect(args.root)))
        elif args.command == "branch":
            print(json.dumps({"branch": create_branch(args.name, args.ticket, args.dry_run)}))
        else:
            report, code = run_checks(args.root)
            print(json.dumps(report, indent=2))
            return code
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
