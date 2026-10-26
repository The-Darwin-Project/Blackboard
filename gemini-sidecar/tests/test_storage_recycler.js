// gemini-sidecar/tests/test_storage_recycler.js
// @ai-rules:
// 1. [Constraint]: Fully hermetic. Every test works in its own fs.mkdtemp root under /tmp and mocks fs.promises.statfs --
//    never point the recycler at the real /tmp or a real volume. All mocks are restored in finally/cleanup.
// 2. [Pattern]: sandbox() gives each test a fresh root + clean recycler/state; usage ratios are scripted via mockStatfs().
// 3. [Gotcha]: an aged workspace needs its CHILDREN aged too (activity = newest mtime of dir, .git bookkeeping, markers
//    and immediate children) -- use makeWorkspace(), not a bare mkdir + utimes.
// 4. [Gotcha]: STORAGE_PRETASK_TIMEOUT_MS is set BEFORE any require so config.js loads the short test value.
// 5. [Pattern]: Watermark/cap defaults asserted here (70% / 85% / 5 deletions / 15min age gate) come from config.js.

process.env.STORAGE_PRETASK_TIMEOUT_MS = '50';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');
const state = require('../state');
const config = require('../config');
const recycler = require('../storage-recycler');
const {
  getStorageUsage,
  isProtectedPath,
  runStorageRecycle,
  checkAndRecycleStorage,
  pinTaskCwd,
  unpinTaskCwd,
  collectProtectedCwds,
  getWorkspaceActivityMs,
  touchActivityMarker,
  stopStorageRecycler,
} = recycler;
const {
  STORAGE_RESULTS_TTL_MS,
  STORAGE_STALE_MS,
  STORAGE_TIER3_MIN_AGE_MS,
  STORAGE_MAX_TIER3_DELETIONS,
  STORAGE_HIGH_WATERMARK,
  STORAGE_CRITICAL_WATERMARK,
  resolveStorageRoot,
  parseWatermarks,
  parsePositiveInt,
} = config;

const HOUR = 3600000;
const CONFIG_PATH = path.resolve(__dirname, '..', 'config.js');

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function makeRoot() {
  return fs.realpathSync(fs.mkdtempSync('/tmp/darwin-recycler-'));
}

function setAge(p, ageMs) {
  const t = (Date.now() - ageMs) / 1000;
  try {
    fs.lutimesSync(p, t, t);
  } catch (_) {
    fs.utimesSync(p, t, t);
  }
}

/** Create <root>/<name> holding one file; age the file, then the dir (children count towards activity). */
function makeWorkspace(root, name, ageMs = 0) {
  const dir = path.join(root, name);
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, 'README.md');
  fs.writeFileSync(file, 'x'.repeat(64));
  if (ageMs) {
    setAge(file, ageMs);
    setAge(dir, ageMs);
  }
  return dir;
}

function mockStatfs(ratioOrFn) {
  const orig = fs.promises.statfs;
  fs.promises.statfs = async (p) => {
    const ratio = typeof ratioOrFn === 'function' ? ratioOrFn(p) : ratioOrFn;
    return { blocks: 1000000n, bavail: BigInt(Math.round((1 - ratio) * 1000000)), bsize: 4096n };
  };
  return () => { fs.promises.statfs = orig; };
}

function countEntries(root, prefix) {
  return fs.readdirSync(root).filter((n) => n.startsWith(prefix)).length;
}

/** Fresh root + clean recycler/state for one test; every registered undo runs afterwards. */
async function sandbox(fn) {
  const root = makeRoot();
  const undo = [];
  recycler.resetStorageRecycler();
  state.clearCurrentTask();
  state.clearLastTaskContext();
  try {
    await fn(root, (f) => undo.push(f));
  } finally {
    for (const f of undo.reverse()) f();
    recycler.resetStorageRecycler();
    state.clearCurrentTask();
    state.clearLastTaskContext();
    fs.rmSync(root, { recursive: true, force: true });
  }
}

async function withEnv(env, fn) {
  const saved = {};
  for (const [k, v] of Object.entries(env)) {
    saved[k] = process.env[k];
    if (v === undefined) delete process.env[k]; else process.env[k] = v;
  }
  try {
    return await fn();
  } finally {
    for (const [k, v] of Object.entries(saved)) {
      if (v === undefined) delete process.env[k]; else process.env[k] = v;
    }
  }
}

function configInChild(env, expr) {
  const childEnv = { PATH: process.env.PATH, ...env };
  return execFileSync(process.execPath, ['-e', `const c=require(${JSON.stringify(CONFIG_PATH)});console.log(JSON.stringify(${expr}))`], {
    env: childEnv,
    encoding: 'utf8',
  }).trim();
}

// ---------------------------------------------------------------------------
// config validation (R17, R23)
// ---------------------------------------------------------------------------

test('parseWatermarks accepts 0 < high < critical <= 1 and falls back to 0.70/0.85 otherwise', () => {
  assert.deepStrictEqual(parseWatermarks('0.6', '0.9'), { high: 0.6, critical: 0.9 });
  assert.deepStrictEqual(parseWatermarks('0.5', '1'), { high: 0.5, critical: 1 });
  assert.deepStrictEqual(parseWatermarks(undefined, undefined), { high: 0.7, critical: 0.85 });
  // a single valid override keeps the other default
  assert.deepStrictEqual(parseWatermarks('0.6', undefined), { high: 0.6, critical: 0.85 });
  assert.deepStrictEqual(parseWatermarks('abc', '0.9'), { high: 0.7, critical: 0.9 });

  const defaults = { high: 0.7, critical: 0.85 };
  assert.deepStrictEqual(parseWatermarks('0.9', '0.8'), defaults, 'high >= critical');
  assert.deepStrictEqual(parseWatermarks('0.8', '0.8'), defaults, 'high == critical');
  assert.deepStrictEqual(parseWatermarks('0', '0.8'), defaults, 'high == 0');
  assert.deepStrictEqual(parseWatermarks('-0.2', '0.8'), defaults, 'negative high');
  assert.deepStrictEqual(parseWatermarks('0.5', '1.5'), defaults, 'critical > 1');
  assert.deepStrictEqual(parseWatermarks('0.9', undefined), defaults, 'high above the default critical');
  assert.deepStrictEqual(parseWatermarks('Infinity', '0.9'), { high: 0.7, critical: 0.9 }, 'non-finite high -> its default');
  assert.deepStrictEqual(parseWatermarks('0.5', 'Infinity'), { high: 0.5, critical: 0.85 }, 'non-finite critical -> its default');
});

