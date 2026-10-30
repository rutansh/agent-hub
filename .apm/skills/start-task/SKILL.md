---
name: start-task
description: Start here for any coding task. Asks if it is a small feature or a big epic, then runs the right workflow (implement directly, or architect, plan, build with stacked MRs).
---

# Start Task

Single entry point for new work. It onboards the task, then routes it.

## Step 1 - Onboard

Ask the user, in this order (skip anything already answered):

1. **What do you want built?** (one or two sentences)
2. **Is this a small feature or a big epic?** Offer these definitions:
   - **Small feature**: one repo, a handful of files, fits in one merge request.
   - **Big epic**: needs design decisions, touches several areas, or needs more than
     one merge request.
3. If epic: **Which Jira project key?** (for example `PAY`; default to `JIRA_PROJECT_KEY`
   from `.env` if set) and an existing epic key, if any.
4. If epic: run the `connect-tools` skill now, so missing credentials show up before any
   work starts and not at the last step.

If the user is unsure, recommend based on the repo: if you cannot describe the change
in about five bullet points, treat it as an epic.

Use a multiple-choice question tool if your environment has one.

## Step 2a - Small feature

Follow the `implement-feature` skill. It reads the repo for context, implements the
change with tests, and optionally opens one MR.

## Step 2b - Big epic

Run three phases. Delegate each phase to the named agent. Pause for the user's approval
between phases.

| Phase | Agent | Output |
| --- | --- | --- |
| 1. Design | `architect` | `docs/epics/<slug>/design.md` |
| 2. Plan | `planner` | `docs/epics/<slug>/plan.md` and Jira tickets |
| 3. Build | `builder` | Code changes and a stack of merge requests |

Rules for the hand-offs:

- Choose `<slug>` once (lowercase, hyphens) and pass it to every agent.
- Agents communicate through the files above, not through chat memory. Tell each agent
  which file to read.
- If your environment cannot delegate to agents, read the agent file
  (`.cursor/agents/<name>.md` or the equivalent for your tool) and follow its
  instructions yourself, in the same order.

## Step 3 - Wrap up

Report to the user: what was built, links to the Jira tickets and merge requests, and
anything left open.
