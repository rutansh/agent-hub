"""Shared fixtures. Skill scripts are not a package, so put their folders on sys.path."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".apm" / "skills"

# Reason: planlib.py is vendored in several skills; CI proves the copies are identical,
# so importing any one of them is equivalent.
for skill in (
    "start-task",
    "jira-tickets",
    "stacked-mrs",
    "implement-feature",
    "ship-small-feature",
    "connect-tools",
):
    sys.path.insert(0, str(SKILLS / skill / "scripts"))

SAMPLE_PLAN = """\
# Plan: Team workspaces
- Epic Jira: (filled in later)

## T1: Add workspace data model
- Jira: (filled in later)
- Depends on: none
- Goal: Store workspaces and members.
- Likely files: workspaces.py, tests/test_workspaces.py
- Acceptance criteria:
  - [ ] A workspace can be created
  - [ ] Members can be added
- Tests: store round trip
- Status: todo

## T2: Add workspace CLI commands
- Jira: (filled in later)
- Depends on: T1
- Goal: Let users manage workspaces from the CLI.
- Likely files: cli.py
- Acceptance criteria:
  - [ ] `workspace create` works
- Tests: CLI tests
- Status: todo
"""


@pytest.fixture(autouse=True)
def git_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scripts under test run `git commit`; CI runners have no git identity configured."""
    for who in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{who}_NAME", "Test User")
        monkeypatch.setenv(f"GIT_{who}_EMAIL", "test@example.com")


@pytest.fixture
def plan_text() -> str:
    return SAMPLE_PLAN


@pytest.fixture
def epic_dir(tmp_path: Path) -> Path:
    """An epic folder containing an approved design and a valid plan."""
    folder = tmp_path / "docs" / "epics" / "team-workspaces"
    folder.mkdir(parents=True)
    (folder / "design.md").write_text("# Team workspaces\n\nStatus: approved\n")
    (folder / "plan.md").write_text(SAMPLE_PLAN)
    return folder


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A directory placed first on PATH so tests can add fake `acli`, `gh`, `glab`."""
    folder = tmp_path / "fakebin"
    folder.mkdir()
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    return folder


def write_fake_tool(folder: Path, name: str, body: str) -> Path:
    """Create an executable shell script named ``name`` in ``folder``."""
    path = folder / name
    path.write_text(f"#!/usr/bin/env bash\n{body}\n")
    path.chmod(0o755)
    return path


def git(cwd: Path, *args: str) -> str:
    """Run git in ``cwd`` with a fixed identity and return stdout."""
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    result = subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()
