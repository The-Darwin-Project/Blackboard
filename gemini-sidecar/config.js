// gemini-sidecar/config.js
// @ai-rules:
// 1. [Constraint]: Pure constants and env-derived values only. No side effects at load time. The single exception is
//    AGENT_CLI validation, which throws at load (fail-fast on an unsupported runtime).
// 2. [Pattern]: resolveTimeoutMs(role) derives a per-task CLI timeout from ROLE_TIMEOUTS.
//    There is deliberately NO module-level TIMEOUT_MS constant: ephemeral roles get their role
//    per-task via a WS message field (see ws-server.js msg.role), NOT via AGENT_ROLE, which stays
//    "" for them at process start. A load-time snapshot of AGENT_ROLE would silently pin every
//    ephemeral dispatch to ROLE_TIMEOUTS.default regardless of the role's own entry -- this was a
//    real, shipped bug (code_reviewer's 45min entry was dead) before resolveTimeoutMs existed. All
//    consumers (currently only cli-executor.js's two spawn() call sites) MUST call
//    resolveTimeoutMs(options.role || AGENT_ROLE) at the point of use, never cache the result.
// 3. [Pattern]: AGENT_CLI routes CLI selection (claude|agy); AGENT_EFFORT_LEVEL controls Claude adaptive reasoning depth.
// 4. [Pattern]: stripAnsi cleans PTY output for Brain/LLM consumption.
// 5. [Gotcha]: stripAnsi, resolveTimeoutMs, resolveStorageRoot and the parse* helpers are the only non-constant exports --
//    pure functions, safe to call anywhere.
// 6. [Pattern]: DEFAULT_WORK_DIR = $DEFAULT_WORK_DIR, else the role's PVC mount /data/gitops-<AGENT_ROLE>, else /data/gitops.
//    resolveStorageRoot(candidateCwd) is the SINGLE source of truth for the storage recycler's volume root
//    (cli-executor.js pre-task check + server.js periodic sweep). Never re-inline a fallback chain.
// 7. [Constraint]: Storage recycler env is validated, never trusted: watermarks need 0 < HIGH < CRITICAL <= 1 (else 0.70/0.85);
//    durations/counts use parseInt(...,10) and must be positive finite (else the default). See parseWatermarks/parsePositiveInt.

const PORT = process.env.PORT || 9090;
const ROLE_TIMEOUTS = {
    architect: 1800000,       // 30 min
    sysadmin: 1800000,        // 30 min
    developer: 1800000,       // 30 min
    qe: 1800000,              // 30 min
    security_analyst: 1800000, // 30 min
    code_reviewer: 2700000,   // 45 min -- fans out to 6 sequential/concurrent subagent delegations before merging, unlike single-pass roles
    explorer: 1800000,        // 30 min -- parity with other roles per user request
    default: 1800000,         // 30 min
};
// explicit TIMEOUT_MS env var always wins (operator override), then the role-specific ceiling,
// then the default. See ai-rule 2 above for why this MUST be called per-task, never cached.
function resolveTimeoutMs(role) {
    return parseInt(process.env.TIMEOUT_MS) || ROLE_TIMEOUTS[role || 'default'] || ROLE_TIMEOUTS.default;
}
const FINDINGS_FRESHNESS_MS = 30000; // 30s -- findings.md older than this is stale
// Agent role -- used to restrict tools (e.g., architect can't write code files)
const AGENT_ROLE = process.env.AGENT_ROLE || '';
// Persistent sidecars mount their PVC at /data/gitops-<role>; ephemeral agents (no role) keep /data/gitops.
const ROLE_MOUNT_RE = /^[a-z0-9_-]+$/i;
const DEFAULT_WORK_DIR = process.env.DEFAULT_WORK_DIR
  || (ROLE_MOUNT_RE.test(AGENT_ROLE) ? `/data/gitops-${AGENT_ROLE}` : '/data/gitops');

// 429 retry -- sidecar-level backoff when CLI exhausts its internal retries
const CLI_429_MAX_RETRIES = 2;              // 3 total attempts (1 initial + 2 retries)
const CLI_429_INITIAL_DELAY_MS = 60000;     // 60s -- quota typically recovers in 1 min
const CLI_429_BACKOFF_MULTIPLIER = 2;       // 60s, then 120s

// CLI routing -- AGENT_CLI selects which binary to spawn (claude or agy)
const SUPPORTED_AGENT_CLIS = ['claude', 'agy'];
const AGENT_CLI = process.env.AGENT_CLI || 'claude';
// Fail fast at startup on an unsupported runtime (e.g. a stale 'gemini' value in a deployment)
if (!SUPPORTED_AGENT_CLIS.includes(AGENT_CLI)) {
  throw new Error(`Unsupported AGENT_CLI: ${AGENT_CLI}. Supported runtimes: ${SUPPORTED_AGENT_CLIS.map((c) => `'${c}'`).join(', ')}`);
}
const AGY_CLI = process.env.AGY_CLI || process.env.ANTIGRAVITY_CLI || 'agy';
const AGENT_MODEL = process.env.AGENT_MODEL || (AGENT_CLI === 'agy' ? 'gemini-3.8-flash' : '');
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

