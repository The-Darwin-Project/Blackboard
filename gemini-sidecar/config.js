// gemini-sidecar/config.js
// @ai-rules:
// 1. [Constraint]: Pure constants and env-derived values only. No side effects at load time.
// 2. [Pattern]: TIMEOUT_MS derives from AGENT_ROLE via ROLE_TIMEOUTS; PORT/TIMEOUT_MS can be overridden by env.
// 3. [Pattern]: AGENT_CLI routes CLI selection (gemini|claude); stripAnsi cleans PTY output for Brain/LLM consumption.
// 4. [Gotcha]: stripAnsi is the only non-constant export — pure function, safe to call on any string.

const PORT = process.env.PORT || 9090;
const ROLE_TIMEOUTS = {
    architect: 600000,   // 10 min
    sysadmin: 300000,    // 5 min
    developer: 900000,   // 15 min
    qe: 600000,          // 10 min
    default: 300000,     // 5 min fallback
};
const TIMEOUT_MS = parseInt(process.env.TIMEOUT_MS) || ROLE_TIMEOUTS[process.env.AGENT_ROLE || 'default'] || ROLE_TIMEOUTS.default;
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

// Strip ANSI escape codes from PTY output (colors, cursor movements, etc.)
// PTY output is raw terminal data -- Brain/LLM needs clean text.
const ANSI_RE = /\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b[()][AB012]|\x1b\[[\?]?[0-9;]*[hlm]/g;
function stripAnsi(text) { return text.replace(ANSI_RE, ''); }

module.exports = {
  PORT,
  ROLE_TIMEOUTS,
  TIMEOUT_MS,
  FINDINGS_FRESHNESS_MS,
  DEFAULT_WORK_DIR,
  AGENT_CLI,
  AGENT_MODEL,
  AGENT_ROLE,
  CLI_429_MAX_RETRIES,
  CLI_429_INITIAL_DELAY_MS,
  CLI_429_BACKOFF_MULTIPLIER,
  ANSI_RE,
  stripAnsi,
};
