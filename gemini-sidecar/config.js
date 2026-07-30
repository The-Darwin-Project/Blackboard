// gemini-sidecar/config.js
// @ai-rules:
// 1. [Constraint]: Pure constants and env-derived values only. No side effects at load time.
// 2. [Pattern]: resolveTimeoutMs(role) derives a per-task CLI timeout from ROLE_TIMEOUTS.
//    There is deliberately NO module-level TIMEOUT_MS constant: ephemeral roles get their role
//    per-task via a WS message field (see ws-server.js msg.role), NOT via AGENT_ROLE, which stays
//    "" for them at process start. A load-time snapshot of AGENT_ROLE would silently pin every
//    ephemeral dispatch to ROLE_TIMEOUTS.default regardless of the role's own entry -- this was a
//    real, shipped bug (code_reviewer's 45min entry was dead) before resolveTimeoutMs existed. All
//    consumers (currently only cli-executor.js's two spawn() call sites) MUST call
//    resolveTimeoutMs(options.role || AGENT_ROLE) at the point of use, never cache the result.
// 3. [Pattern]: AGENT_CLI routes CLI selection (gemini|claude); AGENT_EFFORT_LEVEL controls Claude adaptive reasoning depth.
// 4. [Pattern]: stripAnsi cleans PTY output for Brain/LLM consumption.
// 5. [Gotcha]: stripAnsi and resolveTimeoutMs are the only non-constant exports — pure functions, safe to call anywhere.

const PORT = process.env.PORT || 9090;
const ROLE_TIMEOUTS = {
    architect: 1800000,       // 30 min
    sysadmin: 1800000,        // 30 min
    developer: 1800000,       // 30 min
    qe: 1800000,              // 30 min
    security_analyst: 1800000, // 30 min
    code_reviewer: 2700000,   // 45 min -- fans out to 6 sequential/concurrent subagent delegations before merging, unlike single-pass roles
    default: 1800000,         // 30 min
};
// explicit TIMEOUT_MS env var always wins (operator override), then the role-specific ceiling,
// then the default. See ai-rule 2 above for why this MUST be called per-task, never cached.
function resolveTimeoutMs(role) {
    return parseInt(process.env.TIMEOUT_MS) || ROLE_TIMEOUTS[role || 'default'] || ROLE_TIMEOUTS.default;
}
const FINDINGS_FRESHNESS_MS = 30000; // 30s -- findings.md older than this is stale
const DEFAULT_WORK_DIR = '/data/gitops';

// 429 retry -- sidecar-level backoff when Gemini CLI exhausts its internal retries
const CLI_429_MAX_RETRIES = 2;              // 3 total attempts (1 initial + 2 retries)
const CLI_429_INITIAL_DELAY_MS = 60000;     // 60s -- quota typically recovers in 1 min
const CLI_429_BACKOFF_MULTIPLIER = 2;       // 60s, then 120s

// CLI routing -- AGENT_CLI selects which binary to spawn (gemini or claude)
const AGENT_CLI = process.env.AGENT_CLI || 'gemini';
const AGENT_MODEL = process.env.AGENT_MODEL || process.env.GEMINI_MODEL || '';
// Agent role -- used to restrict tools (e.g., architect can't write code files)
const AGENT_ROLE = process.env.AGENT_ROLE || '';
// Claude Code effort level -- controls adaptive reasoning depth (low|medium|high|max)
const AGENT_EFFORT_LEVEL = process.env.AGENT_EFFORT_LEVEL || '';

// Ephemeral agent config -- set by Tekton TriggerTemplate for on-call agents
const EVENT_ID = process.env.EVENT_ID || '';
const EPHEMERAL = !!EVENT_ID;
const IDLE_TIMEOUT_MS = parseInt(process.env.IDLE_TIMEOUT_MS) || 3600000; // 1h default
const BRAIN_HTTP_URL = process.env.BRAIN_HTTP_URL || '';

// Strip ANSI escape codes from PTY output (colors, cursor movements, etc.)
// PTY output is raw terminal data -- Brain/LLM needs clean text.
const ANSI_RE = /\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b[()][AB012]|\x1b\[[\?]?[0-9;]*[hlm]/g;
function stripAnsi(text) { return text.replace(ANSI_RE, ''); }

module.exports = {
  PORT,
  ROLE_TIMEOUTS,
  resolveTimeoutMs,
  FINDINGS_FRESHNESS_MS,
  DEFAULT_WORK_DIR,
  AGENT_CLI,
  AGENT_MODEL,
  AGENT_ROLE,
  AGENT_EFFORT_LEVEL,
  EVENT_ID,
  EPHEMERAL,
  IDLE_TIMEOUT_MS,
  BRAIN_HTTP_URL,
  CLI_429_MAX_RETRIES,
  CLI_429_INITIAL_DELAY_MS,
  CLI_429_BACKOFF_MULTIPLIER,
  ANSI_RE,
  stripAnsi,
};
