"""The check receipt ties 'tests passed' to the exact content that was tested."""

import json
from pathlib import Path

import feature
import pytest
import receipt
from conftest import git


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "Makefile").write_text("test:\n\t@echo ok\n")
    (tmp_path / ".gitignore").write_text("junk/\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_tree_hash_is_none_outside_a_git_repo(tmp_path: Path) -> None:
    assert receipt.tree_hash(tmp_path) is None


def test_tree_hash_matches_head_when_clean_and_changes_with_content(repo: Path) -> None:
    head_tree = git(repo, "rev-parse", "HEAD^{tree}")
    assert receipt.tree_hash(repo) == head_tree
    (repo / "new.txt").write_text("hello")  # untracked files count too
    changed = receipt.tree_hash(repo)
    assert changed != head_tree
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add file")
    assert receipt.tree_hash(repo) == changed == git(repo, "rev-parse", "HEAD^{tree}")


def test_tree_hash_ignores_ignored_files_and_leaves_the_index_alone(repo: Path) -> None:
    before = receipt.tree_hash(repo)
    (repo / "junk").mkdir()
    (repo / "junk" / "x").write_text("ignored")
    (repo / "staged.txt").write_text("s")
    git(repo, "add", "staged.txt")
    status_before = git(repo, "status", "--porcelain")
    receipt.tree_hash(repo)
    assert git(repo, "status", "--porcelain") == status_before  # nothing staged or unstaged
    (repo / "staged.txt").unlink()
    git(repo, "reset", "-q")
    assert receipt.tree_hash(repo) == before


def test_write_and_read_receipt(repo: Path) -> None:
    assert receipt.read_receipt(repo) is None
    receipt.write_receipt(repo, exit_code=0)
    saved = receipt.read_receipt(repo)
    assert saved == {"tree": receipt.tree_hash(repo), "exit_code": 0, "passed": True}
    assert receipt.passed_tree(repo) == saved["tree"]


def test_a_failed_check_is_not_a_pass(repo: Path) -> None:
    receipt.write_receipt(repo, exit_code=1)
    assert receipt.passed_tree(repo) is None


def test_a_pass_goes_stale_when_the_code_changes(repo: Path) -> None:
    receipt.write_receipt(repo, exit_code=0)
    (repo / "later.txt").write_text("edited after the check")
    assert receipt.passed_tree(repo) is None


def test_feature_check_writes_the_receipt(repo: Path) -> None:
    assert feature.main(["--root", str(repo), "check"]) == 0
    assert receipt.passed_tree(repo) == git(repo, "rev-parse", "HEAD^{tree}")
    (repo / "Makefile").write_text("test:\n\t@exit 1\n")
    assert feature.main(["--root", str(repo), "check"]) == 1
    assert (
        json.loads(
            (Path(git(repo, "rev-parse", "--absolute-git-dir")) / receipt.FILE_NAME).read_text()
        )["passed"]
        is False
    )


def test_feature_check_outside_git_still_runs(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("test:\n\t@echo ok\n")
    assert feature.main(["--root", str(tmp_path), "check"]) == 0
