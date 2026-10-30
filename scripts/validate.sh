#!/usr/bin/env bash
# Validate every skill: SKILL.md exists, name matches folder, description present, ASCII only.
set -euo pipefail

cd "$(dirname "$0")/.."
status=0

for dir in skills/*/; do
  skill="$(basename "$dir")"
  file="${dir}SKILL.md"
  failed=0

  if [[ ! -f "$file" ]]; then
    echo "FAIL $skill: missing SKILL.md"; status=1; continue
  fi

  # Frontmatter = lines between the first two '---' markers
  frontmatter="$(awk '/^---$/{n++; next} n==1' "$file")"

  if ! grep -qE "^name: ${skill}[[:space:]]*$" <<<"$frontmatter"; then
    echo "FAIL $skill: frontmatter 'name' must equal folder name"; failed=1
  fi
  if ! grep -qE "^description: .+" <<<"$frontmatter"; then
    echo "FAIL $skill: missing frontmatter 'description'"; failed=1
  fi
  # Reason: APM requires frontmatter values to be ASCII-only
  if LC_ALL=C grep -q '[^ -~]' <<<"$frontmatter"; then
    echo "FAIL $skill: non-ASCII characters in frontmatter"; failed=1
  fi

  if [[ $failed -eq 0 ]]; then echo "OK   $skill"; else status=1; fi
done

exit $status
