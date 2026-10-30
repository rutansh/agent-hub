#!/usr/bin/env bash
# Copy each shared/<module>.py into the skills that use it.
# Reason: APM installs skills independently (--skill), so each skill must carry its own copy.
# CI (validate.sh) fails if a copy differs from the file in shared/.
set -euo pipefail

cd "$(dirname "$0")/.."

# sync <module> <skill>...
sync() {
  local module=$1; shift
  for skill in "$@"; do
    mkdir -p ".apm/skills/${skill}/scripts"
    cp "shared/${module}.py" ".apm/skills/${skill}/scripts/${module}.py"
    echo "synced ${module} -> ${skill}"
  done
}

sync planlib start-task jira-tickets stacked-mrs
sync receipt implement-feature ship-small-feature
