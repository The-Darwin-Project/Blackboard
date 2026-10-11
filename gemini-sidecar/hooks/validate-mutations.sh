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
#    guard (breaking prompt injection circularity, C2). Applies to EVERY role. Detection lives in
#    hooks/merge-guard.js (tokenizing shell analyzer + verb-based MCP classifier); this script only
#    enforces its verdict (guard=1 => approval + SHA check). Do not re-add regex detection here.
#    Read-only roles may call only allowlisted non-shell tools (readok=1 or HOOK_EXTRA_ALLOWED_TOOLS).
# 7. [Contract]: PreToolUse decision enum contract: strictly `decision: "deny"` to halt tool execution.

# Read-only roles
# Keep in sync with READ_ONLY_ROLES in ../roles.js (heuristics for other names live there).
READONLY_ROLES="explorer security_analyst architect code_reviewer reviewer"

# Shell tools supported by agents
SHELL_TOOLS="Bash shell run_in_terminal execute_command run_shell_command run_command"

# Native file mutation tools (denied for read-only roles; denied for unresolved roles)
# Note: Denylist covers known mutation tools (write_to_file, replace_file_content, multi_replace_file_content,
# edit_file; keep in sync with NATIVE_MUTATION in merge-guard.js);
# future iterations should migrate to an authoritative tool allowlist per role.
MUTATION_TOOLS="write_to_file replace_file_content multi_replace_file_content edit_file Write Edit MultiEdit NotebookEdit"

# Time budget. The agy hook timeout is 10s (cli-setup.js writeAgyHooks) and a hook that gets killed is
# treated as a non-blocking error, i.e. FAIL-OPEN. So every external call below is capped by what is left
# of HOOK_BUDGET_SEC (integer seconds, default 8 => 2s margin) and the script DENIES itself on exhaustion.
# Worst-case ladder: classify <=2s, approval fetch <=3s, git rev-parse <=1s, verdict <=1s, role lookup <=2s.
HOOK_T0=$SECONDS
HOOK_BUDGET="${HOOK_BUDGET_SEC:-8}"
# tmo <cap>: prints min(cap, seconds left); returns 1 when the budget is exhausted.
tmo() {
    local cap="$1" left=$((HOOK_BUDGET - (SECONDS - HOOK_T0)))
    [ "$left" -lt 1 ] && return 1
    [ "$left" -lt "$cap" ] && cap="$left"
    echo "$cap"
}
deny_budget() {
    echo '{"decision": "deny", "reason": "Hook time budget exhausted before the call could be validated: failing closed"}'
    exit 0
}

# Read stdin (PreToolUse JSON payload)
INPUT=$(cat 2>/dev/null)

if [ -z "$INPUT" ]; then
    echo '{"decision": "deny", "reason": "Malformed or unrecognized tool payload"}'
    exit 0
fi

# Parse + classify via merge-guard.js (tokenizing shell analyzer, MCP verb classifier).
# Output: OK|||<tool>|||<guard>|||<readok>|||<command>  (or __MALFORMED__). Missing helper/node => deny.
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARSED=$(printf '%s' "$INPUT" | timeout -k 1 2 node "$HOOK_DIR/merge-guard.js" 2>/dev/null)

if [ "$PARSED" = "__MALFORMED__" ] || [ -z "$PARSED" ] || [ "${PARSED%%|||*}" != "OK" ]; then
    echo '{"decision": "deny", "reason": "Malformed or unrecognized tool payload"}'
    exit 0
fi
PARSED="${PARSED#OK|||}"

TOOL_NAME="${PARSED%%|||*}"
_REST="${PARSED#*|||}"
NEEDS_GUARD="${_REST%%|||*}"
_REST="${_REST#*|||}"
READ_OK="${_REST%%|||*}"
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

# Fast exit: non-shell, non-mutation tools that the classifier marked read-only/comms (readok=1) and
# that cannot merge/write a default branch (guard=0) are allowed without a role lookup. This prevents
# hook timeouts and sidecar degradation from impacting read-only tools. HOOK_EXTRA_ALLOWED_TOOLS
# (space-separated, operator-set env) can add exact tool names to the read-only allowlist.
if [ "$IS_SHELL" = 0 ] && [ "$IS_MUTATION" = 0 ] && [ "$NEEDS_GUARD" != 1 ]; then
    if [ "$READ_OK" = 1 ] || in_list "$TOOL_NAME" "${HOOK_EXTRA_ALLOWED_TOOLS:-}"; then
        echo '{"decision":"allow"}'
        exit 0
    fi
fi

# Used by the read-only git denylist below: global options may sit between `git` and the subcommand
# (git -C . commit). Any dash-token with an optional value token is skipped.
_DQ='"'; _SQ="'"
_V="(${_DQ}[^${_DQ}]*${_DQ}|${_SQ}[^${_SQ}]*${_SQ}|[^[:space:];&|${_DQ}${_SQ}]+)"
_G="([[:space:]]+-[^[:space:];&|]+([[:space:]]+${_V})?)*"

