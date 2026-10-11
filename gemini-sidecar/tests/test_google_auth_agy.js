// gemini-sidecar/tests/test_google_auth_agy.js
// @ai-rules:
// 1. [Pattern]: Self-contained unit tests with ephemeral RSA key pair and isolated temp HOME.
// 2. [Pattern]: Mocks global fetch to assert on RFC 7523 JWT assertion and token exchange.
// 3. [Contract]: Asserts on agy token schema, permissions (0600/0700), and caching semantics.

const { describe, it, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const jwt = require('jsonwebtoken');

const {
  hasGoogleServiceAccount,
  findGoogleServiceAccountPath,
  setupGoogleAuthForAgy,
  _resetGoogleAgyTokenCache,
} = require('../credentials');

describe('Google Service Account Headless Auth for Antigravity CLI (agy)', () => {
  let tmpDir;
  let fakeHome;
  let originalHome;
  let originalGoogleCreds;
  let originalFetch;
  let testPrivateKey;
  let testPublicKey;
  let fakeSaPath;

  beforeEach(() => {
    _resetGoogleAgyTokenCache();
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'agy-auth-test-'));
    fakeHome = path.join(tmpDir, 'home');
    fs.mkdirSync(fakeHome, { recursive: true });

    originalHome = process.env.HOME;
    originalGoogleCreds = process.env.GOOGLE_APPLICATION_CREDENTIALS;
    originalFetch = global.fetch;

    process.env.HOME = fakeHome;

    const keyPair = crypto.generateKeyPairSync('rsa', {
      modulusLength: 2048,
      publicKeyEncoding: { type: 'spki', format: 'pem' },
      privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
    });
    testPrivateKey = keyPair.privateKey;
    testPublicKey = keyPair.publicKey;

    fakeSaPath = path.join(tmpDir, 'service-account.json');
  });

  afterEach(() => {
    _resetGoogleAgyTokenCache();
    process.env.HOME = originalHome;
    if (originalGoogleCreds !== undefined) {
      process.env.GOOGLE_APPLICATION_CREDENTIALS = originalGoogleCreds;
    } else {
      delete process.env.GOOGLE_APPLICATION_CREDENTIALS;
    }
    global.fetch = originalFetch;
    try {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    } catch (_) {}
  });

  it('T-1: returns false when no service account is found', async () => {
    delete process.env.GOOGLE_APPLICATION_CREDENTIALS;
    const res = await setupGoogleAuthForAgy({ saPath: path.join(tmpDir, 'nonexistent.json') });
    assert.strictEqual(res, false);
  });

  it('T-2: returns false when service account JSON is invalid or missing keys', async () => {
    fs.writeFileSync(fakeSaPath, JSON.stringify({ project_id: 'test-project' }), 'utf8');
    const res = await setupGoogleAuthForAgy({ saPath: fakeSaPath });
    assert.strictEqual(res, false);
  });

  it('T-3: mints token via JWT assertion and writes valid agy credentials', async () => {
    const saData = {
      project_id: 'test-cnv-insights',
      client_email: 'test-agent@test-cnv-insights.iam.gserviceaccount.com',
      private_key: testPrivateKey,
      token_uri: 'https://oauth2.googleapis.com/token',
    };
    fs.writeFileSync(fakeSaPath, JSON.stringify(saData), 'utf8');

    let fetchCalled = false;
    let assertionPayload = null;

    global.fetch = async (url, options) => {
      fetchCalled = true;
      assert.strictEqual(url, 'https://oauth2.googleapis.com/token');
      assert.strictEqual(options.method, 'POST');

      const params = new URLSearchParams(options.body);
      assert.strictEqual(params.get('grant_type'), 'urn:ietf:params:oauth:grant-type:jwt-bearer');
      const assertion = params.get('assertion');
      assert.ok(assertion);

      assertionPayload = jwt.verify(assertion, testPublicKey, { algorithms: ['RS256'] });
      assert.strictEqual(assertionPayload.iss, saData.client_email);
      assert.strictEqual(assertionPayload.sub, saData.client_email);
      assert.strictEqual(assertionPayload.aud, 'https://oauth2.googleapis.com/token');
      assert.ok(assertionPayload.scope.includes('https://www.googleapis.com/auth/cloud-platform'));

      return {
        ok: true,
        status: 200,
        json: async () => ({
          access_token: 'mock-ya29-token-12345',
          token_type: 'Bearer',
          expires_in: 3600,
        }),
      };
    };

    const success = await setupGoogleAuthForAgy({ saPath: fakeSaPath });
    assert.strictEqual(success, true);
    assert.strictEqual(fetchCalled, true);

    // Verify ~/.gemini/antigravity-cli/antigravity-oauth-token
    const agyTokenPath = path.join(fakeHome, '.gemini', 'antigravity-cli', 'antigravity-oauth-token');
    assert.ok(fs.existsSync(agyTokenPath), 'antigravity-oauth-token must exist');
    const agyTokenStat = fs.statSync(agyTokenPath);
    assert.strictEqual(agyTokenStat.mode & 0o777, 0o600, 'token file must be 0600');

    const agyTokenContent = JSON.parse(fs.readFileSync(agyTokenPath, 'utf8'));
    assert.strictEqual(agyTokenContent.auth_method, 'gcp');
    assert.strictEqual(agyTokenContent.project_id, 'test-cnv-insights');
    assert.strictEqual(agyTokenContent.token.access_token, 'mock-ya29-token-12345');
    assert.strictEqual(agyTokenContent.token.token_type, 'Bearer');
    assert.ok(agyTokenContent.token.expiry);

    // Verify ~/.gemini/oauth_creds.json
    const oauthCredsPath = path.join(fakeHome, '.gemini', 'oauth_creds.json');
    assert.ok(fs.existsSync(oauthCredsPath), 'oauth_creds.json must exist');
    const oauthCredsContent = JSON.parse(fs.readFileSync(oauthCredsPath, 'utf8'));
    assert.strictEqual(oauthCredsContent.access_token, 'mock-ya29-token-12345');

    // Verify settings.json
    const settingsPath = path.join(fakeHome, '.gemini', 'antigravity-cli', 'settings.json');
    assert.ok(fs.existsSync(settingsPath), 'settings.json must exist');
    const settingsContent = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
    assert.strictEqual(settingsContent.allowNonWorkspaceAccess, true);
  });

  it('T-4: utilizes cache on subsequent call within expiration window', async () => {
    const saData = {
      project_id: 'test-cnv-insights',
      client_email: 'test-agent@test-cnv-insights.iam.gserviceaccount.com',
      private_key: testPrivateKey,
    };
    fs.writeFileSync(fakeSaPath, JSON.stringify(saData), 'utf8');

    let fetchCount = 0;
    global.fetch = async () => {
      fetchCount++;
      return {
        ok: true,
        status: 200,
        json: async () => ({
          access_token: 'mock-token-call-' + fetchCount,
          token_type: 'Bearer',
          expires_in: 3600,
        }),
      };
    };

    const first = await setupGoogleAuthForAgy({ saPath: fakeSaPath });
    assert.strictEqual(first, true);
    assert.strictEqual(fetchCount, 1);

    const second = await setupGoogleAuthForAgy({ saPath: fakeSaPath });
    assert.strictEqual(second, true);
    assert.strictEqual(fetchCount, 1, 'Subsequent call within validity must use cache');

    const third = await setupGoogleAuthForAgy({ saPath: fakeSaPath, force: true });
    assert.strictEqual(third, true);
    assert.strictEqual(fetchCount, 2, 'force: true must bypass cache');
  });
});
