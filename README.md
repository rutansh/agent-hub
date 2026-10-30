# ai4pharma-skills

Central repository of shared agent skills for AI4Pharma, distributed with
[APM (Agent Package Manager)](https://microsoft.github.io/apm/).

Developers publish skills here once; teammates install them into any project with
one command.

## Available skills

| Skill | Purpose |
| --- | --- |
| `clinical-trial-summary` | Structured, plain-language brief of a clinical trial record |
| `adverse-event-triage` | Prioritize AE reports by seriousness and expectedness |
| `literature-review-brief` | Citation-backed synthesis of provided papers |

## Use these skills in a project

```bash
# Install APM once
brew install apm

# In your project: add everything
apm install rutansh/ai4pharma-skills

# ...or only what you need
apm install rutansh/ai4pharma-skills --skill clinical-trial-summary

# Pin to a release
apm install rutansh/ai4pharma-skills#v0.1.0
```

APM records the dependency in your `apm.yml`, pins the exact commit in
`apm.lock.yaml`, and deploys the skills into the agent harness directories it
detects (Cursor, Claude, Copilot, ...). Pass `--target cursor` if no harness is
detected yet.

## Contribute a skill

See [CONTRIBUTING.md](./CONTRIBUTING.md). In short: add
`skills/<name>/SKILL.md`, run `./scripts/validate.sh`, open a PR.

## Layout

```
ai4pharma-skills/
  apm.yml
  skills/
    <skill-name>/SKILL.md
  scripts/validate.sh
  .github/workflows/validate.yml
```
