#!/bin/bash
# gemini-sidecar/hooks/validate-reviewer-bash.sh
# @ai-rules:
# 1. [Pattern]: Claude Code subagent-level PreToolUse hook (frontmatter `hooks:` field,
#    NOT the global settings.json hook registered by cli-setup.js). Wired per-subagent
#    in gemini-sidecar/agents/reviewers/*.md frontmatter, matcher "Bash".
# 2. [Constraint]: Read hook JSON from STDIN only (never argv -- avoids ARG_MAX/E2BIG).
#    Exit 2 (with stderr message) blocks the tool call; exit 0 allows it.
# 3. [Contract]: Defense-in-depth blocklist, NOT an exhaustive sandbox. This is layer 3 of 3:
#    (1) reviewer subagents' `tools:` allowlist (no Write/Edit/NotebookEdit), (2) native
#    Claude Code `permissions.deny` rules (--settings code-reviewer-permissions.json,
#    engine-enforced, shell-operator-aware), (3) this hook (custom regex, catches what the
#    denylist can't express, e.g. flag-insertion, indirection, heredoc-interpreter forms).
#    See gemini-sidecar/rules/code_reviewer.md Hard Rules for the documented residual-risk
#    trade-off (bypass risk + false-positive risk, both accepted) and the tracked sandboxing
#    follow-up (OS-level enforcement, gated on an OpenShift SCC/bubblewrap compatibility probe).
# 4. [Contract]: MUST fail CLOSED (exit 2), never fail OPEN (exit 0), on any extraction
#    failure -- missing node, parse error, or timeout. An empty command is only ever
#    "allow" when extraction explicitly succeeded and the command was genuinely empty.
# 5. [Gotcha]: Read-only commands (git diff/log/blame, rg, find, cat) must NOT match any
#    pattern below -- reviewer subagents need these for their actual job.

set -uo pipefail

INPUT=$(cat) || { echo "Blocked: failed to read hook input, failing closed" >&2; exit 2; }

if ! command -v node >/dev/null 2>&1; then
  echo "Blocked: node runtime unavailable, cannot validate command safely, failing closed" >&2
  exit 2
fi

# Input goes to node via STDIN (not argv) so a large command can never hit execve's
# ARG_MAX and silently truncate to empty (the fail-open bypass found in review).
PARSED=$(printf '%s' "$INPUT" | timeout 5 node -e "
  let raw = '';
  process.stdin.on('data', (chunk) => { raw += chunk; });
  process.stdin.on('end', () => {
    try {
      const data = JSON.parse(raw);
      process.stdout.write('OK:' + ((data.tool_input && data.tool_input.command) || ''));
    } catch (e) {
      process.stdout.write('ERR');
    }
  });
" 2>/dev/null)
NODE_STATUS=$?

# Any failure (missing node, non-zero exit, timeout kill, or an ERR sentinel from a
# JSON parse failure) fails CLOSED. Only an explicit "OK:" prefix is treated as a
# successfully-parsed command (which may legitimately be empty).
if [ "$NODE_STATUS" -ne 0 ] || [[ "$PARSED" != OK:* ]]; then
  echo "Blocked: could not parse hook input or validator timed out, failing closed" >&2
  exit 2
fi

COMMAND="${PARSED#OK:}"
[ -z "$COMMAND" ] && exit 0

# Join backslash-newline continuations the way bash itself does when it executes this
# string (deletes both characters, concatenating with no inserted space). Real
# (non-continuation) newlines are deliberately NOT collapsed yet -- the position-based
# checks below run against JOINED (still multi-line) so grep's default per-line
# behavior gives `^` a free per-line anchor, catching a substitution/ANSI-C construct
# that starts a genuine new statement on its own line, not just after a literal ;/&/|.
# Collapsing to a single line happens AFTER those checks, right before UNQUOTED.
JOINED=$(printf '%s' "$COMMAND" | sed -z 's/\\\n//g')

# ANSI-C quoting ($'...') lets bash interpret \xNN/\oNNN escapes into arbitrary literal
# bytes at parse time -- the only standard construct that can produce a command name
# (e.g. "rm") without its literal text ever appearing anywhere in $COMMAND for the
# checks below to see. Legitimate reviewer commands (git/grep/find/rg/cat) never need
# this construct; block it outright rather than trying to decode every escape form.
if printf '%s\n' "$JOINED" | grep -q "\$'"; then
  echo "Blocked: ANSI-C quoting (\$'...') is not permitted -- reviewer subagents are read-only." >&2
  exit 2
fi

# A command that STARTS a statement with a substitution ($(...), a backtick
# expression, OR a bare variable expansion ($VAR, ${VAR})) is computing its own
# command name dynamically -- this covers ANY mechanism that decodes to a command
# name at runtime (base64, printf hex-escapes, echo -e, variable-splitting across
# multiple assignments like `A=r;B=m;$A$B`, etc.), since the check is on POSITION,
# not content or how the value was constructed. A dangerous verb split across two
# separately-assigned variables never appears as a contiguous substring anywhere in
# $COMMAND for the word-boundary checks below to see -- blocking ANY variable
# reference in the command-name position closes this regardless of how many
# variables the value was assembled from. Legitimate read-only commands use
# variables and substitution as an ARGUMENT (e.g. `git log $BRANCH`,
# `git log $(cat ref.txt)`), never as the executable position. Checked at
# start-of-command AND after any command separator (;, &, |) -- not just the very
# start of the whole string -- so `true; $(echo r)m -rf /data` and
# `A=r;B=m;$A$B -rf /data` are both caught, not just position 0.
# Running this against JOINED (real newlines still present, grep's default per-line
# mode) also catches a substitution/variable starting a genuine new statement on its
# own line (`some_cmd\n$(echo r)m -rf /data`) via the same `^` anchor.
# `["']*` tolerates the construct being wrapped in quotes (`"$(...)"`), which would
# otherwise dodge a bare `^\$\(` anchor while still resolving to the same
# dynamically-computed command at execution time.
if printf '%s\n' "$JOINED" | grep -qE '(^|[;&|({])[[:space:]]*["'"'"']*(\$\(|`|\$[A-Za-z_{])'; then
  echo "Blocked: command substitution or variable expansion as the command itself is not permitted." >&2
  exit 2
fi

# NOW normalize bare (non-continuation) newlines into semicolons so multi-line
# commands retain statement boundary delimiters for statement-anchored checks.
NORMALIZED=$(printf '%s' "$JOINED" | tr '\n' ';')

# Strip quote characters while converting spaces inside quotes to underscores to preserve flag-token boundaries
UNQUOTED=$(printf '%s' "$NORMALIZED" | node -e '
  let s = "";
  process.stdin.on("data", c => s += c);
  process.stdin.on("end", () => {
    s = s.replace(/\\ /g, "_");
    s = s.replace(/\\(.)/g, "$1");
    s = s.replace(/"([^"]*)"/g, (m, g) => g.replace(/\s+/g, "_"));
    s = s.replace(/\x27([^\x27]*)\x27/g, (m, g) => g.replace(/\s+/g, "_"));
    process.stdout.write(s);
  });
' 2>/dev/null || printf '%s' "$NORMALIZED" | sed -E "s/[\"']//g")

