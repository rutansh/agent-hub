#!/usr/bin/env python3
"""Report which credentials are set in .env, by variable name only.

Never prints a secret. The only value shown is JIRA_PROJECT_KEY, which is not secret.

Usage:
  env_status.py [--env .env] [--require github,gitlab,jira]

Exit code 1 if a required tool is not ready, 2 if the env file is missing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOLS = {
    "github": ["GH_TOKEN"],
    "gitlab": ["GITLAB_TOKEN"],
    "jira": ["JIRA_SITE", "JIRA_EMAIL", "JIRA_API_TOKEN"],
}
SHOWN_VALUES = ("JIRA_PROJECT_KEY",)


def read_env(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines. Comments and blank lines are ignored; quotes are stripped."""
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def tool_status(values: dict[str, str]) -> dict[str, dict]:
    """For each tool, whether every required variable is set (non-empty)."""
    status = {}
    for tool, names in TOOLS.items():
        missing = [name for name in names if not values.get(name)]
        status[tool] = {"ready": not missing, "missing": missing}
    return status


def build_report(path: Path) -> dict:
    """Build the report for one env file."""
    values = read_env(path)
    report: dict = {"env_file": str(path), "tools": tool_status(values)}
    report["values"] = {name: values[name] for name in SHOWN_VALUES if values.get(name)}
    return report


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--require", default="", help="comma-separated tools that must be ready")
    args = parser.parse_args(argv)
    if not args.env.exists():
        print(
            f"error: {args.env} not found; copy .env.example to .env and fill it in",
            file=sys.stderr,
        )
        return 2
    report = build_report(args.env)
    print(json.dumps(report, indent=2))
    required = [name.strip() for name in args.require.split(",") if name.strip()]
    unknown = [name for name in required if name not in TOOLS]
    if unknown:
        print(f"error: unknown tool(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    return 0 if all(report["tools"][name]["ready"] for name in required) else 1


if __name__ == "__main__":
    raise SystemExit(main())
