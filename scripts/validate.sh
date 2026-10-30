#!/usr/bin/env bash
# Validate every skill and agent in the hub.
#   skills: .apm/skills/<name>/SKILL.md  (name == folder, description, ASCII frontmatter)
#   agents: .apm/agents/<name>.agent.md  (name == file stem, description, ASCII frontmatter)
set -euo pipefail

cd "$(dirname "$0")/.."
status=0

# Print frontmatter (lines between the first two '---' markers) of a file.
frontmatter_of() { awk '/^---$/{n++; next} n==1' "$1"; }

# check_file <label> <file> <expected-name>
check_file() {
  local label="$1" file="$2" expected="$3" failed=0 fm
  fm="$(frontmatter_of "$file")"

  if ! grep -qE "^name: ${expected}[[:space:]]*$" <<<"$fm"; then
    echo "FAIL $label: frontmatter 'name' must equal '${expected}'"; failed=1
  fi
  if ! grep -qE "^description: .+" <<<"$fm"; then
    echo "FAIL $label: missing frontmatter 'description'"; failed=1
  fi
  # Reason: APM requires frontmatter values to be ASCII-only
  if LC_ALL=C grep -q '[^ -~]' <<<"$fm"; then
    echo "FAIL $label: non-ASCII characters in frontmatter"; failed=1
  fi

  if [[ $failed -eq 0 ]]; then echo "OK   $label"; else status=1; fi
}

for dir in .apm/skills/*/; do
  skill="$(basename "$dir")"
  if [[ ! -f "${dir}SKILL.md" ]]; then
    echo "FAIL skill:$skill: missing SKILL.md"; status=1; continue
  fi
  check_file "skill:$skill" "${dir}SKILL.md" "$skill"
done

for file in .apm/agents/*.agent.md; do
  agent="$(basename "$file" .agent.md)"
  check_file "agent:$agent" "$file" "$agent"
done

exit $status
