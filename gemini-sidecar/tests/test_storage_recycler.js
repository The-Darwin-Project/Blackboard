// gemini-sidecar/tests/test_storage_recycler.js
// @ai-rules:
// 1. [Pattern]: Uses node:test and node:assert for test definitions.
// 2. [Pattern]: Verifies statfs calculation, error fallback, bidirectional CWD protection, sensitive denylist, mutex, and tiered recycling.

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const state = require('../state');
const {
  getStorageUsage,
  isProtectedPath,
  runStorageRecycle,
  checkAndRecycleStorage,
} = require('../storage-recycler');
const {
  STORAGE_RESULTS_TTL_MS,
  STORAGE_STALE_EVENT_TTL_MS,
} = require('../config');

test('getStorageUsage computes correct bytes and ratio from statfs', async () => {
  const result = await getStorageUsage(os.tmpdir());
  assert.strictEqual(result.ok, true);
  assert.strictEqual(typeof result.totalBytes, 'number');
  assert.strictEqual(typeof result.freeBytes, 'number');
  assert.strictEqual(typeof result.usedBytes, 'number');
  assert.strictEqual(typeof result.usedRatio, 'number');
  assert.ok(result.totalBytes > 0);
  assert.ok(result.usedRatio >= 0 && result.usedRatio <= 1);
});

test('getStorageUsage returns safe fallback without throwing when path is invalid', async () => {
  const nonExistentPath = path.join(os.tmpdir(), 'non-existent-dir-' + Date.now());
  const result = await getStorageUsage(nonExistentPath);
  assert.strictEqual(result.ok, false);
  assert.strictEqual(result.totalBytes, 0);
  assert.strictEqual(result.freeBytes, 0);
  assert.strictEqual(result.usedBytes, 0);
  assert.strictEqual(result.usedRatio, 0);
  assert.ok(result.error);
});

test('isProtectedPath guards null, undefined, jail roots, and non-jail paths', () => {
  assert.strictEqual(isProtectedPath(null), true);
  assert.strictEqual(isProtectedPath(''), true);
  assert.strictEqual(isProtectedPath(undefined), true);

  // Jail roots are explicitly protected
  assert.strictEqual(isProtectedPath('/'), true);
  assert.strictEqual(isProtectedPath('/data'), true);
  assert.strictEqual(isProtectedPath('/tmp'), true);

  // Boundary prefixes without path separator are rejected
  assert.strictEqual(isProtectedPath('/data-evil/repo'), true);
  assert.strictEqual(isProtectedPath('/tmp-hacked/payload'), true);

  // Paths outside /data and /tmp are blocked (jailed)
  assert.strictEqual(isProtectedPath('/etc/passwd'), true);
  assert.strictEqual(isProtectedPath('/var/log/syslog'), true);
  assert.strictEqual(isProtectedPath('/home/user/repo'), true);
});

test('isProtectedPath protects sensitive credentials, hook paths, and agent rules', () => {
  assert.strictEqual(isProtectedPath('/tmp/gh-token-map.json'), true);
  assert.strictEqual(isProtectedPath('/tmp/git-creds-12345'), true);
  assert.strictEqual(isProtectedPath('/tmp/.darwin-hooks-1000/strike.count'), true);
  assert.strictEqual(isProtectedPath('/tmp/agent-rules/01-rule.md'), true);
  assert.strictEqual(isProtectedPath('/var/secrets/token'), true);
  assert.strictEqual(isProtectedPath('/app/server.js'), true);
});

test('isProtectedPath enforces bidirectional active & last CWD shielding', () => {
  const activeCwd = '/data/gitops/active-repo';
  const lastCwd = '/data/gitops/recent-repo';

  // Exact match
  assert.strictEqual(isProtectedPath('/data/gitops/active-repo', activeCwd, lastCwd), true);
  assert.strictEqual(isProtectedPath('/data/gitops/recent-repo', activeCwd, lastCwd), true);

  // Child directory of active CWD
  assert.strictEqual(isProtectedPath('/data/gitops/active-repo/src/lib', activeCwd, lastCwd), true);
  assert.strictEqual(isProtectedPath('/data/gitops/recent-repo/dist/bundle.js', activeCwd, lastCwd), true);

  // Ancestor / parent directory of active CWD
  assert.strictEqual(isProtectedPath('/data/gitops', activeCwd, lastCwd), true);

  // Unrelated directory inside jail is NOT protected
  assert.strictEqual(isProtectedPath('/data/gitops/stale-unrelated-repo', activeCwd, lastCwd), false);
  assert.strictEqual(isProtectedPath('/tmp/random-scratch-file.txt', activeCwd, lastCwd), false);
});

