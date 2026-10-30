#!/usr/bin/env bash
# Copy shared/planlib.py into every skill that uses it.
# Reason: APM installs skills independently (--skill), so each skill must carry its own copy.
# CI (validate.sh) fails if a copy differs from shared/planlib.py.
set -euo pipefail

cd "$(dirname "$0")/.."

for skill in start-task jira-tickets stacked-mrs; do
  mkdir -p ".apm/skills/${skill}/scripts"
  cp shared/planlib.py ".apm/skills/${skill}/scripts/planlib.py"
  echo "synced ${skill}"
done
