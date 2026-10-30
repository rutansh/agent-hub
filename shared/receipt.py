"""Check receipt: proof that the tests passed on exactly this content.

`feature.py check` writes the receipt inside the git directory (never committed). `ship.py`
refuses to commit or open a merge request unless the receipt says the checks passed on the
same file contents. The fingerprint is a git tree hash of the working folder, so it is the same
before and after committing identical content, and different as soon as anything changes.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

FILE_NAME = "agent-hub-check.json"


def _git(root: Path, *args: str, env: dict[str, str] | None = None) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, env=env, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def tree_hash(root: Path) -> str | None:
    """Return the tree hash of the working folder (ignored files excluded), or None if no git.

    Uses a throwaway index, so the real staging area is never touched.
    """
    if _git(root, "rev-parse", "--git-dir") is None:
        return None
    with tempfile.TemporaryDirectory() as folder:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(folder) / "index")}
        if _git(root, "add", "-A", env=env) is None:
            return None
        return _git(root, "write-tree", env=env)


def _path(root: Path) -> Path | None:
    git_dir = _git(root, "rev-parse", "--absolute-git-dir")
    return Path(git_dir) / FILE_NAME if git_dir else None


def write_receipt(root: Path, exit_code: int) -> None:
    """Record the result of a check run. Does nothing outside a git repository."""
    path, tree = _path(root), tree_hash(root)
    if path is None or tree is None:
        return
    data = {"tree": tree, "exit_code": exit_code, "passed": exit_code == 0}
    path.write_text(json.dumps(data))


def read_receipt(root: Path) -> dict | None:
    """Return the saved receipt, or None if there is none."""
    path = _path(root)
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text())


def passed_tree(root: Path) -> str | None:
    """Return the tree hash if the checks passed on the current contents, else None."""
    saved = read_receipt(root)
    if not saved or not saved.get("passed"):
        return None
    return saved["tree"] if saved["tree"] == tree_hash(root) else None
