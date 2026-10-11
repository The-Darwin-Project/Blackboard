#!/bin/bash
# gemini-sidecar/hooks/validate-mutations.sh
# @ai-rules:
# 1. [Pattern]: Antigravity CLI PreToolUse hook — blocks shell mutations and native file mutations
#    for read-only roles, PLUS (regardless of role) enforces the out-of-band merge-approval guard.
# 2. [Contract]: Defense-in-depth flange. Primary enforcement is behavioral (agent rules).
#    No normalization pipeline — trusted Darwin prompts, not untrusted external code.
# 3. [Constraint]: Fail-CLOSED on malformed or unrecognized tool payloads (decision: "deny").
#    Exit 0 with JSON always. Merge-approval guard fails closed when approval cannot be verified.
# 4. [Constraint]: Single-responsibility — validation ONLY.
# 5. [Gotcha]: Role from /hook-status (ephemeral) || $AGENT_ROLE (local). Ephemeral pods
#    have AGENT_ROLE="" — real role arrives via WS, exposed by /hook-status endpoint.
# 6. [Security]: Merge-approval guard is the server-side backstop for the Developer merge
#    guard (breaking prompt injection circularity, C2). Applies to EVERY role.
# 7. [Contract]: PreToolUse decision enum contract: strictly `decision: "deny"` to halt tool execution.

# Read-only roles
READONLY_ROLES="explorer security_analyst architect code_reviewer reviewer"

# Resolve role: ephemeral agents have AGENT_ROLE="" at process start (role arrives via WS,
# stored in task.role, exposed at /hook-status). Local sidecars have AGENT_ROLE set in env.
ROLE_DATA=$(curl -sf --max-time 1 "http://localhost:${SIDECAR_PORT:-9090}/hook-status" 2>/dev/null)
ROLE=$(echo "$ROLE_DATA" | node -e "const d=require('fs').readFileSync(0,'utf8');try{const j=JSON.parse(d);process.stdout.write(j.role||'')}catch{process.stdout.write('')}" 2>/dev/null)
[ -z "$ROLE" ] && ROLE="${AGENT_ROLE:-}"

# Read stdin (PreToolUse JSON payload)
INPUT=$(cat 2>/dev/null)

if [ -z "$INPUT" ]; then
    echo '{"decision": "deny", "reason": "Malformed or unrecognized tool payload"}'
    exit 0
fi

