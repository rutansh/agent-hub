---
name: start-task
description: Start here for any coding task. Asks if it is a small feature or a big epic, then runs the right workflow (implement directly, or architect, plan, build with stacked MRs).
---

# Start Task

Single entry point for new work. It onboards the task, then routes it.

Deterministic steps run through `scripts/epic.py` in this skill's folder (written below as
`epic.py`; run it as `python3 <this-skill-folder>/scripts/epic.py ...`, for example
`.agents/skills/start-task/scripts/epic.py` in Cursor). Use the script's output, not your
memory, to decide what happens next. It needs only Python 3.10 or newer.

## Step 1 - Onboard

Ask the user, in this order (skip anything already answered):

1. **What do you want built?** (one or two sentences)
2. **Is this a small feature or a big epic?** Offer these definitions:
   - **Small feature**: one repo, a handful of files, fits in one merge request.
   - **Big epic**: needs design decisions, touches several areas, or needs more than
     one merge request.
3. If epic: **Which Jira project key?** (for example `PAY`) and an existing epic key, if any.
   Run `env_status.py` from the `connect-tools` skill; it reports `JIRA_PROJECT_KEY` as a
   default if set.

If the user is unsure, recommend based on the repo: if you cannot describe the change
in about five bullet points, treat it as an epic.

Use a multiple-choice question tool if your environment has one.

## Step 2a - Small feature

Follow the `implement-feature` skill. It reads the repo for context, implements the
change with tests, and optionally opens one MR.

## Step 2b - Big epic

1. **Check credentials once, up front:**
   `python3 <connect-tools>/scripts/env_status.py --require jira,gitlab` (use `github`
   instead of `gitlab` for GitHub repos). Tell the user about anything not ready, but do
   not block the design phase on it.
2. **Create or resume the epic workspace.**
   - New: `epic.py init "<epic title>"` prints the `slug` and creates
     `docs/epics/<slug>/design.md`. It fails if the epic exists.
   - Existing: `epic.py status <slug>` prints the phase and the agent to run next.
3. **Run the phase `epic.py status <slug>` reports.** Delegate to the named agent and
   pause for the user's approval between phases:

   | Phase | Agent | Output | Then run |
   | --- | --- | --- | --- |
   | design | `architect` | `design.md` | `epic.py approve <slug>` after the user approves |
   | plan | `planner` | `plan.md` and Jira tickets | `epic.py validate <slug>` |
   | build | `builder` | Code changes and a stack of MRs | `epic.py status <slug>` |

4. **Repeat** `epic.py status <slug>` after each phase until it reports `done`.

Rules for the hand-offs:

- Pass the `<slug>` to every agent. Agents communicate through the files in
  `docs/epics/<slug>/`, not through chat memory. Tell each agent which file to read.
- If your environment cannot delegate to agents, read the agent file
  (`.cursor/agents/<name>.md` or the equivalent for your tool) and follow its
  instructions yourself, in the same order.

## Step 3 - Wrap up

Report to the user: what was built, links to the Jira tickets and merge requests, and
anything left open.