test('runStorageRecycle Tier 1 purges stale results files older than TTL', async () => {
  const testRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'darwin-recycler-test-'));
  const resultsDir = path.join(testRoot, 'results');
  fs.mkdirSync(resultsDir, { recursive: true });

  const staleFile = path.join(resultsDir, 'stale-findings.md');
  const freshFile = path.join(resultsDir, 'fresh-findings.md');

  fs.writeFileSync(staleFile, 'old content');
  fs.writeFileSync(freshFile, 'new content');

  // Backdate stale file mtime by 3 hours (older than 2h TTL)
  const threeHoursAgo = (Date.now() - (STORAGE_RESULTS_TTL_MS + 3600000)) / 1000;
  fs.utimesSync(staleFile, threeHoursAgo, threeHoursAgo);

  try {
    const outcome = await runStorageRecycle(testRoot);
    assert.strictEqual(outcome.ok, true);
    assert.strictEqual(fs.existsSync(staleFile), false, 'stale file should have been deleted');
    assert.strictEqual(fs.existsSync(freshFile), true, 'fresh file should be preserved');
  } finally {
    fs.rmSync(testRoot, { recursive: true, force: true });
  }
});

test('runStorageRecycle Tier 2 & Tier 3 purges stale workspaces and respects protected directories under high usage', async () => {
  const testRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'darwin-recycler-tiers-'));
  const staleEventDir = path.join(testRoot, 'repo-evt-44cf0bba');
  const freshEventDir = path.join(testRoot, 'repo-evt-fresh');
  const eventsDir = path.join(testRoot, 'events');
  const activeDir = path.join(testRoot, 'active-workspace');

  fs.mkdirSync(staleEventDir, { recursive: true });
  fs.mkdirSync(freshEventDir, { recursive: true });
  fs.mkdirSync(eventsDir, { recursive: true });
  fs.mkdirSync(activeDir, { recursive: true });

  // Backdate stale event by 30 hours (> 24h TTL)
  const thirtyHoursAgo = (Date.now() - (STORAGE_STALE_EVENT_TTL_MS + 6 * 3600000)) / 1000;
  fs.utimesSync(staleEventDir, thirtyHoursAgo, thirtyHoursAgo);

  // Mock fs.promises.statfs to simulate 80% disk usage (triggers Tier 2)
  const origStatfs = fs.promises.statfs;
  fs.promises.statfs = async (p) => {
    return {
      blocks: 1000000n,
      bavail: 200000n, // 20% free -> 80% used
      bsize: 4096n,
    };
  };

  try {
    state.setCurrentTask({ eventId: 'evt-active', cwd: activeDir });
    const outcome = await runStorageRecycle(testRoot);
    assert.strictEqual(outcome.ok, true);
    assert.strictEqual(fs.existsSync(staleEventDir), false, 'stale event dir should be evicted');
    assert.strictEqual(fs.existsSync(freshEventDir), true, 'fresh event dir should be preserved');
    assert.strictEqual(fs.existsSync(eventsDir), true, 'events doc dir must be preserved');
    assert.strictEqual(fs.existsSync(activeDir), true, 'active workspace must be preserved');
  } finally {
    fs.promises.statfs = origStatfs;
    state.setCurrentTask(null);
    fs.rmSync(testRoot, { recursive: true, force: true });
  }
});

test('runStorageRecycle in-flight mutex (_isRecycling) drops concurrent runs', async () => {
  const testRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'darwin-recycler-mutex-'));
  const origStatfs = fs.promises.statfs;

  // Add delay to statfs to simulate CephFS latency
  fs.promises.statfs = async (p) => {
    await new Promise((resolve) => setTimeout(resolve, 50));
    return origStatfs(p);
  };

  try {
    const firstRun = runStorageRecycle(testRoot);
    const secondRun = runStorageRecycle(testRoot);

    const [res1, res2] = await Promise.all([firstRun, secondRun]);
    assert.strictEqual(res1.ok, true);
    assert.strictEqual(res2.skipped, true);
    assert.strictEqual(res2.reason, 'in-flight');
  } finally {
    fs.promises.statfs = origStatfs;
    fs.rmSync(testRoot, { recursive: true, force: true });
  }
});

test('checkAndRecycleStorage fast-path exits immediately when headroom is plenty', async () => {
  const result = await checkAndRecycleStorage(os.tmpdir());
  assert.ok(result.skipped);
  assert.ok(['headroom_sufficient', 'statfs_failed'].includes(result.reason));
});