# Parse tool name and command via node (Antigravity PreToolUse protocol)
PARSED=$(printf '%s' "$INPUT" | timeout 3 node -e "
  let raw = '';
  process.stdin.on('data', (c) => { raw += c; });
  process.stdin.on('end', () => {
    try {
      const d = JSON.parse(raw);
      if (!d || typeof d !== 'object' || Array.isArray(d)) {
        process.stdout.write('__MALFORMED__');
        return;
      }
      let name = d.toolCall?.name || d.tool_name || d.functionCall?.name || '';
      if (!name || typeof name !== 'string') {
        process.stdout.write('__MALFORMED__');
        return;
      }
      name = name.trim();
      const rawCmd = d.toolCall?.args?.CommandLine ?? d.toolCall?.args?.command ?? (d.tool_input && d.tool_input.command) ?? (d.functionCall?.args?.command) ?? '';
      if (rawCmd !== null && rawCmd !== undefined && typeof rawCmd !== 'string') {
        process.stdout.write('__MALFORMED__');
        return;
      }
      const cmd = (rawCmd || '').trim();
      process.stdout.write(name + '|||' + cmd);
    } catch {
      process.stdout.write('__MALFORMED__');
    }
  });
" 2>/dev/null)

if [ "$PARSED" = "__MALFORMED__" ] || [ -z "$PARSED" ]; then
    echo '{"decision": "deny", "reason": "Malformed or unrecognized tool payload"}'
    exit 0
fi

TOOL_NAME="${PARSED%%|||*}"
COMMAND="${PARSED#*|||}"

# Shell tools supported by agents
SHELL_TOOLS="Bash shell run_in_terminal execute_command run_shell_command run_command"

# --- Merge-approval guard (applies to ALL roles, runs before the READONLY_ROLES gate) ---
if echo "$SHELL_TOOLS" | grep -qw "$TOOL_NAME" && [ -n "$COMMAND" ]; then
    MERGE_CMD=$(printf '%s' "$COMMAND" | sed -E 's#[0-9]?>>?[[:space:]]*/dev/null##g')
    MERGE_PATTERN='\bgit\s+merge\b|\bgit\s+push\b[^&|;]*\bmain\b|\bgh\s+pr\s+merge\b|\bglab\s+mr\s+merge\b'
    if printf '%s\n' "$MERGE_CMD" | grep -qiE "$MERGE_PATTERN"; then
        APPROVAL_JSON=$(curl -sf --max-time 2 "http://localhost:${SIDECAR_PORT:-9090}/proxy/approval" 2>/dev/null)
        LOCAL_SHA=$(git rev-parse HEAD 2>/dev/null)
        GUARD_DECISION=$(node -e "
          let raw = process.argv[1] || '';
          let localSha = process.argv[2] || '';
          let approval = null;
          try { approval = JSON.parse(raw); } catch { approval = null; }
          if (!approval || !approval.approved) {
            process.stdout.write('BLOCK|||Merge REFUSED: event not approved by authorized maintainer (bb_get_approval/proxy/approval reports approved=false or was unreachable).');
          } else if (!approval.approved_mr_sha || !localSha || approval.approved_mr_sha !== localSha) {
            process.stdout.write('BLOCK|||Merge REFUSED: live HEAD (' + localSha + ') differs from authenticated approval SHA (' + approval.approved_mr_sha + ').');
          } else {
            process.stdout.write('ALLOW|||');
          }
        " "$APPROVAL_JSON" "$LOCAL_SHA" 2>/dev/null)
        GUARD_RESULT="${GUARD_DECISION%%|||*}"
        GUARD_REASON="${GUARD_DECISION#*|||}"
        if [ "$GUARD_RESULT" != "ALLOW" ]; then
            [ -z "$GUARD_REASON" ] && GUARD_REASON="Merge REFUSED: unable to verify out-of-band approval (guard check failed)."
            node -e "
              process.stdout.write(JSON.stringify({decision: 'deny', reason: process.argv[1]}));
            " "$GUARD_REASON"
            exit 0
        fi
        # Approved and SHA matches -- fall through to the role-based mutation checks below.
    fi
fi

# Fail-closed: empty/unresolved role must never bypass mutation controls
if [ -z "$ROLE" ]; then
    node -e "process.stdout.write(JSON.stringify({ decision: 'deny', reason: 'Unresolved or empty agent role: failing closed' }));"
    exit 0
fi

# Fast exit: if role is an explicitly recognized mutating role, allow.
if ! echo "$READONLY_ROLES" | grep -qw "$ROLE"; then
    echo '{"decision":"allow"}'
    exit 0
fi

# Native mutation tools check for read-only roles
MUTATION_TOOLS="write_to_file replace_file_content edit_file"
if echo "$MUTATION_TOOLS" | grep -qw "$TOOL_NAME"; then
    echo "{\"decision\": \"deny\", \"reason\": \"Role $ROLE is read-only and not permitted to mutate files\"}"
    exit 0
fi

# Early exit: non-shell tools don't need shell mutation checking
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
# Filesystem mutations
BLOCK_PATTERN+='|\b(rm|mv|chmod|chown|dd|cp|ln|install|mkdir|touch)\b'
# File write redirects (exclude /dev/null and fd duplication)
BLOCK_PATTERN+='|\btee\b'
# Shell redirection to a real file
BLOCK_PATTERN+='|>>?[[:space:]]*[^&[:space:]]'
# Piping output into an interpreter
BLOCK_PATTERN+='|\|\s*(sudo\s+)?(bash|sh|zsh|dash|python[0-9.]*|perl|ruby|node)\b'
# Package publish
BLOCK_PATTERN+='|\bnpm\s+publish\b'

# Credential file paths — block read access to sensitive token stores
CRED_READ_PATTERN='(/tmp/gh-token-map|/tmp/git-creds-|~/\.ssh|~/\.git-credentials|~/\.aws/credentials|~/\.netrc|/secrets/)'
BLOCK_PATTERN+="|${CRED_READ_PATTERN}"

# Case-insensitive check for the main denylist
if printf '%s\n' "$CHECK_CMD" | grep -qiE "$BLOCK_PATTERN"; then
    LOG_CMD=$(printf '%s' "$COMMAND" | cut -c1-120)
    node -e "
      process.stdout.write(JSON.stringify({
        decision: 'deny',
        reason: 'Read-only role (' + process.argv[1] + '): mutation blocked. Command matched denylist: ' +
                process.argv[2].slice(0, 120)
      }));
    " "$ROLE" "$LOG_CMD"
    exit 0
fi

# Curl mutations
if printf '%s\n' "$CHECK_CMD" | grep -qiE '\bcurl\b.*((-X|--request)\s*(POST|PUT|DELETE|PATCH)|--data\b|-d(\s|\S)|--form\b|-T\b|--upload-file\b)' \
    || printf '%s\n' "$CHECK_CMD" | grep -qE '\bcurl\b.*-F\S?'; then
    LOG_CMD=$(printf '%s' "$COMMAND" | cut -c1-120)
    node -e "
      process.stdout.write(JSON.stringify({
        decision: 'deny',
        reason: 'Read-only role (' + process.argv[1] + '): mutation blocked. Command matched denylist: ' +
                process.argv[2].slice(0, 120)
      }));
    " "$ROLE" "$LOG_CMD"
    exit 0
fi

echo '{"decision":"allow"}'
exit 0
