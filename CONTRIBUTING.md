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
```

Open a PR to `main`. CI runs the same check.

## Rules

- No real patient data, credentials or proprietary documents.
- Every skill and agent states what it must not do.
- Agents hand work to each other through files (for example `docs/epics/<slug>/plan.md`),
  not through chat history.

## Releasing

After merging, bump `version` in `apm.yml` and tag it:

```bash
git tag v0.3.0 && git push origin v0.3.0
```

Projects then upgrade by changing the ref in their `apm.yml` and running `apm install --update`.