// Storage Recycler configuration (VMER-2100, incident evt-44cf0bba)
const DEFAULT_HIGH_WATERMARK = 0.70;
const DEFAULT_CRITICAL_WATERMARK = 0.85;

function parsePositiveInt(raw, fallback) {
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

// Both ratios must satisfy 0 < high < critical <= 1; an invalid pair falls back to the defaults as a pair.
function parseWatermarks(highRaw, criticalRaw) {
  const parsedHigh = Number.parseFloat(highRaw);
  const parsedCritical = Number.parseFloat(criticalRaw);
  const high = Number.isFinite(parsedHigh) ? parsedHigh : DEFAULT_HIGH_WATERMARK;
  const critical = Number.isFinite(parsedCritical) ? parsedCritical : DEFAULT_CRITICAL_WATERMARK;
  if (high > 0 && high < critical && critical <= 1) return { high, critical };
  return { high: DEFAULT_HIGH_WATERMARK, critical: DEFAULT_CRITICAL_WATERMARK };
}

const _watermarks = parseWatermarks(process.env.STORAGE_HIGH_WATERMARK, process.env.STORAGE_CRITICAL_WATERMARK);
const STORAGE_HIGH_WATERMARK = _watermarks.high;                 // 70% -- start recycling
const STORAGE_CRITICAL_WATERMARK = _watermarks.critical;         // 85% -- emergency LRU prune
const STORAGE_SWEEP_INTERVAL_MS = parsePositiveInt(process.env.STORAGE_SWEEP_INTERVAL_MS, 1800000); // 30 min
const STORAGE_STALE_MS = parsePositiveInt(process.env.STORAGE_STALE_MS, 86400000);                  // 24 hours
const STORAGE_RESULTS_TTL_MS = parsePositiveInt(process.env.STORAGE_RESULTS_TTL_MS, 7200000);       // 2 hours
const STORAGE_TIER3_MIN_AGE_MS = parsePositiveInt(process.env.STORAGE_TIER3_MIN_AGE_MS, 900000);    // 15 min idle gate
const STORAGE_MAX_TIER3_DELETIONS = parsePositiveInt(process.env.STORAGE_MAX_TIER3_DELETIONS, 5);   // per sweep
const STORAGE_PRETASK_TIMEOUT_MS = parsePositiveInt(process.env.STORAGE_PRETASK_TIMEOUT_MS, 5000);  // pre-task check ceiling
const STORAGE_ACTIVITY_HEARTBEAT_MS = parsePositiveInt(process.env.STORAGE_ACTIVITY_HEARTBEAT_MS, 60000);

// Mounted volume roots a task cwd can live under (persistent sidecars + the ephemeral workspace).
const MOUNT_ROOT_RE = /^\/data\/(gitops-[A-Za-z0-9_-]+|workspace)(?=\/|$)/;

/**
 * Single source of truth for the storage recycler's volume root. Evaluated per call (env can change in tests).
 * Order: STORAGE_RECYCLER_ROOT -> DEFAULT_WORK_DIR env -> /data/gitops-<AGENT_ROLE> -> mount derived from
 * candidateCwd (/data/gitops-<role> | /data/workspace) -> DEFAULT_WORK_DIR constant.
 */
function resolveStorageRoot(candidateCwd) {
  if (process.env.STORAGE_RECYCLER_ROOT) return process.env.STORAGE_RECYCLER_ROOT;
  if (process.env.DEFAULT_WORK_DIR) return process.env.DEFAULT_WORK_DIR;
  const role = process.env.AGENT_ROLE || '';
  if (ROLE_MOUNT_RE.test(role)) return `/data/gitops-${role}`;
  if (typeof candidateCwd === 'string') {
    const m = MOUNT_ROOT_RE.exec(candidateCwd);
    if (m) return m[0];
  }
  return DEFAULT_WORK_DIR;
}

module.exports = {
  PORT,
  ROLE_TIMEOUTS,
  resolveTimeoutMs,
  FINDINGS_FRESHNESS_MS,
  DEFAULT_WORK_DIR,
  AGENT_CLI,
  AGY_CLI,
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
  parsePositiveInt,
  parseWatermarks,
  resolveStorageRoot,
  STORAGE_HIGH_WATERMARK,
  STORAGE_CRITICAL_WATERMARK,
  STORAGE_SWEEP_INTERVAL_MS,
  STORAGE_STALE_MS,
  STORAGE_RESULTS_TTL_MS,
  STORAGE_TIER3_MIN_AGE_MS,
  STORAGE_MAX_TIER3_DELETIONS,
  STORAGE_PRETASK_TIMEOUT_MS,
  STORAGE_ACTIVITY_HEARTBEAT_MS,
};