# Strip backslash-escapes the same way: outside single quotes (already stripped above),
# bash removes a backslash and keeps the following character literally, so `r\m -rf`
# executes as `rm -rf`.
UNESCAPED=$(printf '%s' "$UNQUOTED" | sed -E 's/\\(.)/\1/g')

# Strip the common /dev/null redirect idiom before the mutation check so legitimate
# read-only commands (`grep ... 2>/dev/null`, `git log ... 2>/dev/null`) aren't
# false-positived.
CHECK_COMMAND=$(printf '%s' "$UNESCAPED" | sed -E 's#[0-9]?>>?[[:space:]]*/dev/null##g')

GIT_GAP='((-\S+)(\s+\S+)?\s+)*'
# Statement anchor including start-of-line, semicolons, pipes, subshells, backticks, and shell keywords
STATEMENT_ANCHOR='(^|[;&|({`]|(\b(then|do|else)\b))'
# Execution wrappers (sudo with flags, env, command, exec, nohup, timeout with flags or duration)
WRAPPERS='((sudo([[:space:]]+-\S+([[:space:]]+\S+)?)*|env|command|exec|nohup|timeout([[:space:]]+(-\S+|[0-9]+[a-z]?))*)[[:space:]]+)*'
GIT_BIN='([^[:space:]]*/)?git'

