---
name: implement-feature
description: Implement a small feature in the current repo using the existing code as context. Reads conventions first, writes the change with tests, and runs checks.
---

# Implement Feature

Use for a change that fits in one merge request.

## Step 1 - Understand the request

Restate the feature in one or two sentences. If anything essential is missing (expected
behavior, inputs, edge cases), ask up to three short questions. Do not ask about things
the code already answers.

## Step 2 - Learn the repo before writing code

1. Read the README and any contributor docs or agent rules.
2. Find how the project is laid out, built, tested and linted. Note the exact commands.
3. Search for the closest existing feature and read it. Match its structure, naming,
   error handling and test style.
4. List the files you expect to change.

## Step 3 - Implement

1. Create a branch: `feature/<short-name>` (include the ticket key if one exists).
2. Write or update a test first when the project has tests. Confirm it fails.
3. Make the smallest change that satisfies the request. No unrelated refactors.
4. Follow existing conventions over personal preference.

## Step 4 - Verify

1. Run the project's tests, linter and type checks. Fix what you broke.
2. Re-read your diff. Remove debug code and stray files.
3. If a check cannot run, say so. Never claim it passed.

## Step 5 - Hand off

- Summarize what changed and why, with the files touched and test results.
- If the user wants a merge request, use the `stacked-mrs` skill with a single diff.
- Do not push or open a merge request without the user's go-ahead.
