#!/bin/bash
# gemini-sidecar/hooks/validate-mutations.sh
# @ai-rules:
# 1. [Pattern]: Antigravity CLI PreToolUse hook — blocks shell mutations and native file mutations
#    for read-only roles, PLUS (regardless of role) enforces the out-of-band merge-approval guard.
# 2. [Contract]: Defense-in-depth flange. Primary enforcement is behavioral (agent rules).
#    No normalization pipeline — trusted Darwin prompts, not untrusted external code.
# 3. [Constraint]: Fail-CLOSED on malformed or unrecognized tool payloads (decision: "deny"),
#    and on shell tools whose command cannot be extracted (empty COMMAND).
#    Exit 0 with JSON always. Merge-approval guard fails closed when approval cannot be verified.
# 4. [Constraint]: Single-responsibility — validation ONLY.
# 5. [Gotcha]: Role from /hook-status (ephemeral) || $AGENT_ROLE (local). Ephemeral pods
#    have AGENT_ROLE="" — real role arrives via WS, exposed by /hook-status endpoint.
# 6. [Security]: Merge-approval guard is the server-side backstop for the Developer merge
#    guard (breaking prompt injection circularity, C2). Applies to EVERY role and to MCP
#    merge/write tools (classified in the node parser as MCP_GUARD=1), not just shell commands.
#    MERGE_PATTERN tolerates global options (git -C . merge, gh -R o/r pr merge).
# 7. [Contract]: PreToolUse decision enum contract: strictly `decision: "deny"` to halt tool execution.

# Read-only roles
READONLY_ROLES="explorer security_analyst architect code_reviewer reviewer"

# Shell tools supported by agents
SHELL_TOOLS="Bash shell run_in_terminal execute_command run_shell_command run_command"

