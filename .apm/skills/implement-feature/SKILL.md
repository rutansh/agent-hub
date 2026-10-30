---
name: implement-feature
description: Write the code for a small feature using the existing code as context. Reads conventions first, writes the change with tests, and runs checks. Part of ship-small-feature.
---

# Implement Feature

Use for the coding and testing part of a change that fits in one merge request. For the
whole flow (Jira ticket, branch, commit, merge request) use `ship-small-feature`, which calls
this skill for the coding.

Deterministic steps run through `scripts/feature.py` in this skill's folder:
`python3 <this-skill-folder>/scripts/feature.py ...` (Python 3.10 or newer, standard
library only). Judgment calls (what to build, how) stay with you.

## Step 1 - Understand the request

Restate the feature in one or two sentences. If anything essential is missing (expected
behavior, inputs, edge cases), ask up to three short questions. Do not ask about things
the code already answers.

## Step 2 - Learn the repo before writing code

1. Run `feature.py detect`. It prints the language and the test and lint commands found in
   the project's files (`null` means none was found; say so to the user, do not invent one).
2. Read the README and any contributor docs or agent rules.
3. Search for the closest existing feature and read it. Match its structure, naming,
   error handling and test style.
4. List the files you expect to change.

## Step 3 - Implement

1. Work on the branch you were given (`ship-small-feature` creates it from the Jira key).
   Do not create branches yourself.
2. Write or update a test first when the project has tests. Confirm it fails.
3. Make the smallest change that satisfies the request. No unrelated refactors.
4. Follow existing conventions over personal preference.

## Step 4 - Verify

1. Run `feature.py check`. It also saves a receipt of the result for these exact files, which
   `ship.py` requires before it commits. Read the JSON and the exit code:

   | Exit code | Meaning | What you do |
   | --- | --- | --- |
   | 0 | tests ran and every detected check passed | continue |
   | 1 | a check failed (see `output_tail`) | fix it and run `check` again |
   | 4 | tests could not be run | tell the user exactly why; never say tests passed |

   A check with status `not-run` was not run. Report it as such.
2. Re-read your diff. Remove debug code and stray files.

## Step 5 - Hand off

- Summarize what changed and why, with the files touched and the `check` results.
- Do not commit, push or open a merge request yourself. `ship-small-feature` does that, with
  the Jira key and the recorded check result.
