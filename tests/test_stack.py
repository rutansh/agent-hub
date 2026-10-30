from pathlib import Path

import pytest
import stack
from conftest import SAMPLE_PLAN, git, write_fake_tool
from planlib import parse_plan, set_task_field

FAKE_GH = """
echo "$@" >> "$GH_LOG"
if [ "$1 $2" = "pr view" ]; then
  grep -qx "$3" "$GH_PRS" 2>/dev/null && echo "https://example.test/pr/$3" && exit 0
  exit 1
fi
if [ "$1 $2" = "pr create" ]; then
  head=""; while [ $# -gt 0 ]; do [ "$1" = "--head" ] && head="$2"; shift; done
  echo "$head" >> "$GH_PRS"; echo "https://example.test/pr/$head"
fi
"""

FAKE_GLAB = """
echo "$@" >> "$GLAB_LOG"
if [ "$1 $2" = "stack save" ]; then
  n=$(( $(cat "$GLAB_COUNT" 2>/dev/null || echo 0) + 1 )); echo $n > "$GLAB_COUNT"
  git checkout -q -b "gl-diff-$n" && git commit -q -m "$4"
fi
echo "stack ok"
"""


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A git repo on `main` with a committed plan and a local bare `origin`."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    plan_dir = root / "docs" / "epics" / "team-workspaces"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan.md").write_text(set_task_field(SAMPLE_PLAN, "T1", "Jira", "PAY-101"))
    (root / "app.py").write_text("print('hi')\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    git(root, "remote", "add", "origin", str(origin))
    git(root, "push", "-q", "origin", "main")
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def plan_path(repo: Path) -> Path:
    return repo / "docs" / "epics" / "team-workspaces" / "plan.md"


@pytest.fixture
def gh(fake_bin: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GH_LOG", str(tmp_path / "gh.log"))
    monkeypatch.setenv("GH_PRS", str(tmp_path / "gh.prs"))
    write_fake_tool(fake_bin, "gh", FAKE_GH)
    return tmp_path / "gh.log"


def test_message_uses_jira_key_or_task_id(plan_path: Path) -> None:
    tasks = parse_plan(plan_path.read_text()).tasks
    assert stack.message_text(tasks[0]) == "PAY-101: add workspace data model"
    assert stack.message_text(tasks[1]) == "T2: add workspace CLI commands"  # keeps 'CLI'


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://gitlab.com/a/b.git", "gitlab"),
        ("git@github.com:a/b.git", "github"),
        ("/tmp/somewhere", "unknown"),
    ],
)
def test_detect_host(repo: Path, url: str, expected: str) -> None:
    git(repo, "remote", "set-url", "origin", url)
    assert stack.detect_host() == expected


def test_github_flow_end_to_end(repo: Path, plan_path: Path, gh: Path) -> None:
    assert stack.main(["start", str(plan_path), "--host", "github"]) == 0

    (repo / "workspaces.py").write_text("class Workspace: ...\n")
    assert stack.main(["save", str(plan_path), "T1"]) == 0
    assert git(repo, "branch", "--show-current") == "team-workspaces/1-add-workspace-data-model"
    assert git(repo, "log", "-1", "--format=%s") == "PAY-101: add workspace data model"

    (repo / "cli_workspaces.py").write_text("def create(): ...\n")
    assert stack.main(["save", str(plan_path), "T2"]) == 0
    assert git(repo, "log", "-1", "--format=%s") == "T2: add workspace CLI commands"
    first = "team-workspaces/1-add-workspace-data-model"
    git(repo, "merge-base", "--is-ancestor", first, "HEAD")  # stacked on T1, not on main
    assert [t.status for t in parse_plan(plan_path.read_text()).tasks] == ["done", "done"]

    assert stack.main(["publish", "--confirm"]) == 0
    creates = [line for line in gh.read_text().splitlines() if line.startswith("pr create")]
    assert "--base main --head " + first in creates[0]
    assert "--base " + first + " --head team-workspaces/2-add-workspace-cli-commands" in creates[1]
    log = gh.read_text()  # bodies are multi-line, so check the whole log
    assert "Jira: PAY-101" in log and "Part 2 of 2." in log
    assert "Depends on the previous PR" in log

    assert stack.main(["publish", "--confirm"]) == 0  # idempotent: no duplicate PRs
    again = [ln for ln in gh.read_text().splitlines() if ln.startswith("pr create")]
    assert len(again) == 2


def test_publish_requires_confirm(repo: Path, plan_path: Path, gh: Path) -> None:
    stack.main(["start", str(plan_path), "--host", "github"])
    assert stack.main(["publish"]) == 1
    assert not gh.exists()


def test_save_enforces_plan_order_and_start(repo: Path, plan_path: Path) -> None:
    assert stack.main(["save", str(plan_path), "T1"]) == 1  # no stack started
    stack.main(["start", str(plan_path), "--host", "github"])
    (repo / "x.py").write_text("x = 1\n")
    assert stack.main(["save", str(plan_path), "T2"]) == 1  # T1 must come first
    assert git(repo, "branch", "--show-current") == "main"


def test_save_rejects_empty_and_oversized_diffs(repo: Path, plan_path: Path) -> None:
    stack.main(["start", str(plan_path), "--host", "github"])
    assert stack.main(["save", str(plan_path), "T1"]) == 1  # nothing changed

    (repo / "big.py").write_text("x = 1\n" * 400)
    assert stack.main(["save", str(plan_path), "T1", "--max-lines", "300"]) == 1
    assert git(repo, "diff", "--cached", "--name-only") == ""  # unstaged again
    assert "Status: done" not in plan_path.read_text().split("## T2")[0]
    assert stack.main(["save", str(plan_path), "T1", "--allow-large"]) == 0


def test_plan_docs_do_not_count_toward_the_size_limit(repo: Path, plan_path: Path) -> None:
    stack.main(["start", str(plan_path), "--host", "github"])
    (repo / "docs" / "epics" / "team-workspaces" / "design.md").write_text("line\n" * 500)
    (repo / "small.py").write_text("x = 1\n")
    assert stack.main(["save", str(plan_path), "T1", "--max-lines", "10"]) == 0


def test_start_requires_base_branch_and_known_host(repo: Path, plan_path: Path) -> None:
    git(repo, "checkout", "-q", "-b", "other")
    assert stack.main(["start", str(plan_path), "--base", "main", "--host", "github"]) == 1
    git(repo, "checkout", "-q", "main")
    assert stack.main(["start", str(plan_path)]) == 1  # origin url is a local path


def test_gitlab_flow_uses_glab_stack(
    repo: Path, plan_path: Path, fake_bin: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GLAB_LOG", str(tmp_path / "glab.log"))
    monkeypatch.setenv("GLAB_COUNT", str(tmp_path / "glab.count"))
    write_fake_tool(fake_bin, "glab", FAKE_GLAB)

    assert stack.main(["start", str(plan_path), "--host", "gitlab"]) == 0
    (repo / "workspaces.py").write_text("class Workspace: ...\n")
    assert stack.main(["save", str(plan_path), "T1"]) == 0
    assert stack.main(["publish", "--confirm"]) == 0

    calls = (tmp_path / "glab.log").read_text().splitlines()
    assert calls[0] == "stack create team-workspaces"
    assert calls[1] == "stack save -m PAY-101: add workspace data model"
    assert calls[2] == "stack sync"


def test_missing_tool_is_a_clear_error() -> None:
    with pytest.raises(stack.StackError, match="not installed"):
        stack._run(["definitely-not-a-real-tool"])