# End-of-flow Git mutations: commit, push, merge, send-pack, config, credential (anchored to statement position)
BLOCK_PATTERN="${STATEMENT_ANCHOR}[[:space:]]*([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*${WRAPPERS}${GIT_BIN}[[:space:]]+${GIT_GAP}(commit|push|merge|send-pack|config|credential\\b)"
# Direct credential helper execution and CLI auth dumps
BLOCK_PATTERN+="|\\b(git-credential-[a-zA-Z0-9_-]+)\\b|([^[:space:]]*/)?git-credential-darwin\\b"
BLOCK_PATTERN+="|\\b(gh|glab)([[:space:]]+-[^[:space:]]+([[:space:]]+[^[:space:]]+)?)*[[:space:]]+auth\\b"
# Git alias and config injection bypasses
BLOCK_PATTERN+='|\bgit\s+.*(-c\s*(alias|credential|core\.hooksPath|core\.sshCommand|http\.proxy|uploadpack|receivepack)\b|--config-env\b)|\b(GIT_CONFIG_[A-Za-z0-9_]*|GIT_SSH_COMMAND)\b'
# Config and hook file redirection/writes or copy/moves
BLOCK_PATTERN+='|(>>?|[|;&][[:space:]]*tee([[:space:]]+-[a-zA-Z]+)*)[[:space:]]*[^[:space:]]*(\.git/config|\.gitconfig|\.git/hooks)|\b(cp|mv|install|ln)\b.*(\.git/config|\.gitconfig|\.git/hooks)'
# Raw reverse-shell pseudo-devices
BLOCK_PATTERN+='|/dev/(tcp|udp)/'
# Cluster mutations
BLOCK_PATTERN+="|\\b(kubectl|oc)\\s+${GIT_GAP}(apply|delete|patch|edit|scale|create|run|exec|replace|rollout)\\b"
# Helm mutations
BLOCK_PATTERN+='|\bhelm\s+(install|upgrade|delete|rollback|uninstall)\b'
# ArgoCD mutations
BLOCK_PATTERN+='|\bargocd\s+app\s+(sync|delete|set)\b'
# Tekton mutations
BLOCK_PATTERN+='|\btkn\s+(pipeline\s+start|taskrun\s+create|pipelinerun\s+cancel)\b'
# Kargo mutations
BLOCK_PATTERN+='|\bkargo\s+(promote|verify)\b'
# PR / MR merge via CLI
BLOCK_PATTERN+='|\b(gh|glab)([[:space:]]+-[^[:space:]]+([[:space:]]+[^[:space:]]+)?)*[[:space:]]+(pr|mr)([[:space:]]+-[^[:space:]]+([[:space:]]+[^[:space:]]+)?)*[[:space:]]+merge\b'
# Package publish and versioning
BLOCK_PATTERN+='|\bnpm\s+(publish|version)\b'
# Symlinking sensitive directories
BLOCK_PATTERN+='|\bln\s+.*-[a-zA-Z]*s[a-zA-Z]*\s+.*(/tmp/git-creds|/secrets|/var/run/secrets|/\.ssh|/\.kube|/\.aws|/\.git-credentials)'
# Credential file paths — block read access to sensitive token stores
CRED_READ_PATTERN='(/tmp/gh[-_a-zA-Z0-9*?]*|/tmp/git-creds(\b|[-/])|/tmp/vertex-sa|/tmp/[^[:space:]]*token|/tmp/[^[:space:]]*credential|(/var)?/run/secrets|/secrets/|(/[^[:space:]]+|~|\$HOME)?/\.(ssh|git-credentials|gitconfig|aws|netrc|claude|gemini|docker|kube|config/(gh|glab-cli|gcloud|git)))'
BLOCK_PATTERN+="|${CRED_READ_PATTERN}"

if printf '%s\n' "$CHECK_COMMAND" | grep -qiE "$BLOCK_PATTERN"; then
  # Bound + redact the logged command: blocked commands can legitimately contain
  # secrets that must not reach pod logs.
  LOG_COMMAND=$(printf '%s' "$COMMAND" \
    | sed -E 's#://[^/@[:space:]]+:[^/@[:space:]]+@#://<redacted>@#g' \
    | sed -E 's/Authorization:[[:space:]]*(Bearer|Basic)[[:space:]]+[^[:space:]"'"'"']*/Authorization: \1 <redacted>/gi' \
    | sed -E 's/(^|[[:space:]])-u[[:space:]]+[^[:space:]]+:[^[:space:]]*/\1-u <redacted>/g' \
    | sed -E 's/([A-Za-z_-]*(token|password|apikey|api_key|secret)[[:space:]]*[:=])[[:space:]]*[^[:space:]]*/\1 <redacted>/gi' \
    | sed -E 's/(Authorization:[[:space:]]*token|PRIVATE-TOKEN|X-Auth-Token)[[:space:]]+[^[:space:]"'"'"']*/\1 <redacted>/gi' \
    | sed -E 's/\b(ghp_|gho_|ghu_|ghs_|glpat-|AKIA)[A-Za-z0-9_-]+/\1<redacted>/g' \
    | cut -c1-200)
  echo "Blocked: reviewer subagents are read-only. Command matched a mutation pattern: $LOG_COMMAND" >&2
  exit 2
fi

# Mutating HTTP requests via curl or wget
if printf '%s\n' "$CHECK_COMMAND" | grep -qiE '\bcurl\b.*((-X|--request)\s*(POST|PUT|DELETE|PATCH)|--data\b|-d(\s|\S)|--form\b|-T\b|--upload-file\b)' \
    || printf '%s\n' "$CHECK_COMMAND" | grep -qE '\bcurl\b.*-F\S?' \
    || printf '%s\n' "$CHECK_COMMAND" | grep -qiE '\bwget\b.*(--post-data|--post-file)\b'; then
  LOG_COMMAND=$(printf '%s' "$COMMAND" | cut -c1-200)
  echo "Blocked: reviewer subagents are read-only. Mutating HTTP requests are not permitted: $LOG_COMMAND" >&2
  exit 2
fi

exit 0