test('parsePositiveInt parses base-10 integers and rejects non-positive / non-finite input', () => {
  assert.strictEqual(parsePositiveInt('1000', 5), 1000);
  assert.strictEqual(parsePositiveInt('12.9', 5), 12);
  assert.strictEqual(parsePositiveInt('08', 5), 8);
  assert.strictEqual(parsePositiveInt(undefined, 5), 5);
  assert.strictEqual(parsePositiveInt('', 5), 5);
  assert.strictEqual(parsePositiveInt('abc', 5), 5);
  assert.strictEqual(parsePositiveInt('0', 5), 5);
  assert.strictEqual(parsePositiveInt('-3', 5), 5);
  assert.strictEqual(parsePositiveInt('Infinity', 5), 5);
});

test('config applies validated env at load: bad watermark pair and bad numbers fall back, good ones are honoured', () => {
  const bad = JSON.parse(configInChild(
    { STORAGE_HIGH_WATERMARK: '0.9', STORAGE_CRITICAL_WATERMARK: '0.5', STORAGE_MAX_TIER3_DELETIONS: 'zero', STORAGE_STALE_MS: '-1' },
    '[c.STORAGE_HIGH_WATERMARK,c.STORAGE_CRITICAL_WATERMARK,c.STORAGE_MAX_TIER3_DELETIONS,c.STORAGE_STALE_MS]'
  ));
  assert.deepStrictEqual(bad, [0.7, 0.85, 5, 86400000]);

  const good = JSON.parse(configInChild(
    { STORAGE_HIGH_WATERMARK: '0.6', STORAGE_CRITICAL_WATERMARK: '0.9', STORAGE_MAX_TIER3_DELETIONS: '2', STORAGE_PRETASK_TIMEOUT_MS: '1500' },
    '[c.STORAGE_HIGH_WATERMARK,c.STORAGE_CRITICAL_WATERMARK,c.STORAGE_MAX_TIER3_DELETIONS,c.STORAGE_PRETASK_TIMEOUT_MS]'
  ));
  assert.deepStrictEqual(good, [0.6, 0.9, 2, 1500]);

  const defaults = JSON.parse(configInChild({}, '[c.STORAGE_TIER3_MIN_AGE_MS,c.STORAGE_PRETASK_TIMEOUT_MS]'));
  assert.deepStrictEqual(defaults, [900000, 5000]);
});

test('config DEFAULT_WORK_DIR follows DEFAULT_WORK_DIR env, then the role mount, then /data/gitops', () => {
  assert.strictEqual(JSON.parse(configInChild({ AGENT_ROLE: 'developer' }, 'c.DEFAULT_WORK_DIR')), '/data/gitops-developer');
  assert.strictEqual(JSON.parse(configInChild({ AGENT_ROLE: 'qe', DEFAULT_WORK_DIR: '/data/custom' }, 'c.DEFAULT_WORK_DIR')), '/data/custom');
  assert.strictEqual(JSON.parse(configInChild({}, 'c.DEFAULT_WORK_DIR')), '/data/gitops');
  assert.strictEqual(JSON.parse(configInChild({ AGENT_ROLE: '../etc' }, 'c.DEFAULT_WORK_DIR')), '/data/gitops', 'unsafe role ignored');
});

test('resolveStorageRoot resolves STORAGE_RECYCLER_ROOT > DEFAULT_WORK_DIR > AGENT_ROLE > candidateCwd mount > default', async () => {
  const clean = { STORAGE_RECYCLER_ROOT: undefined, DEFAULT_WORK_DIR: undefined, AGENT_ROLE: undefined };

  await withEnv(clean, () => {
    assert.strictEqual(resolveStorageRoot(), config.DEFAULT_WORK_DIR);
    assert.strictEqual(resolveStorageRoot('/data/workspace/Blackboard/gemini-sidecar'), '/data/workspace');
    assert.strictEqual(resolveStorageRoot('/data/workspace'), '/data/workspace');
    assert.strictEqual(resolveStorageRoot('/data/gitops-developer/Blackboard'), '/data/gitops-developer');
    assert.strictEqual(resolveStorageRoot('/data/gitops-qe'), '/data/gitops-qe');
    // not a mount root: boundary-safe, falls back to the default
    assert.strictEqual(resolveStorageRoot('/data/workspace-evil/x'), config.DEFAULT_WORK_DIR);
    assert.strictEqual(resolveStorageRoot('/data/gitops/foo'), config.DEFAULT_WORK_DIR);
    assert.strictEqual(resolveStorageRoot('/home/user/repo'), config.DEFAULT_WORK_DIR);
    assert.strictEqual(resolveStorageRoot(null), config.DEFAULT_WORK_DIR);
  });

  await withEnv({ ...clean, AGENT_ROLE: 'qe' }, () => {
    assert.strictEqual(resolveStorageRoot(), '/data/gitops-qe');
    assert.strictEqual(resolveStorageRoot('/data/workspace/x'), '/data/gitops-qe', 'role mount wins over a derived mount');
  });

  await withEnv({ ...clean, AGENT_ROLE: 'a/b' }, () => {
    assert.strictEqual(resolveStorageRoot('/data/workspace/x'), '/data/workspace', 'unsafe role ignored');
  });

  await withEnv({ ...clean, AGENT_ROLE: 'qe', DEFAULT_WORK_DIR: '/data/explicit' }, () => {
    assert.strictEqual(resolveStorageRoot('/data/workspace/x'), '/data/explicit');
  });

  await withEnv({ ...clean, DEFAULT_WORK_DIR: '/data/explicit', STORAGE_RECYCLER_ROOT: '/data/recycler-root' }, () => {
    assert.strictEqual(resolveStorageRoot('/data/workspace/x'), '/data/recycler-root');
  });
});

// ---------------------------------------------------------------------------
// statfs
// ---------------------------------------------------------------------------

test('getStorageUsage computes correct bytes and ratio from (mocked) statfs', async () => {
  const restore = mockStatfs(0.25);
  try {
    const result = await getStorageUsage('/tmp/irrelevant');
    assert.strictEqual(result.ok, true);
    assert.strictEqual(result.totalBytes, 1000000 * 4096);
    assert.strictEqual(result.freeBytes, 750000 * 4096);
    assert.strictEqual(result.usedBytes, 250000 * 4096);
    assert.strictEqual(result.usedRatio, 0.25);
  } finally {
    restore();
  }
});

test('getStorageUsage returns safe fallback without throwing when path is invalid', async () => {
  await sandbox(async (root) => {
    const result = await getStorageUsage(path.join(root, 'does-not-exist'));
    assert.strictEqual(result.ok, false);
    assert.strictEqual(result.totalBytes, 0);
    assert.strictEqual(result.freeBytes, 0);
    assert.strictEqual(result.usedBytes, 0);
    assert.strictEqual(result.usedRatio, 0);
    assert.ok(result.error);
  });
});

