---
name: connect-tools
description: Set up and check credentials for the tools agents use (GitHub gh, GitLab glab, Jira acli) from a git-ignored .env file. Use before creating tickets or merge requests, or when a tool says it is not signed in.
---

# Connect Tools

Credentials live in a `.env` file in the project root. The file is git-ignored and is never
read aloud, printed or committed.

## Step 1 - Make sure `.env` exists

1. Look for `.env` in the project root (check that it exists; do **not** open it).
2. If it is missing, copy the template:
   - `cp .env.example .env`, or if the project has no `.env.example`,
     copy `env.example` from this skill's folder to `.env`.
3. Tell the user which variables they need for the work at hand, and stop until they have
   filled the file in themselves:

   | Work | Variables |
   | --- | --- |
   | MRs on GitLab | `GITLAB_TOKEN`, `GITLAB_HOST` |
   | PRs on GitHub | `GH_TOKEN` |
   | Jira tickets | `JIRA_SITE`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY` |

## Step 2 - Check what is filled in

Run `python3 <this-skill-folder>/scripts/env_status.py`. It reports, per tool (GitHub,
GitLab, Jira), whether the required variables are set. It names variables only and never
prints a secret (it shows the value of `JIRA_PROJECT_KEY` only, which is not secret).

To fail early, add `--require`, for example `--require jira,gitlab`. Exit code 1 means a
required tool is not ready, and 2 means there is no `.env`. Tell the user which variables
to fill in.

## Step 3 - Load and sign in

From the project root, run the script that sits next to this file. It must be **sourced**
so the variables stay in the shell:

```bash
source <this-skill-folder>/scripts/connect.sh
```

It prints one status block per tool. Read the result and act on it:

- Signed in: continue.
- Not installed: tell the user the install command shown.
- Skipped or failed: tell the user which variables to check. Do not ask them to paste
  secrets into chat.

Run commands that need credentials (`gh`, `glab`, `acli`) in the same shell session after
sourcing.

## Rules

- Never print, echo, `cat` or quote the contents of `.env` or any token.
- Never put a token on a command line (`--token abc...`). Use the environment or stdin.
- Never commit `.env`. If `git status` shows it, stop and fix `.gitignore`.
- Never ask the user to paste a secret into the conversation.
- Use the least access needed: `repo` for GitHub, `api` and `write_repository` for GitLab.
