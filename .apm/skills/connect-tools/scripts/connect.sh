#!/usr/bin/env bash
# Load credentials from .env and check the tools agents use (gh, glab, acli).
#
# Usage (run from the project root, and SOURCE it so the variables stay in your shell):
#   source <skill-dir>/scripts/connect.sh [path/to/.env]
#
# Never prints secret values. Works in bash and zsh.

_connect_env_file="${1:-.env}"

if [ ! -f "$_connect_env_file" ]; then
  echo "connect-tools: no $_connect_env_file found."
  echo "  Create it:  cp .env.example .env   then fill in your credentials."
  return 1 2>/dev/null || exit 1
fi

# Reason: zsh searches $PATH for a bare relative name, so force an explicit path.
case "$_connect_env_file" in
  */*) ;;
  *) _connect_env_file="./$_connect_env_file" ;;
esac

set -a
# shellcheck disable=SC1090
. "$_connect_env_file"
set +a

# Reason: an exported empty variable can make a tool think a blank token was supplied.
for _v in GH_TOKEN GH_HOST GITLAB_TOKEN GITLAB_HOST JIRA_SITE JIRA_EMAIL JIRA_API_TOKEN \
  JIRA_PROJECT_KEY; do
  eval "_val=\${$_v:-}"
  [ -z "$_val" ] && unset "$_v"
done

_have() { command -v "$1" >/dev/null 2>&1; }

echo "== GitHub (gh)"
if _have gh; then
  gh auth status 2>&1 | sed -n '1,4p'
else
  echo "  not installed: brew install gh"
fi

echo "== GitLab (glab)"
if _have glab; then
  glab auth status 2>&1 | sed -n '1,4p'
else
  echo "  not installed: brew install glab"
fi

echo "== Jira (acli)"
if ! _have acli; then
  echo "  not installed: see https://developer.atlassian.com/cloud/acli/guides/update-install-guide/"
elif [ -n "${JIRA_API_TOKEN:-}" ] && [ -n "${JIRA_SITE:-}" ] && [ -n "${JIRA_EMAIL:-}" ]; then
  # Reason: acli takes the token on stdin, not from an environment variable.
  printf '%s' "$JIRA_API_TOKEN" | acli jira auth login \
    --site "$JIRA_SITE" --email "$JIRA_EMAIL" --token >/dev/null 2>&1 \
    && echo "  signed in to $JIRA_SITE" \
    || echo "  login failed: check JIRA_SITE, JIRA_EMAIL and JIRA_API_TOKEN"
else
  echo "  skipped: JIRA_SITE, JIRA_EMAIL and JIRA_API_TOKEN are not all set"
fi

unset _connect_env_file _v _val
unset -f _have