// ---------------------------------------------------------------------------
// isProtectedPath
// ---------------------------------------------------------------------------

test('isProtectedPath guards null, undefined, jail roots, and non-jail paths', () => {
  assert.strictEqual(isProtectedPath(null), true);
  assert.strictEqual(isProtectedPath(''), true);
  assert.strictEqual(isProtectedPath(undefined), true);

  assert.strictEqual(isProtectedPath('/'), true);
  assert.strictEqual(isProtectedPath('/data'), true);
  assert.strictEqual(isProtectedPath('/tmp'), true);

  // Boundary prefixes without path separator are rejected
  assert.strictEqual(isProtectedPath('/data-evil/repo'), true);
  assert.strictEqual(isProtectedPath('/tmp-hacked/payload'), true);

  assert.strictEqual(isProtectedPath('/etc/passwd'), true);
  assert.strictEqual(isProtectedPath('/var/log/syslog'), true);
  assert.strictEqual(isProtectedPath('/home/user/repo'), true);
});

test('isProtectedPath protects sensitive credentials, hook paths, and agent rules on path boundaries', () => {
  assert.strictEqual(isProtectedPath('/tmp/gh-token-map.json'), true);
  assert.strictEqual(isProtectedPath('/tmp/git-creds-12345'), true);
  assert.strictEqual(isProtectedPath('/tmp/git-creds'), true);
  assert.strictEqual(isProtectedPath('/tmp/git-creds/token'), true);
  assert.strictEqual(isProtectedPath('/tmp/.darwin-hooks-1000/strike.count'), true);
  assert.strictEqual(isProtectedPath('/tmp/agent-rules/01-rule.md'), true);
  assert.strictEqual(isProtectedPath('/tmp/agent-rules'), true);
  assert.strictEqual(isProtectedPath('/var/secrets/token'), true);
  assert.strictEqual(isProtectedPath('/app/server.js'), true);

  // boundary-matched entries do not over-match unrelated siblings
  assert.strictEqual(isProtectedPath('/tmp/agent-rules-scratch/x'), false);
});

test('isProtectedPath without a workDir keeps the conservative bidirectional CWD shielding', () => {
  const cwds = ['/data/gitops/active-repo', '/data/gitops/recent-repo'];

  assert.strictEqual(isProtectedPath('/data/gitops/active-repo', cwds), true);
  assert.strictEqual(isProtectedPath('/data/gitops/recent-repo', cwds), true);
  assert.strictEqual(isProtectedPath('/data/gitops/active-repo/src/lib', cwds), true);
  assert.strictEqual(isProtectedPath('/data/gitops/recent-repo/dist/bundle.js', cwds), true);
  assert.strictEqual(isProtectedPath('/data/gitops', cwds), true);

  assert.strictEqual(isProtectedPath('/data/gitops/stale-unrelated-repo', cwds), false);
  assert.strictEqual(isProtectedPath('/tmp/random-scratch-file.txt', cwds), false);
});

test('isProtectedPath with a workDir: a CWD equal to (or above) the root does NOT shield sibling workspaces', () => {
  const root = '/data/gitops-developer';

  for (const cwd of [root, '/data', '/data/']) {
    assert.strictEqual(isProtectedPath(`${root}/stale-repo`, [cwd], root), false, `cwd=${cwd}`);
    assert.strictEqual(isProtectedPath(`${root}/results/old.md`, [cwd], root), false, `cwd=${cwd}`);
  }
  // the root itself is never a recycle target
  assert.strictEqual(isProtectedPath(root, [root], root), true);
  assert.strictEqual(isProtectedPath(root, [], root), true);
  assert.strictEqual(isProtectedPath('/data/other-volume/repo', [], root), true, 'outside the root');
});

test('isProtectedPath with a workDir: a specific active sub-repository stays shielded (self, descendants, holders)', () => {
  const root = '/data/gitops-developer';
  const active = `${root}/active-repo`;

  assert.strictEqual(isProtectedPath(active, [active], root), true);
  assert.strictEqual(isProtectedPath(`${active}/src`, [active], root), true, 'candidate inside the CWD');
  // CWD deep inside a workspace protects the workspace that holds it
  assert.strictEqual(isProtectedPath(active, [`${active}/src/lib`], root), true, 'candidate holds the CWD');
  assert.strictEqual(isProtectedPath(`${root}/other-repo`, [active, root], root), false);
  assert.strictEqual(isProtectedPath(`${root}/active-repo-2`, [active], root), false, 'prefix without separator');
});

test('isProtectedPath with a workDir: results dir, events and lost+found are reserved; results contents are not', () => {
  const root = '/data/gitops-developer';
  assert.strictEqual(isProtectedPath(`${root}/results`, [], root), true);
  assert.strictEqual(isProtectedPath(`${root}/results/old.md`, [], root), false);
  assert.strictEqual(isProtectedPath(`${root}/events`, [], root), true);
  assert.strictEqual(isProtectedPath(`${root}/events/event-evt-1.md`, [], root), true);
  assert.strictEqual(isProtectedPath(`${root}/lost+found`, [], root), true);
});

// ---------------------------------------------------------------------------
// pinning / live protected set
// ---------------------------------------------------------------------------

test('pinTaskCwd/unpinTaskCwd are reference counted and ignore invalid input', async () => {
  await sandbox(async (root) => {
    const cwd = path.join(root, 'repo');
    pinTaskCwd(null);
    pinTaskCwd('');
    assert.deepStrictEqual(collectProtectedCwds(null), []);

    pinTaskCwd(cwd);
    pinTaskCwd(cwd);
    assert.ok(collectProtectedCwds(null).includes(cwd));
    unpinTaskCwd(cwd);
    assert.ok(collectProtectedCwds(null).includes(cwd), 'still pinned after one unpin');
    unpinTaskCwd(cwd);
    assert.ok(!collectProtectedCwds(null).includes(cwd));
    assert.doesNotThrow(() => unpinTaskCwd(cwd));
  });
});

test('collectProtectedCwds is the live union of candidate, current task, last task and pinned CWDs', async () => {
  await sandbox(async () => {
    state.setCurrentTask({ eventId: 'e1', cwd: '/data/gitops-qe/a' });
    state.saveLastTaskContext({ eventId: 'e0', cwd: '/data/gitops-qe/b' });
    pinTaskCwd('/data/gitops-qe/p');
    const cwds = collectProtectedCwds('/data/gitops-qe/c');
    assert.deepStrictEqual(new Set(cwds), new Set([
      '/data/gitops-qe/a', '/data/gitops-qe/b', '/data/gitops-qe/p', '/data/gitops-qe/c',
    ]));

    state.clearCurrentTask();
    assert.ok(!collectProtectedCwds(null).includes('/data/gitops-qe/a'), 'reads live state, not a snapshot');
  });
});

