---
name: jira-tickets
description: Create Jira tickets with a script, so they are always created the same way - an epic with child tasks from plan.md, or a single ticket for a small feature. Falls back to a markdown file if Jira is unavailable.
---

# Jira Tickets

Turns `docs/epics/<slug>/plan.md` into Jira work items. The `scripts/jira_sync.py` script in
this skill's folder does the work, so the result does not depend on how you phrase commands:

`python3 <this-skill-folder>/scripts/jira_sync.py ...` (Python 3.10 or newer, standard
library only; it calls the Atlassian CLI `acli`).

## What the script guarantees

- The plan is validated first. A broken plan is rejected before anything is created.
- Creation is refused without `--confirm`.
- The epic is created first, then each task under it with `--parent`, in plan order.
- Each Jira key is written back to `plan.md` right after its ticket is created, so a failed
  run resumes where it stopped and never creates duplicates.
- Ticket descriptions are generated from the plan (goal, likely files, acceptance criteria,
  dependencies) and saved to `docs/epics/<slug>/tickets/<id>.md`.

## Steps

1. **Check the plan.** Each task in `plan.md` needs a goal, acceptance criteria and a
   title under 80 characters. Ask the `planner` to fix gaps rather than editing around them.
2. **Preview:** `jira_sync.py preview docs/epics/<slug>/plan.md`. It prints every summary,
   in order, with dependencies, and creates nothing.
3. **Get approval.** Show the preview to the user. Creating tickets is visible to the whole
   team, so wait for a clear yes.
4. **Connect.** Follow the `connect-tools` skill. It loads `JIRA_SITE`, `JIRA_EMAIL` and
   `JIRA_API_TOKEN` from `.env` and signs `acli` in. Use `JIRA_PROJECT_KEY` as the default
   project if the user did not name one.
5. **Create:**
   `jira_sync.py create docs/epics/<slug>/plan.md --project PAY --confirm`.
   Add `--task-type Story` (or another type) if the project does not use `Task`.
   If the plan already has an `Epic Jira` key, the script uses it instead of creating one.
6. **Tell the user** which keys were created. The `builder` uses them in branch names,
   commits and MR titles.

## A single ticket (small features)

The `ship-small-feature` skill uses two more commands:

- `jira_sync.py check PAY-123` exits 0 if Jira knows the ticket, 1 if not, 2 if the key is
  malformed.
- `jira_sync.py ticket --project PAY --summary "..." --goal "..." --criterion "..."` builds a
  ticket with the same description layout every time (goal, acceptance criteria, optional
  details). Repeat `--criterion` for each one; `--details`, `--type` and `--parent` are
  optional. It needs a goal, at least one criterion and a summary of at most 80 characters.
  Without `--confirm` it only prints the preview and exits 2; show the preview to the user,
  then run it again with `--confirm`.

## Fallback

If `acli` is missing or Jira cannot be reached, run
`jira_sync.py export-markdown docs/epics/<slug>/plan.md`. It writes
`docs/epics/<slug>/tickets.md`, ready to paste into Jira, and marks the tasks `Jira: none`.
Tell the user plainly that no tickets were created.

## If the script fails

Read its error, fix the cause (usually sign-in, project key or an invalid plan) and run the
same command again. Do not create tickets by typing `acli` commands yourself; that is how
duplicates and inconsistent tickets happen.
