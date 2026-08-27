// gemini-sidecar/catalog-skills.js
// @ai-rules:
// 1. [Pattern]: Fetches full DevOps Skills Catalog at WS connect time. index.json -> per-skill ZIP download.
// 2. [Pattern]: Extracts full ZIP contents (SKILL.md + references/ + scripts/) into ~/.gemini/skills/catalog-{slug}/.
// 3. [Pattern]: Claude symlink with exists-check for idempotency (EEXIST on second sync).
// 4. [Constraint]: Fire-and-forget from ws.on('open'). One-shot module flag prevents re-sync on WS reconnect.
// 5. [Constraint]: setImmediate yield between extractions to avoid parking the event loop (WS heartbeat).
// 6. [Pattern]: Promise.allSettled with concurrency cap for downloads. Per-slug fail-open.
// 7. [Constraint]: No SKILLS_CATALOG_SKILLS env needed — fetches entire active catalog via index.json.
// 8. [Security]: slug MUST be validated against SAFE_SLUG_RE before ANY filesystem use — path traversal via untrusted index.json skill.name.
// 9. [Gotcha]: The 30-min _refreshTimer is armed in startCatalogSync()'s .finally(), not
//    the success branch — a failed first sync must still get retried periodically, or a
//    catalog service that isn't ready yet at WS-open permanently disables sync for the pod.

const fs = require('fs');
const path = require('path');
const os = require('os');
const https = require('https');
const http = require('http');
const AdmZip = require('adm-zip');

const GEMINI_SKILLS_DIR = path.join(os.homedir(), '.gemini', 'skills');
const CLAUDE_SKILLS_DIR = path.join(os.homedir(), '.claude', 'skills');
const CONCURRENCY_CAP = 8;
const SAFE_SLUG_RE = /^[a-z0-9][a-z0-9-]*$/;
const DOWNLOAD_TIMEOUT_MS = 10000;
const REFRESH_INTERVAL_MS = 30 * 60 * 1000;

let _refreshTimer = null;

function httpGet(url, timeoutMs) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? https : http;
    const req = mod.get(url, { timeout: timeoutMs }, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        if (res.statusCode !== 200) {
          reject(new Error(`HTTP ${res.statusCode} for ${url}`));
          return;
        }
        resolve(Buffer.concat(chunks));
      });
      res.on('error', reject);
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error(`Timeout: ${url}`)); });
  });
}

async function runWithConcurrency(tasks, cap) {
  const results = [];
  let idx = 0;
  async function worker() {
    while (idx < tasks.length) {
      const i = idx++;
      results[i] = await tasks[i]().then(
        (v) => ({ status: 'fulfilled', value: v }),
        (e) => ({ status: 'rejected', reason: e }),
      );
    }
  }
  const workers = Array.from({ length: Math.min(cap, tasks.length) }, () => worker());
  await Promise.all(workers);
  return results;
}

async function syncCatalogSkills(catalogUrl) {
  if (!catalogUrl) return 0;

  const indexBuf = await httpGet(`${catalogUrl}/api/v1/skills/index.json`, DOWNLOAD_TIMEOUT_MS);
  const index = JSON.parse(indexBuf.toString('utf-8'));
  const skills = (index.skills || []).filter((s) => s.lifecycle === 'active');
  if (!skills.length) return 0;

  fs.mkdirSync(GEMINI_SKILLS_DIR, { recursive: true });
  fs.mkdirSync(CLAUDE_SKILLS_DIR, { recursive: true });

  const downloadTasks = skills.map((skill) => () => downloadAndExtract(catalogUrl, skill.name));
  const results = await runWithConcurrency(downloadTasks, CONCURRENCY_CAP);

  let extracted = 0;
  for (let i = 0; i < results.length; i++) {
    const r = results[i];
    if (r.status === 'fulfilled' && r.value) {
      extracted++;
    } else if (r.status === 'rejected') {
      const slug = skills[i] ? skills[i].name : `index-${i}`;
      console.warn(`[catalog-skills] Failed to sync skill '${slug}': ${r.reason?.message || r.reason}`);
    }
  }
  return extracted;
}

async function downloadAndExtract(catalogUrl, slug) {
  if (!SAFE_SLUG_RE.test(slug)) {
    console.warn(`[catalog-skills] Rejected unsafe slug: ${JSON.stringify(slug).slice(0, 80)}`);
    return;
  }
  const url = `${catalogUrl}/api/v1/skills/${encodeURIComponent(slug)}/download`;
  const buf = await httpGet(url, DOWNLOAD_TIMEOUT_MS);

  const zip = new AdmZip(buf);
  const destDir = path.resolve(GEMINI_SKILLS_DIR, `catalog-${slug}`);
  const tmpDir = path.resolve(GEMINI_SKILLS_DIR, `.tmp-${slug}-${Date.now()}`);
  if (!destDir.startsWith(GEMINI_SKILLS_DIR + path.sep) || !tmpDir.startsWith(GEMINI_SKILLS_DIR + path.sep)) {
    console.warn(`[catalog-skills] Path confinement failed for slug: ${JSON.stringify(slug).slice(0, 80)}`);
    return;
  }

  zip.extractAllTo(tmpDir, true);

  // ZIP root is {slug}/ — rename to catalog-{slug}
  const extracted = fs.readdirSync(tmpDir);
  const srcDir = extracted.length === 1
    ? path.join(tmpDir, extracted[0])
    : tmpDir;

  if (fs.existsSync(destDir)) fs.rmSync(destDir, { recursive: true });
  fs.renameSync(srcDir, destDir);
  if (fs.existsSync(tmpDir)) fs.rmSync(tmpDir, { recursive: true });

  // Yield to event loop between extractions (WS heartbeat protection)
  await new Promise((r) => setImmediate(r));

  // Claude symlink with exists-check (EEXIST idempotency) + path confinement
  const claudeTarget = path.resolve(CLAUDE_SKILLS_DIR, `catalog-${slug}`);
  if (!claudeTarget.startsWith(CLAUDE_SKILLS_DIR + path.sep)) return;
  if (!fs.existsSync(claudeTarget)) {
    try { fs.symlinkSync(destDir, claudeTarget); } catch {}
  }

  return true;
}

function startCatalogSync(catalogUrl, ephemeral) {
  if (!catalogUrl) return;

  const ts = () => new Date().toISOString();

  // Arm the periodic refresh regardless of whether the very first sync
  // succeeds or fails -- a transient failure (e.g. catalog service not yet
  // ready when the WS first opens) must not permanently disable sync for the
  // pod's lifetime. This is the only retry path for a failed first attempt.
  const armRefreshTimer = () => {
    if (ephemeral || _refreshTimer) return;
    _refreshTimer = setInterval(() => {
      syncCatalogSkills(catalogUrl)
        .then((c) => console.log(`[${ts()}] Catalog skills refreshed: ${c} skills`))
        .catch((e) => console.warn(`[${ts()}] Catalog skills refresh failed: ${e.message}`));
    }, REFRESH_INTERVAL_MS);
    if (_refreshTimer.unref) _refreshTimer.unref();
  };

  syncCatalogSkills(catalogUrl)
    .then((count) => {
      console.log(`[${ts()}] Catalog skills synced: ${count} skills extracted`);
    })
    .catch((e) => {
      console.warn(`[${ts()}] Catalog skills sync failed: ${e.message}`);
    })
    .finally(armRefreshTimer);
}

module.exports = { syncCatalogSkills, startCatalogSync };