// ---------------------------------------------------------------------------
// activity markers (shared developer/qe PVC)
// ---------------------------------------------------------------------------

test('getWorkspaceActivityMs reflects the newest of dir, .git bookkeeping, markers and children', async () => {
  await sandbox(async (root) => {
    const idle = makeWorkspace(root, 'idle', 10 * HOUR);
    const idleActivity = await getWorkspaceActivityMs(idle);
    assert.ok(Math.abs(Date.now() - idleActivity - 10 * HOUR) < 5000);

    // dir mtime does not change when a nested .git/index is rewritten by the sibling sidecar
    const busy = makeWorkspace(root, 'busy', 10 * HOUR);
    fs.mkdirSync(path.join(busy, '.git'));
    fs.writeFileSync(path.join(busy, '.git', 'index'), 'idx');
    setAge(path.join(busy, '.git'), 10 * HOUR);
    setAge(busy, 10 * HOUR);
    assert.ok(Date.now() - (await getWorkspaceActivityMs(busy)) < 5000, '.git/index counts');

    const marked = makeWorkspace(root, 'marked', 10 * HOUR);
    fs.writeFileSync(path.join(marked, '.darwin-active-qe'), 'pid');
    setAge(marked, 10 * HOUR);
    assert.ok(Date.now() - (await getWorkspaceActivityMs(marked)) < 5000, 'marker child counts');

    assert.strictEqual(await getWorkspaceActivityMs(path.join(root, 'missing')), 0);
  });
});

test('touchActivityMarker writes inside .git for repos, in the workspace otherwise, and refuses unsafe targets', async () => {
  await sandbox(async (root) => {
    const repo = makeWorkspace(root, 'repo');
    fs.mkdirSync(path.join(repo, '.git'));
    fs.mkdirSync(path.join(repo, 'src'));
    const plain = makeWorkspace(root, 'plain');
    fs.mkdirSync(path.join(root, 'results'));

    assert.strictEqual(await touchActivityMarker(path.join(repo, 'src'), root), path.join(repo, '.git', 'darwin-active'));
    assert.ok(fs.existsSync(path.join(repo, '.git', 'darwin-active')));
    assert.ok(!fs.existsSync(path.join(repo, '.darwin-active')), 'a repo working tree is never dirtied');

    assert.strictEqual(await touchActivityMarker(plain, root), path.join(plain, '.darwin-active'));
    assert.ok(fs.existsSync(path.join(plain, '.darwin-active')));

    assert.strictEqual(await touchActivityMarker(root, root), null, 'cwd == root');
    assert.strictEqual(await touchActivityMarker(path.join(root, 'results', 'x'), root), null, 'reserved top-level');
    assert.strictEqual(await touchActivityMarker(path.join(root, 'ghost'), root), null, 'missing workspace');
    assert.strictEqual(await touchActivityMarker('/tmp/elsewhere-xyz/repo', root), null, 'outside the root');
    assert.strictEqual(await touchActivityMarker(null, root), null);
  });
});

// ---------------------------------------------------------------------------
// Tier 1
// ---------------------------------------------------------------------------

test('Tier 1 purges stale results files older than TTL, even when cwd/lastCwd equal the root (R2)', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.1));
    const resultsDir = path.join(root, 'results');
    fs.mkdirSync(resultsDir);
    const staleFile = path.join(resultsDir, 'stale-findings.md');
    const freshFile = path.join(resultsDir, 'fresh-findings.md');
    fs.writeFileSync(staleFile, 'old content');
    fs.writeFileSync(freshFile, 'new content');
    setAge(staleFile, STORAGE_RESULTS_TTL_MS + HOUR);

    state.setCurrentTask({ eventId: 'e', cwd: root });
    state.saveLastTaskContext({ eventId: 'e0', cwd: root });

    const outcome = await runStorageRecycle(root);
    assert.strictEqual(outcome.ok, true);
    assert.strictEqual(outcome.purgedCount, 1);
    assert.strictEqual(fs.existsSync(staleFile), false, 'stale file should have been deleted');
    assert.strictEqual(fs.existsSync(freshFile), true, 'fresh file should be preserved');
    assert.strictEqual(fs.existsSync(resultsDir), true, 'results dir itself is kept');
  });
});

test('Tier 1 refuses to descend into a symlinked results directory (lstat)', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.1));
    const outside = makeRoot();
    undo(() => fs.rmSync(outside, { recursive: true, force: true }));
    const victim = path.join(outside, 'precious.md');
    fs.writeFileSync(victim, 'keep me');
    setAge(victim, STORAGE_RESULTS_TTL_MS + HOUR);
    fs.symlinkSync(outside, path.join(root, 'results'));

    const outcome = await runStorageRecycle(root);
    assert.strictEqual(outcome.ok, true);
    assert.strictEqual(outcome.purgedCount, 0);
    assert.strictEqual(fs.existsSync(victim), true, 'files behind the symlink must never be touched');
    assert.ok(fs.lstatSync(path.join(root, 'results')).isSymbolicLink());
  });
});

test('Tier 1 refuses a results symlink that points inside the root', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.1));
    const other = makeWorkspace(root, 'other-repo', 0);
    const victim = path.join(other, 'stale-but-not-results.md');
    fs.writeFileSync(victim, 'belongs to a workspace, not to results/');
    setAge(victim, STORAGE_RESULTS_TTL_MS + HOUR);
    fs.symlinkSync(other, path.join(root, 'results'));

    const outcome = await runStorageRecycle(root);
    assert.strictEqual(outcome.ok, true);
    assert.strictEqual(outcome.purgedCount, 0);
    assert.ok(fs.existsSync(victim), 'realpath containment alone must not make an in-root symlink acceptable');
    assert.ok(fs.lstatSync(path.join(root, 'results')).isSymbolicLink());
  });
});

test('Tier 1 unlinks a symlink entry inside results without following it', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.1));
    const outside = makeRoot();
    undo(() => fs.rmSync(outside, { recursive: true, force: true }));
    const victim = path.join(outside, 'precious.md');
    fs.writeFileSync(victim, 'keep me');

    const resultsDir = path.join(root, 'results');
    fs.mkdirSync(resultsDir);
    const link = path.join(resultsDir, 'link');
    fs.symlinkSync(outside, link);
    setAge(link, STORAGE_RESULTS_TTL_MS + HOUR);

    const outcome = await runStorageRecycle(root);
    assert.strictEqual(outcome.ok, true);
    assert.strictEqual(fs.existsSync(link), false, 'the link itself is removed');
    assert.strictEqual(fs.existsSync(victim), true, 'its target is untouched');
    assert.strictEqual(fs.existsSync(outside), true);
  });
});

