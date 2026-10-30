# Contributing

Everything shared lives under `.apm/`. Teammates get it with one `apm install`.

```
.apm/
  skills/<skill-name>/SKILL.md     # a task the agent can perform
  agents/<agent-name>.agent.md     # a role the agent can take on
```

**Skill vs agent:** a *skill* is a how-to for one task. An *agent* is a role with its own
context that does a phase of work and may use skills.

## Add a skill

1. `git checkout -b feature/<skill-name>`
2. Create `.apm/skills/<skill-name>/SKILL.md`:

   ```yaml
   ---
   name: <skill-name>        # must equal the folder name
   description: <what it does and when to use it>   # ASCII only
   ---
   ```

3. Body: when to use it, numbered steps, output format, boundaries.
4. Extra files (examples, templates) go in the same folder.

## Make a skill deterministic

If a step must behave the same every time (naming, ordering, limits, approval gates,
parsing), put it in a script, not in prose:

- Put it in `.apm/skills/<skill-name>/scripts/`, in Python 3.10+ using only the standard
  library, so it runs anywhere without installs.
- Refuse unsafe actions in code (for example `--confirm` before anything visible to the
  team) and exit non-zero with a clear message.
- Print JSON for results the agent must act on.
- Have `SKILL.md` say when to run it and what each exit code means.
- Add tests in `tests/` (they stay out of installs). Use fake `acli`, `gh` and `glab`
  scripts on `PATH`; never call real services in tests.
- Code shared by several skills lives in `shared/` and is copied into each skill with
  `./scripts/sync-shared.sh`. Never edit the copies by hand (CI checks they match).

## Add an agent

1. Create `.apm/agents/<agent-name>.agent.md`:

   ```yaml
   ---
   name: <agent-name>        # must equal the file name without .agent.md
   description: <what it does and when to use it>   # ASCII only
   ---
   ```

2. Body: role in two sentences, inputs, process, boundaries, what it returns.
3. Keep it under 300 lines.

## Naming

- Lowercase letters, digits and hyphens.
- Skills: start with a verb that says the task (`implement-feature`, `triage-adverse-events`).
- Agents: a single role noun (`architect`, `planner`, `builder`).

## Check and submit

```bash
./scripts/validate.sh
uv run --no-project --with pytest pytest -q     # or: python -m pytest -q
uvx ruff check . && uvx ruff format --check .
```

Open a PR to `main`. CI runs the same checks.

## Rules

- No real patient data, credentials or proprietary documents.
- Every skill and agent states what it must not do.
- Never commit `.env` or a real token. A new tool that needs credentials gets a variable
  in `.env.example`, and the same change must be copied to
  `.apm/skills/connect-tools/env.example` (CI checks they match).
- Agents hand work to each other through files (for example `docs/epics/<slug>/plan.md`),
  not through chat history.

## Releasing

After merging, bump `version` in `apm.yml` and tag it:

```bash
git tag v0.5.0 && git push origin v0.5.0
```

Projects then upgrade by changing the ref in their `apm.yml` and running `apm install --update`.
