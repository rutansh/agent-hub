---
name: ship-small-feature
description: The full flow for a small feature, every time - get or create the Jira ticket, implement, test, then raise the merge request. Scripts enforce the order, so no step can be skipped.
---

# Ship Small Feature

Use for any change that fits in one merge request. The order is always the same:

1. **Ticket** - use the user's Jira ticket, or create one with a description and details.
2. **Implement** - on a branch named after the ticket.
3. **Test** - run the project's checks; the result is recorded.
4. **Merge request** - preview, get approval, then open it.

Two scripts do the deterministic parts (Python 3.10 or newer, standard library only). Run them
as `python3 <skill-folder>/scripts/<name>.py ...`:

- `ship.py` in this skill's folder: `branch`, `commit`, `mr`, `status`.
- `jira_sync.py` in the `jira-tickets` skill: `check`, `ticket`.
- `feature.py` in the `implement-feature` skill: `detect`, `check`.

## What the scripts refuse to do

You cannot talk your way past these; the scripts exit with code 2 and change nothing.

- Create a branch without a Jira key (`PAY-123`).
- Commit or open a merge request outside a `feature/<KEY>-...` branch.
- Commit unless `feature.py check` passed on exactly the files being committed. Edit a file
  after the check and the pass is stale: run `check` again.
- Commit a `.env` file (`.env.example` templates are fine).
- Open a merge request with uncommitted changes, with no commits, or when the committed code
  was not checked.
- Create a ticket or a merge request without `--confirm`. Without it they only preview.

Check `ship.py status` whenever you are unsure where things stand.

## Step 0 - Connect

Run `env_status.py --require jira,github` from the `connect-tools` skill (use `gitlab` for a
GitLab repo). Tell the user about anything not ready. If Jira is not ready, stop: a ticket is
required, so do not invent a key. `JIRA_PROJECT_KEY` in `.env` is the default project.

## Step 1 - The Jira ticket

Ask: **"Is there a Jira ticket for this?"**

**Yes.** Get the key and run `jira_sync.py check KEY`.

| Exit code | Meaning | What you do |
| --- | --- | --- |
| 0 | Jira knows the ticket | continue to step 2 |
| 1 | Jira cannot find it | ask the user to re-check the key |
| 2 | not a key like `PAY-123` | ask again |

**No.** Create one. Draft these from the user's request, then ask only for what is missing:

- **Summary**: one line, at most 80 characters.
- **Goal**: what is wanted and why, in a sentence or two.
- **Acceptance criteria**: at least one, each one testable.
- **Details** (optional): constraints, edge cases, links.

Then:

1. Run `jira_sync.py ticket --project <KEY> --summary "..." --goal "..." --criterion "..."
   [--criterion "..."] [--details "..."]`. Without `--confirm` it only prints the preview.
2. Show the preview and wait for a clear yes. Tickets are visible to the whole team.
3. Run the same command again with `--confirm`. It prints the new key. If the project does
   not use `Task`, add `--type Story` (or the type it uses).
4. Tell the user the key.

## Step 2 - Implement

1. `ship.py branch --ticket PAY-123 --name "<short feature name>"` creates
   `feature/PAY-123-<name>` from the base branch.
2. Follow the `implement-feature` skill for the coding: understand the repo, write the test
   first, make the smallest change that meets the acceptance criteria.

## Step 3 - Test

Run `feature.py check` and read the exit code:

| Exit code | Meaning | What you do |
| --- | --- | --- |
| 0 | tests ran and every detected check passed | continue |
| 1 | a check failed (see `output_tail`) | fix it, run `check` again |
| 4 | tests could not be run | tell the user exactly why; never say tests passed |

Then commit: `ship.py commit --summary "<what changed>"`. The message becomes
`PAY-123: <what changed>`. It needs the passing check from just now.

## Step 4 - Merge request

1. `ship.py mr` prints the preview (title, base, branch, description) and exits 2. Nothing
   is pushed.
2. Show it to the user and wait for approval.
3. `ship.py mr --confirm` pushes the branch and opens the pull request (GitHub) or merge
   request (GitLab). If one is already open for the branch, it returns that one.
4. Report the ticket key, the merge request link, and the check results.

## If a script refuses

Read the message after `refused:`; it says which rule applies. Do the missing step. Do not
work around a refusal with raw `git commit`, `git push`, `gh` or `glab`: the merge request
step checks that the committed code was tested, and it will refuse that too.