// ---------------------------------------------------------------------------
// Tier 2
// ---------------------------------------------------------------------------

test('Tier 2 evicts stale event workspaces, keeps fresh/active/events, and judges staleness by real activity', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.8)); // >= HIGH, < CRITICAL
    const stale = makeWorkspace(root, 'repo-evt-44cf0bba', STORAGE_STALE_MS + 6 * HOUR);
    const fresh = makeWorkspace(root, 'repo-evt-fresh', 0);
    const active = makeWorkspace(root, 'repo-evt-active', STORAGE_STALE_MS + 6 * HOUR);
    const eventsDir = makeWorkspace(root, 'events', STORAGE_STALE_MS + 6 * HOUR);
    const plainOld = makeWorkspace(root, 'plain-old', STORAGE_STALE_MS + 6 * HOUR);

    // old dir mtime but the sibling sidecar just touched .git/index -> must survive
    const busy = makeWorkspace(root, 'repo-evt-busy', STORAGE_STALE_MS + 6 * HOUR);
    fs.mkdirSync(path.join(busy, '.git'));
    fs.writeFileSync(path.join(busy, '.git', 'index'), 'idx');
    setAge(path.join(busy, '.git'), STORAGE_STALE_MS + 6 * HOUR);
    setAge(busy, STORAGE_STALE_MS + 6 * HOUR);

    // fresh cross-process marker -> must survive
    const marked = makeWorkspace(root, 'repo-evt-marked', STORAGE_STALE_MS + 6 * HOUR);
    fs.writeFileSync(path.join(marked, '.darwin-active'), 'pid');
    setAge(marked, STORAGE_STALE_MS + 6 * HOUR);

    state.setCurrentTask({ eventId: 'evt-active', cwd: active });
    const outcome = await runStorageRecycle(root);

    assert.strictEqual(outcome.ok, true);
    assert.strictEqual(fs.existsSync(stale), false, 'stale event dir should be evicted');
    assert.strictEqual(fs.existsSync(fresh), true, 'fresh event dir should be preserved');
    assert.strictEqual(fs.existsSync(active), true, 'active workspace must be preserved');
    assert.strictEqual(fs.existsSync(eventsDir), true, 'events doc dir must be preserved');
    assert.strictEqual(fs.existsSync(plainOld), true, 'Tier 2 only touches event-named workspaces');
    assert.strictEqual(fs.existsSync(busy), true, 'recent .git/index activity protects the workspace');
    assert.strictEqual(fs.existsSync(marked), true, 'recent activity marker protects the workspace');
  });
});

// ---------------------------------------------------------------------------
// Tier 3
// ---------------------------------------------------------------------------

test('Tier 3 at >= critical evicts oldest first and stops once usage drops below the high watermark', async () => {
  await sandbox(async (root, undo) => {
    const names = [];
    for (let i = 0; i < 7; i++) {
      names.push(`repo-${i}`);
      makeWorkspace(root, `repo-${i}`, (8 - i) * HOUR); // repo-0 oldest
    }
    // 0.95 with all 7 present, minus 0.10 per eviction -> 0.65 (< 0.70) after the 3rd
    undo(mockStatfs(() => 0.95 - 0.1 * (7 - countEntries(root, 'repo-'))));

    const outcome = await runStorageRecycle(root);
    assert.strictEqual(outcome.ok, true);
    assert.strictEqual(outcome.purgedCount, 3);
    for (const gone of ['repo-0', 'repo-1', 'repo-2']) assert.ok(!fs.existsSync(path.join(root, gone)), `${gone} evicted`);
    for (const kept of ['repo-3', 'repo-4', 'repo-5', 'repo-6']) assert.ok(fs.existsSync(path.join(root, kept)), `${kept} kept`);
    assert.ok(outcome.finalRatio < STORAGE_HIGH_WATERMARK);
    assert.ok(outcome.finalRatio < STORAGE_CRITICAL_WATERMARK);
  });
});

test('Tier 3 never deletes more than STORAGE_MAX_TIER3_DELETIONS per sweep', async () => {
  await sandbox(async (root, undo) => {
    const total = STORAGE_MAX_TIER3_DELETIONS + 3;
    for (let i = 0; i < total; i++) makeWorkspace(root, `repo-${i}`, (total + 2 - i) * HOUR);
    undo(mockStatfs(0.95)); // never recovers

    const outcome = await runStorageRecycle(root);
    assert.strictEqual(outcome.purgedCount, STORAGE_MAX_TIER3_DELETIONS);
    assert.strictEqual(countEntries(root, 'repo-'), 3);
    // the newest survive
    for (let i = total - 3; i < total; i++) assert.ok(fs.existsSync(path.join(root, `repo-${i}`)));
  });
});

test('Tier 3 evicts least-recently-active first even when alphabetical order disagrees', async () => {
  await sandbox(async (root, undo) => {
    // alphabetical (readdir) order is newest -> middle -> oldest, the exact opposite of LRU order
    const newest = makeWorkspace(root, 'aaa-newest', 2 * HOUR);
    const middle = makeWorkspace(root, 'mmm-middle', 5 * HOUR);
    const oldest = makeWorkspace(root, 'zzz-oldest', 9 * HOUR);
    // usage recovers after the first eviction, so exactly one workspace goes
    undo(mockStatfs(() => (countEntries(root, '') === 3 ? 0.95 : 0.5)));

    const outcome = await runStorageRecycle(root);
    assert.strictEqual(outcome.ok, true);
    assert.strictEqual(outcome.purgedCount, 1);
    assert.ok(!fs.existsSync(oldest), 'the least recently active workspace is evicted first');
    assert.ok(fs.existsSync(middle));
    assert.ok(fs.existsSync(newest));
  });
});

test('Tier 3 stops as soon as statfs fails and reports ok:false', async () => {
  await sandbox(async (root, undo) => {
    for (let i = 0; i < 4; i++) makeWorkspace(root, `repo-${i}`, (6 - i) * HOUR);
    undo(mockStatfs(() => {
      if (countEntries(root, 'repo-') < 4) throw new Error('cephfs stale handle');
      return 0.95;
    }));

    const outcome = await runStorageRecycle(root);
    assert.strictEqual(countEntries(root, 'repo-'), 3, 'exactly one eviction before the failure stopped the loop');
    assert.strictEqual(outcome.ok, false);
    assert.match(outcome.error, /stale handle/);
    assert.strictEqual(outcome.purgedCount, 1);
    assert.strictEqual(outcome.finalRatio, 0.95, 'last known good ratio, not 0');
  });
});

