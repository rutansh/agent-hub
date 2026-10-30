# Contributing a skill

This repo is a **skill collection**: every skill lives in its own folder under
`skills/` and is installable by any teammate through APM.

## Add a skill

1. Branch: `git checkout -b feature/<skill-name>`
2. Create `skills/<skill-name>/SKILL.md`
3. Frontmatter is required:

   ```yaml
   ---
   name: <skill-name>        # must exactly match the folder name
   description: <what it does and when to use it>   # ASCII characters only
   ---
   ```

4. Keep the body focused: when to use, steps, output format, guardrails.
5. Supporting files (examples, templates) go next to `SKILL.md` in the same folder.
6. Run the local check: `./scripts/validate.sh`
7. Open a PR to `main`. CI runs the same check.

## Rules

- Folder names: lowercase letters, digits, hyphens.
- No real patient data, credentials, or proprietary documents in skills.
- Skills must state their guardrails (what the agent must not do).

## Releasing

Consumers pin versions with git tags. After merging, a maintainer bumps `version`
in `apm.yml` and tags the release:

```bash
git tag v0.2.0 && git push origin v0.2.0
```
