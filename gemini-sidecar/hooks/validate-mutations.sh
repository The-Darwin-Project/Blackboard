#!/bin/bash
# gemini-sidecar/hooks/validate-mutations.sh
# @ai-rules:
# 1. [Pattern]: Gemini CLI BeforeTool hook — blocks shell mutations for read-only roles.
# 2. [Contract]: Defense-in-depth flange. Primary enforcement is behavioral (agent rules).
#    No normalization pipeline — trusted Darwin prompts, not untrusted external code.
# 3. [Constraint]: Fail-OPEN always. Exit 0 with JSON. Never exit non-zero (blocks agent).
# 4. [Constraint]: Single-responsibility — validation ONLY. Context injection stays in AfterTool.
# 5. [Gotcha]: Role from /hook-status (ephemeral) || $AGENT_ROLE (local). Ephemeral pods
#    have AGENT_ROLE="" — real role arrives via WS, exposed by /hook-status endpoint.

# Read-only roles (Gemini-CLI roles only — Claude roles have their own enforcement)
READONLY_ROLES="explorer security_analyst"

# Resolve role: ephemeral agents have AGENT_ROLE="" at process start (role arrives via WS,
# stored in task.role, exposed at /hook-status). Local sidecars have AGENT_ROLE set in env.
ROLE_DATA=$(curl -sf "http://localhost:${SIDECAR_PORT:-9090}/hook-status" 2>/dev/null)
ROLE=$(echo "$ROLE_DATA" | node -e "const d=require('fs').readFileSync(0,'utf8');try{const j=JSON.parse(d);process.stdout.write(j.role||'')}catch{process.stdout.write('')}" 2>/dev/null)
[ -z "$ROLE" ] && ROLE="${AGENT_ROLE:-}"

# Fast exit: if role is not read-only, allow everything
if ! echo "$READONLY_ROLES" | grep -qw "$ROLE"; then
    echo '{"decision":"allow"}'
    exit 0
fi

# Read stdin (BeforeTool JSON payload)
INPUT=$(cat 2>/dev/null) || { echo '{"decision":"allow"}'; exit 0; }

# Parse tool name and command via node (same pattern as validate-reviewer-bash.sh)
PARSED=$(printf '%s' "$INPUT" | timeout 3 node -e "
  let raw = '';
  process.stdin.on('data', (c) => { raw += c; });
  process.stdin.on('end', () => {
    try {
      const d = JSON.parse(raw);
      const name = d.tool_name || d.functionCall?.name || '';
      const cmd = (d.tool_input && d.tool_input.command) || (d.functionCall?.args?.command) || '';
      process.stdout.write(name + '|||' + cmd);
    } catch { process.stdout.write('|||'); }
  });
" 2>/dev/null) || { echo '{"decision":"allow"}'; exit 0; }

TOOL_NAME="${PARSED%%|||*}"
COMMAND="${PARSED#*|||}"

# Early exit: non-shell tools don't need mutation checking
SHELL_TOOLS="Bash shell run_in_terminal execute_command"
if ! echo "$SHELL_TOOLS" | grep -qw "$TOOL_NAME"; then
    echo '{"decision":"allow"}'
    exit 0
fi

# Empty command = nothing to validate
[ -z "$COMMAND" ] && { echo '{"decision":"allow"}'; exit 0; }

# Strip /dev/null redirects before checking (legitimate in read commands: `grep 2>/dev/null`)
CHECK_CMD=$(printf '%s' "$COMMAND" | sed -E 's#[0-9]?>>?[[:space:]]*/dev/null##g')

# --- Mutation denylist (infrastructure + filesystem + git + network mutations) ---
BLOCK_PATTERN=''
# Git mutations
BLOCK_PATTERN+='\bgit\s+(commit|push|merge|rebase|reset\s+.*--hard|tag\b|clean\b|apply\b|am\b)\b'
# K8s/OCP mutations (with flag-gap tolerance)
BLOCK_PATTERN+='|\b(kubectl|oc)\s+(((-\S+)(\s+\S+)?\s+)*(apply|delete|patch|edit|scale|create)\b)'
# Helm mutations
BLOCK_PATTERN+='|\bhelm\s+(install|upgrade|delete|rollback|uninstall)\b'
# ArgoCD mutations
BLOCK_PATTERN+='|\bargocd\s+app\s+(sync|delete|set)\b'
# Tekton mutations
BLOCK_PATTERN+='|\btkn\s+(pipeline\s+start|taskrun\s+create|pipelinerun\s+cancel)\b'
# Kargo mutations
BLOCK_PATTERN+='|\bkargo\s+(promote|verify)\b'
# Filesystem mutations — \binstall\b intentionally blocks npm/pip install (read-only roles
# must not modify the runtime environment; legitimate package installs go through Dockerfile)
BLOCK_PATTERN+='|\b(rm|mv|chmod|chown|dd|cp|ln|install|mkdir|touch)\b'
# File write redirects (exclude /dev/null and fd duplication)
BLOCK_PATTERN+='|\btee\b'
# Package publish
BLOCK_PATTERN+='|\bnpm\s+publish\b'

# Case-insensitive check for the main denylist
if printf '%s\n' "$CHECK_CMD" | grep -qiE "$BLOCK_PATTERN"; then
    LOG_CMD=$(printf '%s' "$COMMAND" | cut -c1-120)
    node -e "process.stdout.write(JSON.stringify({
      decision: 'block',
      reason: 'Read-only role ($ROLE): mutation blocked. Command matched denylist: ' +
              process.argv[1].slice(0, 120)
    }))" "$LOG_CMD"
    exit 0
fi

# Curl mutations — case-SENSITIVE (uppercase -F is form upload, lowercase -f is fail-silently)
# Covers: -X METHOD, --request METHOD, --data/--data-*, -d/-dVALUE, -F/-FVALUE, --form
if printf '%s\n' "$CHECK_CMD" | grep -qE '\bcurl\b.*((-X|--request)\s*(POST|PUT|DELETE|PATCH)|--data\b|-d\S|-F\S?|--form\b)'; then
    LOG_CMD=$(printf '%s' "$COMMAND" | cut -c1-120)
    node -e "process.stdout.write(JSON.stringify({
      decision: 'block',
      reason: 'Read-only role ($ROLE): mutation blocked. Command matched denylist: ' +
              process.argv[1].slice(0, 120)
    }))" "$LOG_CMD"
    exit 0
fi

echo '{"decision":"allow"}'
exit 0
