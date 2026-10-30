---
name: stacked-mrs
description: Ship work as a stack of small, dependent merge requests. Uses glab stack on GitLab and chained pull requests on GitHub.
---

# Stacked MRs

A stack is a chain of small changes. Each change is one commit on its own branch, built
on the previous branch, and becomes one merge request that targets the previous one.
Reviewers can review and merge in order while you keep building.

## Rules for every diff

- One logical change per diff. Aim for under about 300 changed lines.
- Each diff must build and pass tests on its own.
- Commit message format: `<TICKET-KEY>: <imperative summary>`. Example:
  `PAY-124: add workspace data model`.
- MR description: what changed, the Jira link, "Part N of M", and which MR it depends on.

## Detect the host

Run `git remote get-url origin`.

- Contains `gitlab` -> use **GitLab flow**.
- Contains `github` -> use **GitHub flow**.
- Anything else -> ask the user.

## GitLab flow (`glab stack`)

Requires `glab` (`brew install glab`, then `glab auth login`). `glab stack` is marked
experimental by GitLab; tell the user once.

```bash
# 1. Start from an up-to-date base branch that exists on the remote
git checkout main && git pull
glab stack create <epic-slug>

# 2. After finishing each task: check git status, then save it as a diff
glab stack save . -m "PAY-124: add workspace data model"

# 3. Repeat step 2 per task, then push and open the MRs
glab stack sync
```

Useful commands:

| Need | Command |
| --- | --- |
| Show the stack | `glab stack list` |
| Go back to an earlier diff | `glab stack move` |
| Fix a diff after review | `glab stack amend <file>` then `glab stack sync` |
| Rebase on latest base | `glab stack sync --update-base` |

## GitHub flow (chained PRs)

```bash
git checkout -b <epic-slug>/1-data-model main
# ...commit task 1...
git push -u origin HEAD
gh pr create --base main --title "PAY-124: add workspace data model" --body "Part 1 of 3"

git checkout -b <epic-slug>/2-api <epic-slug>/1-data-model
# ...commit task 2...
git push -u origin HEAD
gh pr create --base <epic-slug>/1-data-model --title "PAY-125: add workspace API" \
  --body "Part 2 of 3. Depends on the previous PR."
```

When a parent PR is merged, retarget the next one to `main` (`gh pr edit --base main`).

## Before pushing

Show the user the stack (titles, order, base) and get a go-ahead. Pushing and opening
merge requests is visible to the team.