test('Tier 3 minimum-age gate never purges recently active workspaces even if statfs lags', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.95));
    const old = makeWorkspace(root, 'repo-old', 3 * HOUR);
    const justNow = makeWorkspace(root, 'repo-fresh', 0);
    const recent = makeWorkspace(root, 'repo-recent', Math.floor(STORAGE_TIER3_MIN_AGE_MS / 3));
    // old dir, but a file inside was just edited -> activity is recent
    const edited = makeWorkspace(root, 'repo-edited', 3 * HOUR);
    fs.writeFileSync(path.join(edited, 'work-in-progress.txt'), 'edit');
    setAge(edited, 3 * HOUR);

    const outcome = await runStorageRecycle(root);
    assert.strictEqual(outcome.purgedCount, 1);
    assert.ok(!fs.existsSync(old));
    assert.ok(fs.existsSync(justNow));
    assert.ok(fs.existsSync(recent));
    assert.ok(fs.existsSync(edited));
  });
});

test('Tier 3 isolates per-candidate rm failures (EBUSY/EACCES) and keeps sweeping', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.95));
    const busy = makeWorkspace(root, 'repo-0', 9 * HOUR); // oldest -> attempted first
    const denied = makeWorkspace(root, 'repo-1', 8 * HOUR);
    for (let i = 2; i < 5; i++) makeWorkspace(root, `repo-${i}`, (9 - i) * HOUR);

    const origRm = fs.promises.rm;
    fs.promises.rm = async (p, opts) => {
      if (p === busy) throw Object.assign(new Error('resource busy'), { code: 'EBUSY' });
      if (p === denied) throw Object.assign(new Error('permission denied'), { code: 'EACCES' });
      return origRm(p, opts);
    };
    undo(() => { fs.promises.rm = origRm; });

    const outcome = await runStorageRecycle(root);
    assert.strictEqual(outcome.ok, true, 'one bad candidate must not abort the sweep');
    assert.strictEqual(outcome.failedCount, 2);
    assert.strictEqual(outcome.purgedCount, 3);
    assert.ok(fs.existsSync(busy));
    assert.ok(fs.existsSync(denied));
    for (let i = 2; i < 5; i++) assert.ok(!fs.existsSync(path.join(root, `repo-${i}`)));
  });
});

test('Tier 3 skips dot-directories, results, events, lost+found and symlinks', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.95));
    const outside = makeRoot();
    undo(() => fs.rmSync(outside, { recursive: true, force: true }));
    const protectedNames = ['.hidden-cache', '.git', 'results', 'events', 'lost+found'];
    for (const n of protectedNames) makeWorkspace(root, n, 20 * HOUR);
    fs.symlinkSync(outside, path.join(root, 'linked-repo'));
    setAge(path.join(root, 'linked-repo'), 20 * HOUR);
    const victim = makeWorkspace(root, 'repo-victim', 10 * HOUR);

    const outcome = await runStorageRecycle(root);
    assert.strictEqual(outcome.ok, true);
    assert.ok(!fs.existsSync(victim));
    for (const n of protectedNames) assert.ok(fs.existsSync(path.join(root, n)), `${n} must survive`);
    assert.ok(fs.lstatSync(path.join(root, 'linked-repo')).isSymbolicLink());
    assert.ok(fs.existsSync(outside));
  });
});

test('cwd === workDir and lastCwd === workDir do not block cleanup, while a specific active repo stays protected', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.95));
    const active = makeWorkspace(root, 'active-repo', 6 * HOUR);
    const stale = makeWorkspace(root, 'stale-repo', 7 * HOUR);

    state.setCurrentTask({ eventId: 'e', cwd: active });
    state.saveLastTaskContext({ eventId: 'e0', cwd: root });
    const outcome = await runStorageRecycle(root);
    assert.strictEqual(outcome.ok, true);
    assert.ok(!fs.existsSync(stale), 'sibling workspace is reclaimable although lastCwd == workDir');
    assert.ok(fs.existsSync(active), 'the active sub-repository stays protected');
  });

  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.95));
    const stale = makeWorkspace(root, 'stale-repo', 7 * HOUR);
    state.setCurrentTask({ eventId: 'e', cwd: root });
    const outcome = await runStorageRecycle(root);
    assert.strictEqual(outcome.ok, true);
    assert.ok(!fs.existsSync(stale), 'cwd == workDir must not shield every candidate');
  });
});

test('candidateCwd + current task cwd + last task cwd are protected as a union', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.95));
    const a = makeWorkspace(root, 'repo-a', 6 * HOUR);
    fs.mkdirSync(path.join(a, 'src'));
    const b = makeWorkspace(root, 'repo-b', 6 * HOUR);
    const c = makeWorkspace(root, 'repo-c', 6 * HOUR);
    const d = makeWorkspace(root, 'repo-d', 6 * HOUR);
    setAge(a, 6 * HOUR);

    state.setCurrentTask({ eventId: 'e', cwd: path.join(a, 'src') });
    state.saveLastTaskContext({ eventId: 'e0', cwd: b });
    const outcome = await runStorageRecycle(root, { candidateCwd: c });

    assert.strictEqual(outcome.ok, true);
    assert.ok(fs.existsSync(a), 'current task CWD (nested) protects its workspace');
    assert.ok(fs.existsSync(b), 'last task CWD');
    assert.ok(fs.existsSync(c), 'candidateCwd');
    assert.ok(!fs.existsSync(d), 'the only unprotected workspace is reclaimed');
  });
});

test('protection is re-checked immediately before every rm: a CWD pinned mid-sweep survives', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.95));
    makeWorkspace(root, 'repo-a', 9 * HOUR);
    const b = makeWorkspace(root, 'repo-b', 8 * HOUR);
    makeWorkspace(root, 'repo-c', 7 * HOUR);

    const origRm = fs.promises.rm;
    let first = true;
    fs.promises.rm = async (p, opts) => {
      if (first) {
        first = false;
        pinTaskCwd(b); // a task starts in repo-b while the sweep is already running
      }
      return origRm(p, opts);
    };
    undo(() => { fs.promises.rm = origRm; });

    const outcome = await runStorageRecycle(root);
    assert.strictEqual(outcome.ok, true);
    assert.ok(!fs.existsSync(path.join(root, 'repo-a')));
    assert.ok(fs.existsSync(b), 'repo-b was pinned mid-sweep');
    assert.ok(!fs.existsSync(path.join(root, 'repo-c')));
  });
});