# Native file mutation tools (denied for read-only roles; denied for unresolved roles)
# Note: Denylist covers known mutation tools (write_to_file, replace_file_content, edit_file);
# future iterations should migrate to an authoritative tool allowlist per role.
MUTATION_TOOLS="write_to_file replace_file_content edit_file"

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
      // MCP merge/write tools never carry a shell command, so classify them here:
      // guard=1 routes them through the merge-approval guard instead of the fast-exit allow.
      const args = d.toolCall?.args ?? d.tool_input ?? d.functionCall?.args ?? {};
      const lname = name.toLowerCase();
      const tail = lname.split(/[.:\/]/).pop();
      let guard = 0;
      if (/(^|[^a-z])merge([^a-z]|\$)/.test(tail)) guard = 1;
      if (/(^|[^a-z])(push_files|create_or_update_file|delete_file)\$/.test(tail)) {
        const br = args && typeof args === 'object' ? args.branch : undefined;
        const b = typeof br === 'string' ? br.trim().toLowerCase().replace(/^refs\/heads\//, '') : '';
        if (!b || b === 'main' || b === 'master') guard = 1;
      }
      if (/(^|[^a-z])glab_api\$/.test(tail) && /\/merge([^a-z0-9_-]|\$)/i.test(JSON.stringify(args ?? ''))) guard = 1;
      process.stdout.write(name + '|||' + guard + '|||' + cmd);
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
_REST="${PARSED#*|||}"
MCP_GUARD="${_REST%%|||*}"
COMMAND="${_REST#*|||}"

# Exact (case-insensitive) membership test; avoids treating TOOL_NAME as a grep pattern.
in_list() {
    local needle="${1,,}" item
    for item in $2; do
        [ "${item,,}" = "$needle" ] && return 0
    done
    return 1
}

IS_SHELL=0; in_list "$TOOL_NAME" "$SHELL_TOOLS" && IS_SHELL=1
IS_MUTATION=0; in_list "$TOOL_NAME" "$MUTATION_TOOLS" && IS_MUTATION=1

# Fail closed: a shell tool with no extractable command cannot be validated (unknown arg key,
# empty payload) and must not be allowed through.
if [ "$IS_SHELL" = 1 ] && [ -z "$COMMAND" ]; then
    echo '{"decision": "deny", "reason": "Shell tool call with empty or unextractable command: failing closed"}'
    exit 0
fi

# Fast exit: tools that are neither shell, native file mutation, nor an MCP merge/write tool flagged
# by the parser (MCP_GUARD=1) are allowed immediately without querying role over HTTP. This prevents
# hook timeouts and sidecar degradation from impacting read-only tools.
if [ "$IS_SHELL" = 0 ] && [ "$IS_MUTATION" = 0 ] && [ "$MCP_GUARD" != 1 ]; then
    echo '{"decision":"allow"}'
    exit 0
fi

# Resolve role: local sidecars have AGENT_ROLE set in env (no curl needed). Ephemeral agents have
# AGENT_ROLE="" at start; their role arrives via WS and is exposed by /hook-status.
ROLE="${AGENT_ROLE:-}"
if [ -z "$ROLE" ]; then
    _start=$SECONDS
    for _attempt in 1 2; do
        if ROLE_DATA=$(curl -sf --connect-timeout 0.5 --max-time 1 "http://localhost:${SIDECAR_PORT:-9090}/hook-status" 2>/dev/null); then
            ROLE=$(echo "$ROLE_DATA" | node -e "const d=require('fs').readFileSync(0,'utf8');try{const j=JSON.parse(d);process.stdout.write(j.role||'')}catch{process.stdout.write('')}" 2>/dev/null)
            break
        fi
        [ $((SECONDS - _start)) -ge 2 ] && break
        sleep 0.1
    done
fi

# Global options may sit between the binary and the subcommand (git -C . merge, gh -R o/r pr merge,
# glab -R o/r mr merge). Any dash-token with an optional value token is skipped.
_DQ='"'; _SQ="'"
_V="(${_DQ}[^${_DQ}]*${_DQ}|${_SQ}[^${_SQ}]*${_SQ}|[^[:space:];&|${_DQ}${_SQ}]+)"
_G="([[:space:]]+-[^[:space:];&|]+([[:space:]]+${_V})?)*"
_END='([^[:alnum:]_-]|$)'

# --- Merge-approval guard (applies to ALL roles, runs before the READONLY_ROLES gate) ---
NEEDS_GUARD=0
if [ "$MCP_GUARD" = 1 ]; then
    NEEDS_GUARD=1
elif [ "$IS_SHELL" = 1 ]; then
    # Flatten line continuations/newlines so a split command cannot dodge the per-line grep.
    MERGE_CMD=$(printf '%s' "$COMMAND" | sed -E ':a;N;$!ba;s#\\\n# #g' | tr '\n' ' ' | sed -E 's#[0-9]?>>?[[:space:]]*/dev/null##g')
    MERGE_PATTERN="\\bgit${_G}[[:space:]]+merge${_END}"
    MERGE_PATTERN+="|\\bgit${_G}[[:space:]]+push([[:space:]][^&|;]*)?[[:space:]:/+${_DQ}${_SQ}](main|master)([^[:alnum:]_.-]|\$)"
    MERGE_PATTERN+="|\\bgit${_G}[[:space:]]+push([[:space:]][^&|;]*)?[[:space:]](--all|--mirror)${_END}"
    MERGE_PATTERN+="|\\bgh${_G}[[:space:]]+pr${_G}[[:space:]]+merge${_END}"
    MERGE_PATTERN+="|\\bglab${_G}[[:space:]]+mr${_G}[[:space:]]+merge${_END}"
    MERGE_PATTERN+="|\\b(gh|glab)${_G}[[:space:]]+api\\b[^&|;]*/merge${_END}"
    if printf '%s\n' "$MERGE_CMD" | grep -qiE "$MERGE_PATTERN"; then
        NEEDS_GUARD=1
    fi
fi

if [ "$NEEDS_GUARD" = 1 ]; then
    APPROVAL_JSON=$(curl -sf --connect-timeout 0.5 --max-time 1 "http://localhost:${SIDECAR_PORT:-9090}/proxy/approval" 2>/dev/null)
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
    # Approved and SHA matches -- fall through to the role-based checks below.
fi

# Fail-closed: empty/unresolved role must never bypass mutation controls. Only tools that can
# mutate (shell, native file mutation, guarded MCP merge/write tools) reach this point and are denied.
if [ -z "$ROLE" ]; then
    node -e "process.stdout.write(JSON.stringify({ decision: 'deny', reason: 'Unresolved or empty agent role: failing closed' }));"
    exit 0
fi

# Fast exit: if role is an explicitly recognized mutating role, allow.
if ! echo "$READONLY_ROLES" | grep -qwi "$ROLE"; then
    echo '{"decision":"allow"}'
    exit 0
fi

# Native mutation tools check for read-only roles
if [ "$IS_MUTATION" = 1 ]; then
    echo "{\"decision\": \"deny\", \"reason\": \"Role $ROLE is read-only and not permitted to mutate files\"}"
    exit 0
fi

# MCP merge/write tools are never permitted for read-only roles, even when approved
if [ "$IS_SHELL" = 0 ]; then
    echo "{\"decision\": \"deny\", \"reason\": \"Role $ROLE is read-only and not permitted to merge or write via MCP tools\"}"
    exit 0
fi

# Strip /dev/null redirects before checking (legitimate in read commands: `grep 2>/dev/null`)
CHECK_CMD=$(printf '%s' "$COMMAND" | sed -E 's#[0-9]?>>?[[:space:]]*/dev/null##g')

# --- Mutation denylist (infrastructure + filesystem + git + network mutations) ---
BLOCK_PATTERN=''
# Git mutations
BLOCK_PATTERN+="\\bgit${_G}[[:space:]]+(commit|push|merge|rebase|reset[[:space:]]+.*--hard|tag\\b|clean\\b|apply\\b|am\\b)\\b"
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
