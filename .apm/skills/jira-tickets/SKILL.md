---
name: jira-tickets
description: Create a Jira epic and child tasks from a plan, with clear descriptions and acceptance criteria. Uses the Atlassian CLI (acli) and falls back to a markdown file.
---

# Jira Tickets

Turns a task list into Jira work items.

## Inputs

- The plan file (usually `docs/epics/<slug>/plan.md`) with a list of tasks.
- Jira project key. Ask the user if it is not provided.
- Existing epic key, if the epic already exists.

## Step 1 - Write each ticket

Every ticket needs:

- **Summary**: imperative, under 80 characters ("Add notification preferences API").
- **Description**: what and why, in two to five sentences.
- **Acceptance criteria**: a checklist a reviewer can verify.
- **Dependencies**: the tickets that must land first.

Save each description as a file (for example `docs/epics/<slug>/tickets/T1.md`) so it can
be passed with `--description-file`.

## Step 2 - Confirm before creating

Show the user the full list (summaries, order, dependencies) and wait for approval.
Creating tickets is visible to the whole team.

## Step 3 - Create them

Check that the CLI works: `acli --version`. If it is missing or not signed in, tell the
user to install it and run `acli jira auth login --web`, or use a Jira MCP server if the
environment has one.

Create the epic first (skip if it exists), then each task under it:

```bash
acli jira workitem create --project PAY --type Epic \
  --summary "Team workspaces" --description-file docs/epics/<slug>/design.md --json

acli jira workitem create --project PAY --type Task --parent PAY-123 \
  --summary "Add workspace data model" \
  --description-file docs/epics/<slug>/tickets/T1.md --json
```

Read the new key from the command output. If many tickets are needed,
`acli jira workitem create-bulk --from-json` is also available.

## Step 4 - Record the keys

Write each Jira key next to its task in `plan.md`. The `builder` agent uses these keys in
branch names, commit messages and merge request titles.

## Fallback

If Jira cannot be reached, write all tickets to `docs/epics/<slug>/tickets.md` in a format
that is easy to paste into Jira, and tell the user plainly that nothing was created.
