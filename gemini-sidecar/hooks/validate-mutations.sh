#!/bin/bash
# gemini-sidecar/hooks/validate-mutations.sh
# @ai-rules:
# 1. [Pattern]: Gemini CLI BeforeTool hook — blocks shell mutations for read-only roles,
#    PLUS (regardless of role) enforces the out-of-band merge-approval guard below.
# 2. [Contract]: Defense-in-depth flange. Primary enforcement is behavioral (agent rules).
#    No normalization pipeline — trusted Darwin prompts, not untrusted external code.
#    Known accepted gap: a naive regex denylist over the raw command string cannot catch
#    indirection (eval, process substitution, variable-split commands). Closing that
#    requires a tool-allowlist / engine permissions.deny layer, out of scope here.
# 3. [Constraint]: Fail-OPEN always. Exit 0 with JSON. Never exit non-zero (blocks agent).
#    "Fail-open" is about this script's own exit code only -- the merge-approval guard
#    below still emits decision:"block" (a normal, successful JSON response) whenever
#    approval cannot be positively confirmed; it fails CLOSED on the merge decision itself.
# 4. [Constraint]: Single-responsibility — validation ONLY. Context injection stays in AfterTool.
# 5. [Gotcha]: Role from /hook-status (ephemeral) || $AGENT_ROLE (local). Ephemeral pods
#    have AGENT_ROLE="" — real role arrives via WS, exposed by /hook-status endpoint.
# 6. [Security]: Merge-approval guard is the server-side backstop for the Developer merge
#    guard described in src/agents/brain_skills/dispatch/mr-lifecycle.md (breaking prompt
#    injection circularity, C2) -- same approved/approved_mr_sha comparison as
#    src/utils/vcs_approval.py's verify_merge_guard(), reached here via the sidecar's own
#    /proxy/approval route. Applies to EVERY role (including "developer", who is
#    intentionally absent from READONLY_ROLES below since Developer must be able to git
#    push/commit) -- git mutations in general are allowed for Developer, but a merge
#    specifically now requires server-confirmed approval bound to the current commit.

# Read-only roles (Gemini-CLI and agy roles)
READONLY_ROLES="explorer security_analyst architect code_reviewer reviewer"

# Resolve role: ephemeral agents have AGENT_ROLE="" at process start (role arrives via WS,
# stored in task.role, exposed at /hook-status). Local sidecars have AGENT_ROLE set in env.
ROLE_DATA=$(curl -sf --max-time 1 "http://localhost:${SIDECAR_PORT:-9090}/hook-status" 2>/dev/null)
ROLE=$(echo "$ROLE_DATA" | node -e "const d=require('fs').readFileSync(0,'utf8');try{const j=JSON.parse(d);process.stdout.write(j.role||'')}catch{process.stdout.write('')}" 2>/dev/null)
[ -z "$ROLE" ] && ROLE="${AGENT_ROLE:-}"

# Read stdin (BeforeTool JSON payload) once, before any role-based fast exit -- the
# merge-approval guard below must run for every role, not just READONLY_ROLES.
INPUT=$(cat 2>/dev/null) || { echo '{"decision":"allow"}'; exit 0; }