test('a task pinned while a sweep is in flight is shielded; the overlapping pre-task check reports in-flight', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.95));
    makeWorkspace(root, 'repo-a', 9 * HOUR);
    const b = makeWorkspace(root, 'repo-b', 8 * HOUR);

    const origRm = fs.promises.rm;
    let release;
    const gate = new Promise((r) => { release = r; });
    let entered;
    const enteredP = new Promise((r) => { entered = r; });
    fs.promises.rm = async (p, opts) => {
      entered();
      await gate;
      return origRm(p, opts);
    };
    undo(() => { fs.promises.rm = origRm; });

    const sweep = runStorageRecycle(root);
    await enteredP;

    pinTaskCwd(b); // what cli-executor's withTaskStorage does for the task being started
    const overlapping = await checkAndRecycleStorage(root, b);
    assert.strictEqual(overlapping.skipped, true);
    assert.strictEqual(overlapping.reason, 'in-flight');

    release();
    const outcome = await sweep;
    assert.strictEqual(outcome.ok, true);
    assert.ok(fs.existsSync(b), 'the task that started during the sweep keeps its workspace');
    assert.ok(!fs.existsSync(path.join(root, 'repo-a')));
  });
});

// ---------------------------------------------------------------------------
// statfs failure reporting (R10)
// ---------------------------------------------------------------------------

test('statfs failure after Tier 2 returns ok:false with the last known ratio instead of a fake success', async () => {
  await sandbox(async (root, undo) => {
    const stale = makeWorkspace(root, 'repo-evt-stale', STORAGE_STALE_MS + 6 * HOUR);
    let calls = 0;
    undo(mockStatfs(() => {
      calls += 1;
      if (calls >= 3) throw new Error('statfs EIO'); // initial + post-Tier-1 ok, post-Tier-2 fails
      return 0.8;
    }));

    const outcome = await runStorageRecycle(root);
    assert.ok(!fs.existsSync(stale), 'Tier 2 ran');
    assert.strictEqual(outcome.ok, false);
    assert.match(outcome.error, /EIO/);
    assert.strictEqual(outcome.finalRatio, 0.8);
    assert.strictEqual(outcome.purgedCount, 1);
    assert.strictEqual(typeof outcome.cleanedBytes, 'number');
  });
});

test('statfs failure after Tier 3 returns ok:false with purge counts and the last known ratio', async () => {
  await sandbox(async (root, undo) => {
    makeWorkspace(root, 'repo-0', 6 * HOUR);
    makeWorkspace(root, 'repo-1', 5 * HOUR);
    let calls = 0;
    undo(mockStatfs(() => {
      calls += 1;
      if (calls >= 4) throw new Error('statfs EIO'); // initial, post-T1, post-T2 ok; post-eviction fails
      return 0.95;
    }));

    const outcome = await runStorageRecycle(root);
    assert.strictEqual(outcome.ok, false);
    assert.strictEqual(outcome.purgedCount, 1, 'loop stopped after the first eviction');
    assert.strictEqual(outcome.finalRatio, 0.95);
    assert.strictEqual(outcome.cleanedBytes, 0);
  });
});

test('initial statfs failure is reported as ok:false', async () => {
  await sandbox(async (root) => {
    const outcome = await runStorageRecycle(path.join(root, 'not-mounted'));
    assert.strictEqual(outcome.ok, false);
    assert.ok(outcome.error);
  });
});

// ---------------------------------------------------------------------------
// mutex (R15)
// ---------------------------------------------------------------------------

test('in-flight mutex (_isRecycling) drops concurrent runs', async () => {
  await sandbox(async (root, undo) => {
    const restoreBase = mockStatfs(0.1);
    const base = fs.promises.statfs;
    fs.promises.statfs = async (p) => {
      await new Promise((resolve) => setTimeout(resolve, 50));
      return base(p);
    };
    undo(restoreBase);

    const [res1, res2] = await Promise.all([runStorageRecycle(root), runStorageRecycle(root)]);
    assert.strictEqual(res1.ok, true);
    assert.strictEqual(res2.skipped, true);
    assert.strictEqual(res2.reason, 'in-flight');
  });
});

test('mutex is released when a state getter throws, and the sweep fails closed', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.1));
    const resultsDir = path.join(root, 'results');
    fs.mkdirSync(resultsDir);
    const stale = path.join(resultsDir, 'stale.md');
    fs.writeFileSync(stale, 'x');
    setAge(stale, STORAGE_RESULTS_TTL_MS + HOUR);

    const origGetter = state.getCurrentTask;
    state.getCurrentTask = () => { throw new Error('state exploded'); };
    try {
      const first = await runStorageRecycle(root);
      assert.strictEqual(first.ok, true);
      assert.strictEqual(fs.existsSync(stale), true, 'unknown protection state => nothing is deleted');
    } finally {
      state.getCurrentTask = origGetter;
    }

    const second = await runStorageRecycle(root);
    assert.notStrictEqual(second.reason, 'in-flight', 'mutex must have been released');
    assert.strictEqual(second.ok, true);
    assert.strictEqual(fs.existsSync(stale), false, 'healthy getters resume normal cleanup');
  });
});

test('mutex is released when the sweep itself rejects', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.1));
    const origRealpath = fs.promises.realpath;
    fs.promises.realpath = async () => { throw new Error('realpath EIO'); };
    try {
      await assert.rejects(() => runStorageRecycle(root), /realpath EIO/);
    } finally {
      fs.promises.realpath = origRealpath;
    }
    const again = await runStorageRecycle(root);
    assert.strictEqual(again.ok, true);
  });
});

test('mutex is released after an early return (initial statfs failure)', async () => {
  await sandbox(async (root) => {
    const early = await runStorageRecycle(path.join(root, 'not-mounted'));
    assert.strictEqual(early.ok, false);
    const later = await runStorageRecycle(root, {});
    assert.notStrictEqual(later.reason, 'in-flight');
  });
});

// ---------------------------------------------------------------------------
// shutdown drain (R11)
// ---------------------------------------------------------------------------

test('stopStorageRecycler resolves immediately when idle and blocks new sweeps until reset', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.1));
    await stopStorageRecycler();
    const outcome = await runStorageRecycle(root);
    assert.deepStrictEqual(outcome, { skipped: true, reason: 'shutting_down' });

    recycler.resetStorageRecycler();
    assert.strictEqual((await runStorageRecycle(root)).ok, true);
  });
});