# --- Merge-approval guard (applies to ALL roles, runs before the READONLY_ROLES gate) ---
# NEEDS_GUARD comes from merge-guard.js (shell: tokenized git/gh/glab/curl/wget analysis; MCP: verb-based).

if [ "$NEEDS_GUARD" = 1 ]; then
    t=$(tmo 3) || deny_budget
    APPROVAL_JSON=$(curl -sf --connect-timeout 1 --max-time "$t" "http://localhost:${SIDECAR_PORT:-9090}/proxy/approval" 2>/dev/null)
    t=$(tmo 1) || deny_budget
    LOCAL_SHA=$(timeout -k 1 "$t" git rev-parse HEAD 2>/dev/null)
    t=$(tmo 1) || deny_budget
    GUARD_DECISION=$(timeout -k 1 "$t" node "$HOOK_DIR/merge-guard.js" --verdict -- "$APPROVAL_JSON" "$LOCAL_SHA" 2>/dev/null)
    GUARD_RESULT="${GUARD_DECISION%%|||*}"
    GUARD_REASON="${GUARD_DECISION#*|||}"
    if [ "$GUARD_RESULT" != "ALLOW" ]; then
        [ -z "$GUARD_REASON" ] && GUARD_REASON="Merge REFUSED: unable to verify out-of-band approval (guard check failed)."
        # Static JSON-escape of the reason (it only ever carries our own text + SHAs) -- no node needed.
        GUARD_REASON="${GUARD_REASON//\\/\\\\}"; GUARD_REASON="${GUARD_REASON//\"/\\\"}"
        echo "{\"decision\": \"deny\", \"reason\": \"$GUARD_REASON\"}"
        exit 0
    fi
    # Approved and SHA matches -- fall through to the role-based checks below.
fi

# Resolve role: local sidecars have AGENT_ROLE set in env (no curl needed). Ephemeral agents have
# AGENT_ROLE="" at start; their role arrives via WS and is exposed by /hook-status.
ROLE="${AGENT_ROLE:-}"
if [ -z "$ROLE" ]; then
    for _attempt in 1 2; do
        t=$(tmo 1) || deny_budget
        if ROLE_DATA=$(curl -sf --connect-timeout 0.5 --max-time "$t" "http://localhost:${SIDECAR_PORT:-9090}/hook-status" 2>/dev/null); then
            t=$(tmo 1) || deny_budget
            ROLE=$(echo "$ROLE_DATA" | timeout -k 1 "$t" node -e "const d=require('fs').readFileSync(0,'utf8');try{const j=JSON.parse(d);process.stdout.write(j.role||'')}catch{process.stdout.write('')}" 2>/dev/null)
            break
        fi
        sleep 0.1
    done
fi

# Fail-closed: empty/unresolved role must never bypass mutation controls. Only tools that can
# mutate (shell, native file mutation, guarded MCP merge/write tools) reach this point and are denied.
if [ -z "$ROLE" ]; then
    node -e "process.stdout.write(JSON.stringify({ decision: 'deny', reason: 'Unresolved or empty agent role: failing closed' }));"
    exit 0
fi

# Read-only role detection. Listed read-only roles match instantly; known mutating roles skip the check; anything
# else (qa_reviewer_agent, ARCHITECT_LEAD ...) is classified by the shared name heuristics in ../roles.js (fail closed:
# a node failure counts as read-only).
is_readonly_role() {
    echo "$READONLY_ROLES" | grep -qwi -- "$1" && return 0
    in_list "$1" "developer sysadmin qe tester executor" && return 1
    local t out
    t=$(tmo 1) || return 0
    out=$(timeout -k 1 "$t" node "$HOOK_DIR/merge-guard.js" --readonly "$1" 2>/dev/null)
    [ "$out" = "0" ] && return 1
    return 0
}

# Fast exit: if role is an explicitly recognized mutating role, allow.
if ! is_readonly_role "$ROLE"; then
    echo '{"decision":"allow"}'
    exit 0
fi

# Native mutation tools check for read-only roles
if [ "$IS_MUTATION" = 1 ]; then
    echo "{\"decision\": \"deny\", \"reason\": \"Role $ROLE is read-only and not permitted to mutate files\"}"
    exit 0
fi

# Non-shell tools that reach here are not allowlisted read-only/comms tools (merge/write MCP tools,
# unknown verbs): never permitted for read-only roles, even when the merge guard approved.
if [ "$IS_SHELL" = 0 ]; then
    echo "{\"decision\": \"deny\", \"reason\": \"Role $ROLE is read-only: tool $TOOL_NAME is not on the read-only allowlist\"}"
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
    " -- "$ROLE" "$LOG_CMD"
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
    " -- "$ROLE" "$LOG_CMD"
    exit 0
fi

echo '{"decision":"allow"}'
exit 0