# Parse tool name, command, and client flavor via node (supports Gemini BeforeTool and agy PreToolUse)
PARSED=$(printf '%s' "$INPUT" | timeout 3 node -e "
  let raw = '';
  process.stdin.on('data', (c) => { raw += c; });
  process.stdin.on('end', () => {
    try {
      const d = JSON.parse(raw);
      const isAgy = Boolean(d.toolCall) || process.env.AGENT_CLI === 'agy';
      const name = d.tool_name || d.functionCall?.name || d.toolCall?.name || '';
      const cmd = (d.tool_input && d.tool_input.command) || (d.functionCall?.args?.command) || (d.toolCall?.args?.CommandLine) || (d.toolCall?.args?.command) || '';
      process.stdout.write((isAgy ? 'agy' : 'gemini') + '|||' + name + '|||' + cmd);
    } catch { process.stdout.write('gemini||||||'); }
  });
" 2>/dev/null) || { echo '{"decision":"allow"}'; exit 0; }

CLIENT_FLAVOR="${PARSED%%|||*}"
REST="${PARSED#*|||}"
TOOL_NAME="${REST%%|||*}"
COMMAND="${REST#*|||}"
IS_AGY="no"
[ "$CLIENT_FLAVOR" = "agy" ] && IS_AGY="yes"

# run_shell_command is Gemini CLI's built-in shell tool; run_command is Antigravity (agy).
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
        # Empty GUARD_DECISION means the node subprocess itself failed (not a parse outcome,
        # since the script above always writes BLOCK||| or ALLOW|||) -- fail CLOSED here too,
        # this is the one check in this file where "unable to verify" must mean "refuse".
        if [ "$GUARD_RESULT" != "ALLOW" ]; then
            [ -z "$GUARD_REASON" ] && GUARD_REASON="Merge REFUSED: unable to verify out-of-band approval (guard check failed)."
            node -e "
              const isAgy = process.argv[2] === 'yes' || process.env.AGENT_CLI === 'agy';
              process.stdout.write(JSON.stringify({decision: isAgy ? 'deny' : 'block', reason: process.argv[1]}));
            " "$GUARD_REASON" "$IS_AGY"
            exit 0
        fi
        # Approved and SHA matches -- fall through to the role-based mutation checks below.
    fi
fi

# Fast exit: if role is not read-only, allow everything else.
# Explicit empty check first -- don't rely on grep -w's empty-pattern behavior,
# which is not consistently specified across grep implementations.
if [ -z "$ROLE" ] || ! echo "$READONLY_ROLES" | grep -qw "$ROLE"; then
    echo '{"decision":"allow"}'
    exit 0
fi

# Early exit: non-shell tools don't need mutation checking
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
# Shell redirection to a real file (CHECK_CMD already stripped >/dev/null above;
# any >/>> remaining is a write). Excludes fd duplication (e.g. 2>&1).
BLOCK_PATTERN+='|>>?[[:space:]]*[^&[:space:]]'
# Piping output into an interpreter (curl ... | bash, etc.) -- trivial RCE otherwise
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
      const isAgy = process.argv[3] === 'yes' || process.env.AGENT_CLI === 'agy';
      process.stdout.write(JSON.stringify({
        decision: isAgy ? 'deny' : 'block',
        reason: 'Read-only role (' + process.argv[1] + '): mutation blocked. Command matched denylist: ' +
                process.argv[2].slice(0, 120)
      }));
    " "$ROLE" "$LOG_CMD" "$IS_AGY"
    exit 0
fi

# Curl mutations. Method/data/upload flags are checked case-INSENSITIVELY (curl accepts
# lowercase HTTP verbs, e.g. `-X post`). -F is checked separately, case-SENSITIVE, since
# uppercase -F is form upload but lowercase -f is unrelated (fail-silently).
if printf '%s\n' "$CHECK_CMD" | grep -qiE '\bcurl\b.*((-X|--request)\s*(POST|PUT|DELETE|PATCH)|--data\b|-d(\s|\S)|--form\b|-T\b|--upload-file\b)' \
    || printf '%s\n' "$CHECK_CMD" | grep -qE '\bcurl\b.*-F\S?'; then
    LOG_CMD=$(printf '%s' "$COMMAND" | cut -c1-120)
    node -e "
      const isAgy = process.argv[3] === 'yes' || process.env.AGENT_CLI === 'agy';
      process.stdout.write(JSON.stringify({
        decision: isAgy ? 'deny' : 'block',
        reason: 'Read-only role (' + process.argv[1] + '): mutation blocked. Command matched denylist: ' +
                process.argv[2].slice(0, 120)
      }));
    " "$ROLE" "$LOG_CMD" "$IS_AGY"
    exit 0
fi

echo '{"decision":"allow"}'
exit 0