test('stopStorageRecycler drains the in-flight sweep: the running rm finishes, no further deletions start', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.95));
    for (let i = 0; i < 3; i++) makeWorkspace(root, `repo-${i}`, (9 - i) * HOUR);

    const origRm = fs.promises.rm;
    let release;
    const gate = new Promise((r) => { release = r; });
    let entered;
    const enteredP = new Promise((r) => { entered = r; });
    fs.promises.rm = async (p, opts) => {
      entered();
      await gate;
      return origRm(p, opts);
    };
    undo(() => { fs.promises.rm = origRm; });

    const sweep = runStorageRecycle(root);
    await enteredP;

    let drained = false;
    const drain = stopStorageRecycler().then(() => { drained = true; });
    await new Promise((r) => setImmediate(r));
    assert.strictEqual(drained, false, 'drain waits for the in-flight rm');

    release();
    await drain;
    const outcome = await sweep;
    assert.strictEqual(drained, true);
    assert.strictEqual(outcome.purgedCount, 1, 'the in-flight deletion completed cleanly');
    assert.strictEqual(countEntries(root, 'repo-'), 2, 'nothing else was started after the abort');
  });
});

// ---------------------------------------------------------------------------
// pre-task fast path
// ---------------------------------------------------------------------------

test('checkAndRecycleStorage fast-path exits without file I/O when headroom is plenty', async () => {
  await sandbox(async (root, undo) => {
    undo(mockStatfs(0.1));
    const stale = makeWorkspace(root, 'repo-evt-stale', STORAGE_STALE_MS + 6 * HOUR);
    const result = await checkAndRecycleStorage(root, path.join(root, 'task'));
    assert.strictEqual(result.skipped, true);
    assert.strictEqual(result.reason, 'headroom_sufficient');
    assert.strictEqual(result.usedRatio, 0.1);
    assert.ok(fs.existsSync(stale), 'no sweep happened');
  });
});

test('checkAndRecycleStorage reports statfs_failed and recycles above the high watermark, releasing its pin', async () => {
  await sandbox(async (root, undo) => {
    const restoreFail = mockStatfs(() => { throw new Error('no mount'); });
    const failed = await checkAndRecycleStorage(root, path.join(root, 'task'));
    restoreFail();
    assert.strictEqual(failed.skipped, true);
    assert.strictEqual(failed.reason, 'statfs_failed');

    undo(mockStatfs(0.8));
    const stale = makeWorkspace(root, 'repo-evt-stale', STORAGE_STALE_MS + 6 * HOUR);
    const cwd = path.join(root, 'task');
    const result = await checkAndRecycleStorage(root, cwd);
    assert.strictEqual(result.ok, true);
    assert.ok(!fs.existsSync(stale));
    assert.ok(!collectProtectedCwds(null).includes(cwd), 'transient pin released');
  });
});

// ---------------------------------------------------------------------------
// withTaskStorage (cli-executor pre-task hook, R12/R17)
// ---------------------------------------------------------------------------

function loadExecutor() {
  const fakeHome = fs.mkdtempSync('/tmp/darwin-recycler-home-');
  const savedHome = process.env.HOME;
  process.env.HOME = fakeHome;
  try {
    return { mod: require('../cli-executor'), fakeHome };
  } finally {
    if (savedHome === undefined) delete process.env.HOME; else process.env.HOME = savedHome;
  }
}

test('withTaskStorage pins the cwd for the task, bounds a hung storage check, and unpins in finally', async () => {
  const { mod, fakeHome } = loadExecutor();
  await sandbox(async (root, undo) => {
    undo(() => fs.rmSync(fakeHome, { recursive: true, force: true }));
    const cwd = path.join(root, 'task');

    // 1. healthy: pinned while the task runs, released afterwards
    undo(mockStatfs(0.1));
    let seen;
    const value = await mod.withTaskStorage(cwd, 'test', async () => {
      seen = collectProtectedCwds(null).includes(cwd);
      return 'ran';
    });
    assert.strictEqual(value, 'ran');
    assert.strictEqual(seen, true);
    assert.ok(!collectProtectedCwds(null).includes(cwd));

    // 2. fn rejection propagates and still unpins
    await assert.rejects(() => mod.withTaskStorage(cwd, 'test', async () => { throw new Error('spawn failed'); }), /spawn failed/);
    assert.ok(!collectProtectedCwds(null).includes(cwd));

    // 3. storage check errors never block the task
    const restoreFail = mockStatfs(() => { throw new Error('cephfs down'); });
    assert.strictEqual(await mod.withTaskStorage(cwd, 'test', async () => 'still ran'), 'still ran');
    restoreFail();
  });
});

test('withTaskStorage does not wait on a hung CephFS metadata call beyond STORAGE_PRETASK_TIMEOUT_MS', async () => {
  const { mod, fakeHome } = loadExecutor();
  assert.strictEqual(config.STORAGE_PRETASK_TIMEOUT_MS, 50, 'test timeout applied at load');
  await sandbox(async (root, undo) => {
    undo(() => fs.rmSync(fakeHome, { recursive: true, force: true }));
    const orig = fs.promises.statfs;
    fs.promises.statfs = () => new Promise(() => {}); // never settles
    undo(() => { fs.promises.statfs = orig; });

    const cwd = path.join(root, 'task');
    const started = Date.now();
    let pinnedDuringTask = false;
    const value = await mod.withTaskStorage(cwd, 'test', async () => {
      pinnedDuringTask = collectProtectedCwds(null).includes(cwd);
      return 'ran';
    });
    assert.strictEqual(value, 'ran');
    assert.ok(Date.now() - started < 2000, 'task started without waiting for the hung statfs');
    assert.strictEqual(pinnedDuringTask, true);
  });
});

test('withTaskStorage derives the storage root from resolveStorageRoot(cwd)', async () => {
  const { mod, fakeHome } = loadExecutor();
  await sandbox(async (root, undo) => {
    undo(() => fs.rmSync(fakeHome, { recursive: true, force: true }));
    const probed = [];
    undo(mockStatfs((p) => { probed.push(p); return 0.1; }));

    const clean = { STORAGE_RECYCLER_ROOT: undefined, DEFAULT_WORK_DIR: undefined, AGENT_ROLE: undefined };
    await withEnv(clean, async () => {
      await mod.withTaskStorage('/data/workspace/Blackboard/gemini-sidecar', 'test', async () => 'ran');
      assert.deepStrictEqual(probed, ['/data/workspace'], 'ephemeral workspace mount derived from the task cwd');

      probed.length = 0;
      await mod.withTaskStorage('/data/gitops-qe/repo', 'test', async () => 'ran');
      assert.deepStrictEqual(probed, ['/data/gitops-qe']);
    });

    probed.length = 0;
    await withEnv({ ...clean, STORAGE_RECYCLER_ROOT: root }, async () => {
      await mod.withTaskStorage('/data/workspace/x', 'test', async () => 'ran');
      assert.deepStrictEqual(probed, [root], 'explicit root override wins over the cwd');
    });
  });
});
