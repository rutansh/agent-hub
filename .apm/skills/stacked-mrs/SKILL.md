---
name: stacked-mrs
description: Ship plan.md tasks as a stack of small, dependent merge requests with a script that enforces the rules. Uses glab stack on GitLab and chained pull requests on GitHub.
---

# Stacked MRs

A stack is a chain of small changes. Each change is one commit on its own branch, built on
the previous one, and becomes one merge request that targets the previous one. Reviewers can
review and merge in order while you keep building.

The `scripts/stack.py` script in this skill's folder applies the same rules every time:

`python3 <this-skill-folder>/scripts/stack.py ...` (Python 3.10 or newer, standard library
only; it calls `git`, plus `glab` or `gh`).

## What the script enforces

- Tasks are saved in plan order, and only from the current stack tip.
- A save with no changes is rejected.
- Each diff is capped at 300 changed lines (excluding `docs/epics`). Over the cap, the
  script refuses and unstages; split the task or pass `--allow-large` with the user's OK.
- Commit message is always `<JIRA-KEY or task id>: <summary from the plan title>`.
- A task is marked `done` in `plan.md` only after its save succeeds.
- Nothing is pushed without `publish --confirm`.
- Re-running `publish` does not create duplicate PRs or MRs.

## Steps

1. **Detect the host:** `stack.py host` prints `gitlab` or `github` from the `origin` URL.
   If it cannot tell, ask the user and pass `--host` to `start`.
2. **Connect.** Follow the `connect-tools` skill (`GITLAB_TOKEN`/`GITLAB_HOST` or
   `GH_TOKEN`). `glab stack` is marked experimental by GitLab; tell the user once.
3. **Start from the base branch.** Check it out and run `git pull` yourself, then run
   `stack.py start docs/epics/<slug>/plan.md`. The script requires that the current branch
   is the base (pass `--base <branch>` if it is not the one you are on) and refuses to start
   a second stack until `.git/agent-hub-stack.json` is deleted.
4. **For each task, in order:** implement it (the `builder` agent does this), then run
   `stack.py save docs/epics/<slug>/plan.md T1`. Use `stack.py message <plan> T1` to preview
   the commit message.
5. **Show the stack:** `stack.py status` lists the diffs, order and base. Show it to the
   user and wait for a clear go-ahead. Opening merge requests is visible to the team.
6. **Publish:** `stack.py publish --confirm` pushes the branches and opens the MRs. On
   GitHub each PR targets the previous branch and says "Part i of N" and its Jira key.

## After review

- GitLab: `glab stack amend <file>` then `glab stack sync` to fix a diff;
  `glab stack sync --update-base` to rebase on the latest base.
- GitHub: when a parent PR is merged, retarget the next one with `gh pr edit --base main`.

## If the script refuses

Read the message and fix the cause (wrong order, wrong branch, too large, nothing to save).
Do not work around it with raw `git` or `glab` commands; that is how stacks end up
inconsistent.
