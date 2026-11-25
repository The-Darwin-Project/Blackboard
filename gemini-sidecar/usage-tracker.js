// gemini-sidecar/usage-tracker.js
// @ai-rules:
// 1. [Constraint]: Pure stream token extraction & per-task/provider accumulation — no I/O, no WS, no side effects.
// 2. [Pattern]: Dedups Claude assistant updates by message.id; reconciles terminal result via max(0, total - emitted).
// 3. [Gotcha]: Never double-counts across failover spawns; each startSpawn() tracks its own emitted baseline.

const USAGE_FIELDS = [
  'input_tokens', 'output_tokens', 'cache_read_input_tokens',
  'cache_creation_input_tokens', 'cached_tokens', 'thinking_tokens',
];
const ALL_KEYS = [...USAGE_FIELDS, 'total_tokens'];
const emptyUsage = () => Object.fromEntries(ALL_KEYS.map((k) => [k, 0]));

function normalizeUsage(raw, agentCli) {
  if (!raw || typeof raw !== 'object') return null;
  const out = emptyUsage();
  for (const k of USAGE_FIELDS) { const v = Number(raw[k]); if (Number.isFinite(v) && v > 0) out[k] = v; }
  const total = Number(raw.total_tokens);
  const anth = out.cached_tokens > 0 ? 0 : out.cache_read_input_tokens + out.cache_creation_input_tokens;
  out.total_tokens = Number.isFinite(total) && total > 0
    ? total : out.input_tokens + anth + out.output_tokens + (agentCli === 'agy' ? out.thinking_tokens : 0);
  return out;
}

function diffAndAdd(next, prev, targets) {
  const delta = emptyUsage();
  let nonZero = false;
  for (const k of ALL_KEYS) {
    const d = Math.max(0, (next[k] || 0) - (prev[k] || 0));
    delta[k] = d;
    if (d > 0) nonZero = true;
  }
  if (!nonZero) return null;
  for (const t of targets) { for (const k of ALL_KEYS) t[k] += delta[k]; }
  return delta;
}

function inferProvider(agentCli, env = process.env) {
  const cli = agentCli || env?.AGENT_CLI || 'claude';
  if (cli === 'agy') return 'vertex_gemini';
  if (env?.CLAUDE_CODE_USE_VERTEX === '1') return 'vertex_claude';
  return env?.ANTHROPIC_BASE_URL ? 'enmaas' : 'vertex_claude';
}

function extractStreamUsage(line, agentCli) {
  let obj;
  try { obj = typeof line === 'string' && line ? JSON.parse(line) : null; } catch { return null; }
  if (!obj || typeof obj !== 'object') return null;
  if ((!agentCli || agentCli === 'agy') && obj.event === 'result') {
    const usage = normalizeUsage(obj.result?.usage, agentCli || 'agy');
    return usage ? { kind: 'result', messageId: null, model: obj.result?.model || null, usage } : null;
  }
  if ((!agentCli || agentCli === 'claude') && obj.type === 'assistant') {
    const usage = normalizeUsage(obj.message?.usage, agentCli);
    return usage ? { kind: 'message', messageId: obj.message?.id || null, model: obj.message?.model || null, usage } : null;
  }
  if ((!agentCli || agentCli === 'claude') && obj.type === 'result') {
    const usage = normalizeUsage(obj.usage, agentCli);
    const model = obj.modelUsage ? Object.keys(obj.modelUsage)[0] || null : null;
    return usage ? { kind: 'result', messageId: null, model, usage } : null;
  }
  return null;
}

function createTaskUsageAccumulator() {
  const totalUsage = emptyUsage(), byProvider = {};
  let lastProvider = null, lastModel = null;

  function startSpawn(cli, provider, model) {
    const prov = provider || inferProvider(cli);
    lastProvider = prov;
    if (model) lastModel = model;
    let spawnModel = model || null;
    const spawnEmitted = emptyUsage(), seenMessages = new Map();
    if (!byProvider[prov]) byProvider[prov] = emptyUsage();
    return {
      onLine(line) {
        const ext = extractStreamUsage(line, cli);
        if (!ext) return null;
        if (ext.model) { spawnModel = ext.model; lastModel = ext.model; }
        const prev = ext.kind === 'result' ? spawnEmitted : (seenMessages.get(ext.messageId) || emptyUsage());
        if (ext.kind === 'message' && ext.messageId) seenMessages.set(ext.messageId, ext.usage);
        const delta = diffAndAdd(ext.usage, prev, [spawnEmitted, totalUsage, byProvider[prov]]);
        return delta ? { cli: cli || null, provider: prov, model: spawnModel, usage: delta } : null;
      },
    };
  }

  function summary() {
    const usage_by_provider = Object.fromEntries(Object.entries(byProvider).map(([k, v]) => [k, { ...v }]));
    return { provider: lastProvider, used_model: lastModel, usage: { ...totalUsage }, usage_by_provider };
  }

  return { startSpawn, summary };
}

module.exports = { inferProvider, extractStreamUsage, createTaskUsageAccumulator };
