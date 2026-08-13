#!/bin/bash
# gemini-sidecar/gh-wrapper.sh
# @ai-rules:
# 1. [Pattern]: Wrapper for `gh` CLI — resolves per-org GH_TOKEN from token map before exec.
# 2. [Contract]: Installed as /usr/local/bin/gh; real binary at /usr/local/bin/.gh-real.
# 3. [Constraint]: Falls back to existing GH_TOKEN env if org lookup fails.
# 4. [Gotcha]: Must exec (not fork) so exit codes propagate correctly.

TOKEN_MAP="${GH_TOKEN_MAP_PATH:-/tmp/gh-token-map.json}"

# Try to extract org from current git remote
ORG=""
if REMOTE_URL=$(git remote get-url origin 2>/dev/null); then
  # Extract org from https://github.com/ORG/repo or git@github.com:ORG/repo
  ORG=$(printf '%s' "$REMOTE_URL" | sed -nE 's#.*github\.com[:/]([^/]+)/.*#\1#p' | tr '[:upper:]' '[:lower:]')
fi

# Look up per-org token if map exists and org resolved
if [ -n "$ORG" ] && [ -f "$TOKEN_MAP" ]; then
  RESOLVED_TOKEN=$(node -e "
    const fs = require('fs');
    try {
      const map = JSON.parse(fs.readFileSync(process.argv[1], 'utf8'));
      const entry = map[process.argv[2]] || map._default;
      if (entry && entry.token) process.stdout.write(entry.token);
    } catch {}
  " "$TOKEN_MAP" "$ORG" 2>/dev/null)
  if [ -n "$RESOLVED_TOKEN" ]; then
    export GH_TOKEN="$RESOLVED_TOKEN"
  fi
fi

exec /usr/local/bin/.gh-real "$@"
