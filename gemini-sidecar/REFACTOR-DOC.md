# Pre-Refactor Documentation: `gemini-sidecar/server.js`

> **File:** `gemini-sidecar/server.js` (1390 lines)
> **Generated:** 2026-02-21
> **Purpose:** Validate no logic is lost during modular split.

---

## 1. Function Inventory

| # | Name | Lines | Parameters | Return Type | Pure / Side-Effect | Description |
|---|------|-------|------------|-------------|-------------------|-------------|
| 1 | `stripAnsi` | 49 | `text: string` | `string` | Pure | Removes ANSI escape codes from PTY output. |
| 2 | `parseStreamLine` | 128–169 | `line: string` | `{text, sessionId, toolCalls, done} \| null` | Pure | Unified stream-json line parser for both Gemini and Claude CLIs. Handles init, assistant message, content_block_delta, assistant summary, and result events. Falls back to raw text on JSON parse failure. |
| 3 | `parseClaudeStreamLine` | 172–175 | `line: string` | `string \| null` | Pure | Backward-compat wrapper around `parseStreamLine`. Returns only the text field. |
| 4 | `buildCLICommand` | 181–209 | `prompt: string, options?: {autoApprove?, sessionId?}` | `{binary: string, args: string[]}` | Pure | Routes to `gemini` or `claude` binary based on `AGENT_CLI` env var. Handles `--permission-mode`, `--dangerously-skip-permissions` / `--yolo`, `--resume`, `-o stream-json`, model selection. |
| 5 | `findPrivateKeyPath` | 233–240 | _(none)_ | `string \| null` | Side-effect (fs read) | Scans `/secrets/github/` for a `.pem` file. |
| 6 | `hasGitHubCredentials` | 245–249 | _(none)_ | `boolean` | Side-effect (fs read) | Checks existence of `app-id`, `installation-id`, and a `.pem` key in secrets dir. |
| 7 | `generateInstallationToken` | 256–293 | _(none)_ | `Promise<string>` | Side-effect (fs read + HTTP POST) | Reads GitHub App credentials, creates JWT (RS256), exchanges it for an installation access token via GitHub API. Token valid ~1 hour. |
| 8 | `setupGitCredentials` | 301–329 | `token: string, workDir: string` | `void` | Side-effect (fs write + execSync) | Creates workDir, configures git user globally, marks dir as safe, sets up host-specific credential store for `github.com`. |
| 9 | `setupCLILogins` | 339–393 | _(none)_ | `Promise<void>` | Side-effect (spawn) | Logs into ArgoCD and Kargo CLIs. Deduplicates via `_lastCLILoginTime` (30-min cooldown). Each login has 10s timeout. Failures are non-fatal (logged, resolved). |
| 10 | `setupGitHubTooling` | 402–451 | `token: string` | `void` | Side-effect (env + fs write) | Sets `GH_TOKEN` env var, configures GitHub MCP server in both `~/.gemini/settings.json` and `~/.claude/settings.json`. |
| 11 | `hasGitLabCredentials` | 456–458 | _(none)_ | `boolean` | Side-effect (fs read) | Checks if GitLab token file exists AND `GITLAB_HOST` is set. |
| 12 | `readGitLabToken` | 465–470 | _(none)_ | `string` | Side-effect (fs read) | Reads GitLab PAT from mounted secret path. Throws if missing. |
| 13 | `setupGitLabCredentials` | 478–495 | `token: string, workDir: string` | `void` | Side-effect (fs write + execFileSync) | Creates workDir, sets up host-specific credential store for GitLab host, disables SSL verify for internal GitLab. |
| 14 | `setupGitLabTooling` | 504–573 | `token: string` | `void` | Side-effect (env + fs + exec) | Sets `GITLAB_TOKEN` / `GITLAB_HOST` env vars, checks for `glab` binary, configures `skip_tls_verify`, writes GitLab MCP server config (`glab mcp serve`) into both `~/.gemini/settings.json` and `~/.claude/settings.json`. |
| 15 | `wsSend` | 578–582 | `ws: WebSocket, data: object` | `void` | Side-effect (WS send) | JSON-serializes and sends data only if socket is OPEN. |
| 16 | `readFindings` | 592–612 | `workDir: string` | `string \| null` | Side-effect (fs read + delete) | Reads `${workDir}/results/findings.md`, checks freshness (30s), deletes file after read. Returns null if missing, stale, or empty. |
| 17 | `stdoutFallback` | 627–637 | `effectiveOutput: string` | `string` | Pure | Returns the last 3000 chars of stdout as a fallback result. Prepends truncation notice if clipped. |
| 18 | `resolveResult` | 659–698 | `opts: {callbackResult, cachedFindings, findingsPath, workDir, autoApprove, effectiveOutput}` | `Promise<{output: string, source: string}>` | Side-effect (fs + spawn via retry) | **Single resolution function used by both `executeCLI` and `executeCLIStreaming`**. Priority chain: (1) callback → (2) cached findings → (3) disk findings → (4) retry via `requestFindings` → (5) stdout tail. |
| 19 | `requestFindings` | 709–743 | `workDir: string, autoApprove: boolean` | `Promise<string \| null>` | Side-effect (spawn) | Last-resort retry: spawns agent CLI with a prompt asking it to write `results/findings.md`. 60s timeout. Never rejects. |
| 20 | `prepareResultsDir` | 749–764 | `workDir: string` | `void` | Side-effect (fs) | Ensures `${workDir}/results/` exists and is empty (cleans stale files from crashed runs). |
| 21 | `executeCLI` | 769–878 | `prompt: string, options?: {autoApprove?, cwd?}` | `Promise<{status, exitCode?, output, source, stderr?}>` | Side-effect (spawn + fs.watch) | Spawns agent CLI (headless), accumulates stdout via `parseStreamLine`, sets up `fs.watch` on results dir, delegates result resolution to `resolveResult`. Used by HTTP `/execute` endpoint. |
| 22 | `executeCLIStreaming` | 883–1029 | `ws: WebSocket, eventId: string, prompt: string, options?: {autoApprove?, cwd?, sessionId?}` | `Promise<{status, sessionId?, output, source, exitCode?, stderr?}>` | Side-effect (spawn + WS + fs.watch) | Same as `executeCLI` but streams `progress` messages over WebSocket in real-time. Sets `currentTask`. Used by WS `task` and `followup` handlers. |
| 23 | `parseBody` | 1034–1047 | `req: http.IncomingMessage` | `Promise<object>` | Side-effect (stream read) | Buffers and JSON-parses HTTP request body. Rejects on invalid JSON. |
| 24 | `handleRequest` | 1052–1196 | `req: IncomingMessage, res: ServerResponse` | `Promise<void>` | Side-effect (HTTP handler) | Routes to `/health`, `/callback`, `/execute`, or 404. See §5 for endpoint details. |

---

## 2. Module-Level Mutable State

| Name | Type | Declared | Set By | Read By | Lifecycle |
|------|------|----------|--------|---------|-----------|
| `_callbackResult` | `string \| null` | L40 | `handleRequest` (POST `/callback`, type=result), reset to `null` at task start in both `/execute` handler and WS `task` handler | `executeCLI` close handler (captured as `capturedCallback`), `executeCLIStreaming` close handler (same), `resolveResult` (via param) | Reset to `null` before each task. Set when agent calls `sendResults`. Consumed (and nulled) when CLI process exits. |
| `_lastCLILoginTime` | `number` | L336 | `setupCLILogins` (set to `Date.now()` after successful login batch) | `setupCLILogins` (dedup check) | Starts at `0`. Updated after each successful ArgoCD/Kargo login round. Persists for process lifetime. |
| `currentTask` | `object \| null` | L1205 | `executeCLIStreaming` (L928: set to `{eventId, child}`), WS `task` handler (cleared L1292), WS `cancel` handler (cleared L1336), WS `close` handler (cleared L1355) | `executeCLIStreaming` stdout handler (sessionId write), `handleRequest` callback handler (read `eventId`, `ws`), WS `task`/`cancel`/`close` handlers, `parseStreamLine` consumers (sessionId write) | `null` when idle. Set to `{eventId, child}` when a CLI process is running. May also carry `.sessionId`, `.ws`, `.cwd` during WS execution. Cleared on task completion, cancellation, or WS disconnect. |
| `server` | `http.Server` | L1199 | `http.createServer(handleRequest)` | `server.listen()` (L1364), SIGTERM handler (L1388) | Created once at module load. Closed on SIGTERM. |
| `wss` | `WebSocket.Server` | L1202 | `new WebSocket.Server({server, path: '/ws'})` | `wss.on('connection', ...)` (L1207) | Created once at module load. Attached to HTTP server. |

### Note on `currentTask` shape

The `currentTask` object is loosely typed with these observed fields:

| Field | Type | Set Where | Used Where |
|-------|------|-----------|------------|
| `eventId` | `string` | `executeCLIStreaming` L928 | WS handlers, logging |
| `child` | `ChildProcess` | `executeCLIStreaming` L928 | WS `cancel` handler (`.kill()`), WS `close` handler (`.kill()`) |
| `sessionId` | `string \| undefined` | `parseStreamLine` consumers in stdout handler | `executeCLIStreaming` close handler (captured before clear), WS `result` message |
| `ws` | `WebSocket \| undefined` | **Not explicitly set** (missing — `currentTask.ws` is read in `/callback` handler L1095–1106 but never assigned) | `/callback` handler — forwards `partial_result` / `progress` |
| `cwd` | `string \| undefined` | **Not explicitly set** (read at L1306 in `followup` handler) | WS `followup` handler as fallback workDir |

> **Bug/Gap:** `currentTask.ws` and `currentTask.cwd` are read but never assigned. The `/callback` forward-to-WS path and the `followup` cwd fallback are dead code paths under current flow.

---

## 3. Constants & Env-Var-Derived Values

| Name | Line | Value / Source | Description |
|------|------|---------------|-------------|
| `PORT` | 25 | `process.env.PORT \|\| 9090` | HTTP + WS listen port |
| `ROLE_TIMEOUTS` | 26–32 | `{architect: 600000, sysadmin: 300000, developer: 900000, qe: 600000, default: 300000}` | Role-specific CLI timeout map (ms) |
| `TIMEOUT_MS` | 33 | `parseInt(process.env.TIMEOUT_MS) \|\| ROLE_TIMEOUTS[AGENT_ROLE] \|\| 300000` | Effective CLI process timeout |
| `FINDINGS_FRESHNESS_MS` | 34 | `30000` | Max age (ms) for `findings.md` to be considered fresh in `readFindings` |
| `DEFAULT_WORK_DIR` | 35 | `'/data/gitops'` | Default CWD for CLI execution |
| `AGENT_CLI` | 43 | `process.env.AGENT_CLI \|\| 'gemini'` | Which CLI binary to spawn (`gemini` or `claude`) |
| `AGENT_MODEL` | 44 | `process.env.AGENT_MODEL \|\| process.env.GEMINI_MODEL \|\| ''` | Model override for CLI |
| `ANSI_RE` | 48 | Regex | Pattern matching ANSI escape sequences |
| `AGENT_ROLE` | 51 | `process.env.AGENT_ROLE \|\| ''` | Agent role (architect, sysadmin, developer, qe) |
| `claudeDir` | 54 | `~/.claude` | Claude config directory |
| `claudeSettingsPath` | 56 | `~/.claude/settings.json` | Claude settings file |
| `geminiDir` | 64 | `~/.gemini` | Gemini config directory |
| `stagedRulesPath` | 67 | `'/tmp/agent-rules/GEMINI.md'` | Source path for agent rules (K8s ConfigMap mount) |
| `geminiSettingsPath` | 80 | `~/.gemini/settings.json` | Gemini settings file |
| `trustedFoldersPath` | 98 | `~/.gemini/trustedFolders.json` | Gemini trusted folders file |
| `SECRETS_PATH` | 219 | `'/secrets/github'` | GitHub App secrets mount path |
| `APP_ID_PATH` | 220 | `'/secrets/github/app-id'` | GitHub App ID file |
| `INSTALL_ID_PATH` | 221 | `'/secrets/github/installation-id'` | GitHub installation ID file |
| `PRIVATE_KEY_PATTERN` | 223 | `/\.pem$/` | Regex to find private key file |
| `GITLAB_SECRETS_PATH` | 226 | `'/secrets/gitlab'` | GitLab secrets mount path |
| `GITLAB_TOKEN_PATH` | 227 | `process.env.GITLAB_TOKEN_PATH \|\| '/secrets/gitlab/token'` | GitLab PAT file |
| `GITLAB_HOST` | 228 | `process.env.GITLAB_HOST \|\| ''` | GitLab hostname (e.g., `gitlab.example.com`) |
| `CLI_LOGIN_INTERVAL_MS` | 337 | `1800000` (30 min) | Cooldown between ArgoCD/Kargo re-login attempts |

### Env vars read at runtime (not captured as module constants)

| Env Var | Read Where | Purpose |
|---------|-----------|---------|
| `AGENT_PERMISSION_MODE` | `buildCLICommand` L182 | If `"plan"` → `--permission-mode plan` for Claude |
| `GOOGLE_GENAI_USE_VERTEXAI` | `executeCLI` L804, `executeCLIStreaming` L921, `requestFindings` L717 | Set to `'true'` in spawned Gemini env |
| `GOOGLE_APPLICATION_CREDENTIALS` | Inherited by child processes | ADC for Vertex AI auth |
| `GH_TOKEN` | Set by `setupGitHubTooling` L404 | Used by `gh` CLI |
| `GITLAB_TOKEN` | Set by `setupGitLabTooling` L506 | Used by `glab` CLI |
| `GIT_USER_NAME` | `setupGitCredentials` L311 | Git commit author name |
| `GIT_USER_EMAIL` | `setupGitCredentials` L312 | Git commit author email |
| `ARGOCD_SERVER` | `setupCLILogins` L348 | ArgoCD server address |
| `ARGOCD_INSECURE` | `setupCLILogins` L352 | If `'true'`, add `--insecure` to ArgoCD login |
| `KARGO_SERVER` | `setupCLILogins` L369 | Kargo server address |
| `KARGO_INSECURE` | `setupCLILogins` L373 | If `'true'`, add `--insecure-skip-tls-verify` |

---

## 4. External Dependencies

| Module | Import | Used For |
|--------|--------|----------|
| `http` | `require('http')` L17 | HTTP server (`createServer`, `handleRequest`) |
| `fs` | `require('fs')` L18 | File I/O (settings, secrets, findings, results dir) |
| `path` | `require('path')` L19 | Path construction (settings dirs) |
| `os` | `require('os')` L20 | `os.homedir()` for `~/.gemini` / `~/.claude` |
| `child_process` | `{ spawn, execSync, execFileSync }` L21 | Spawning CLI binaries, git config, ArgoCD/Kargo login, glab config |
| `jsonwebtoken` | `require('jsonwebtoken')` L22 | Signing JWT (RS256) for GitHub App authentication |
| `ws` | `require('ws')` L23 | WebSocket server + client state checks (`WebSocket.OPEN`) |

---

## 5. HTTP Endpoints

### `GET /health`

| Field | Value |
|-------|-------|
| Handler | `handleRequest` L1056–1074 |
| Response | `200 application/json` |
| Body | `{ status, service, cliType, cliModel, agentRole, toolRestrictions, hasGitHubCredentials, hasGitLabCredentials, hasArgocdCredentials, hasKargoCredentials, hasGitHubMCP, hasGitLabMCP, gitlabHost }` |

### `POST /callback`

| Field | Value |
|-------|-------|
| Handler | `handleRequest` L1077–1123 |
| Request body | `{ type?: "result" \| "message", content: string }` |
| Response | `200 { ok: true, type }` or `400 { error }` |
| Behavior (type=result) | Stores `content` in `_callbackResult`. Forwards as `partial_result` WS message if a task is active and `currentTask.ws` exists. |
| Behavior (type=message) | Forwards `content` as `progress` WS message with `source: 'agent_message'`. Does NOT overwrite `_callbackResult`. |

### `POST /execute`

| Field | Value |
|-------|-------|
| Handler | `handleRequest` L1126–1191 |
| Request body | `{ prompt: string, autoApprove?: boolean, cwd?: string }` |
| Concurrency | Returns `429 { error: 'Agent busy' }` if `currentTask` is set |
| Response (success) | `200 { status: 'success', exitCode, output, source }` |
| Response (failure) | `200 { status: 'failed', exitCode, stderr, stdout, source }` |
| Response (error) | `500 { status: 'error', message }` |
| Flow | Reset `_callbackResult` → GitHub creds → GitLab creds → ArgoCD/Kargo login → `executeCLI()` → JSON response |

---

## 6. WebSocket Message Types

### 6.1 Inbound (Brain → Sidecar)

#### `task`

```json
{
  "type": "task",
  "event_id": "string",
  "prompt": "string",
  "cwd": "string (optional, default /data/gitops)",
  "autoApprove": "boolean (optional, default false)",
  "session_id": "string | null (optional, for --resume)"
}
```

**Handler:** L1219–1292. Rejects with `busy` if `currentTask` is set. Resets `_callbackResult`. Sets up GitHub/GitLab credentials and MCP tooling. Calls `setupCLILogins()`. Delegates to `executeCLIStreaming()`. Sends `result` on completion.

#### `followup`

```json
{
  "type": "followup",
  "event_id": "string",
  "session_id": "string (required for --resume)",
  "message": "string"
}
```

**Handler:** L1294–1322. Calls `executeCLIStreaming()` with `sessionId` for `--resume`. Sends `result` on completion. Returns `error` if no `session_id`.

#### `cancel`

```json
{
  "type": "cancel"
}
```

**Handler:** L1324–1338. Sends SIGTERM to `currentTask.child`. Escalates to SIGKILL after 5 seconds. Clears `currentTask`.

### 6.2 Outbound (Sidecar → Brain)

#### `progress`

```json
{
  "type": "progress",
  "event_id": "string",
  "message": "string",
  "source": "string (optional, 'agent_message' when from /callback)"
}
```

Sent during streaming execution (each parsed line from CLI stdout) and for credential setup status messages.

#### `partial_result`

```json
{
  "type": "partial_result",
  "event_id": "string",
  "content": "string"
}
```

Sent when `/callback` receives a `type: "result"` while a WS task is active.

#### `result`

```json
{
  "type": "result",
  "event_id": "string",
  "session_id": "string | null",
  "status": "'success' | 'failed'",
  "output": "string | object",
  "source": "'callback' | 'findings' | 'stdout'"
}
```

Final result sent after CLI process exits and `resolveResult` completes.

#### `error`

```json
{
  "type": "error",
  "event_id": "string (optional)",
  "message": "string"
}
```

Sent on invalid JSON, missing prompt, spawn failure, or missing `session_id` for followup.

#### `busy`

```json
{
  "type": "busy",
  "event_id": "string",
  "message": "Agent busy, task rejected. One task at a time."
}
```

Sent when a `task` message arrives while `currentTask` is non-null.

---

## 7. Startup Sequence (Module Load Order)

| Order | Lines | What Happens |
|-------|-------|-------------|
| 1 | 17–23 | `require()` — load `http`, `fs`, `path`, `os`, `child_process`, `jsonwebtoken`, `ws` |
| 2 | 25–35 | Declare constants: `PORT`, `ROLE_TIMEOUTS`, `TIMEOUT_MS`, `FINDINGS_FRESHNESS_MS`, `DEFAULT_WORK_DIR` |
| 3 | 40 | Initialize `_callbackResult = null` |
| 4 | 43–51 | Declare CLI routing constants: `AGENT_CLI`, `AGENT_MODEL`, `ANSI_RE`, `AGENT_ROLE` |
| 5 | 54–60 | **Side-effect:** Create `~/.claude/` dir, write `settings.json` with `{theme:'dark', hasCompletedOnboarding:true}` (skip onboarding) — only if file doesn't exist |
| 6 | 64–65 | **Side-effect:** Create `~/.gemini/` dir |
| 7 | 67–79 | **Side-effect:** Copy agent rules from `/tmp/agent-rules/GEMINI.md` into both `~/.gemini/GEMINI.md` and `~/.claude/CLAUDE.md` (only if source exists and targets don't) |
| 8 | 80–95 | **Side-effect:** Read/create `~/.gemini/settings.json` — disable folder trust, preserve MCP servers |
| 9 | 98–111 | **Side-effect:** Write `~/.gemini/trustedFolders.json` — object mapping 5 `/data/gitops*` paths to `TRUST_FOLDER` |
| 10 | 128–175 | Declare functions: `parseStreamLine`, `parseClaudeStreamLine` |
| 11 | 181–209 | Declare function: `buildCLICommand` |
| 12 | 219–573 | Declare constants + functions: GitHub/GitLab credential and MCP tooling setup |
| 13 | 578–764 | Declare utility functions: `wsSend`, `readFindings`, `stdoutFallback`, `resolveResult`, `requestFindings`, `prepareResultsDir` |
| 14 | 769–1047 | Declare execution functions: `executeCLI`, `executeCLIStreaming`, `parseBody`, `handleRequest` |
| 15 | 1199 | **Side-effect:** `server = http.createServer(handleRequest)` |
| 16 | 1202 | **Side-effect:** `wss = new WebSocket.Server({server, path: '/ws'})` |
| 17 | 1205 | Initialize `currentTask = null` |
| 18 | 1207–1362 | Register WS `connection` event handler (which registers per-connection `message`, `close`, `error` handlers) |
| 19 | 1364–1383 | **Side-effect:** `server.listen(PORT, '0.0.0.0')` — starts accepting connections. Callback: logs startup info, calls `setupCLILogins()` (warm-up, async, non-blocking), starts `setInterval` for periodic CLI login refresh (every 30 min) |
| 20 | 1386–1389 | Register `process.on('SIGTERM')` handler — graceful shutdown via `server.close()` |

---

## 8. Execution Flows

### 8.1 HTTP `/execute` → `executeCLI()` → result

```
POST /execute { prompt, autoApprove?, cwd? }
│
├─ Guard: if currentTask → 429 "Agent busy"
├─ Reset _callbackResult = null
│
├─ Credential Setup (sequential):
│  ├─ GitHub: generateInstallationToken() → setupGitCredentials() → setupGitHubTooling()
│  ├─ GitLab: readGitLabToken() → setupGitLabCredentials() → setupGitLabTooling()
│  └─ CLI logins: setupCLILogins() (ArgoCD + Kargo, 30-min dedup)
│
├─ executeCLI(prompt, {autoApprove, cwd})
│  │
│  ├─ buildCLICommand(prompt, {autoApprove}) → {binary, args}
│  ├─ prepareResultsDir(cwd) — clean/create results/
│  ├─ fs.watch(results/) — preemptive read of findings.md into cachedFindings
│  │
│  ├─ spawn(binary, args, {env, cwd, timeout, stdio: [ignore, pipe, pipe]})
│  │
│  ├─ stdout.on('data'):
│  │  ├─ Accumulate raw stdout
│  │  ├─ parseStreamLine(line) for each complete line
│  │  ├─ Accumulate parsed text into streamTextAccum
│  │  └─ Extract sessionId → currentTask.sessionId
│  │
│  ├─ stderr.on('data'): accumulate stderr
│  │
│  └─ child.on('close', code):
│     ├─ Close fs.watch
│     ├─ effectiveOutput = streamTextAccum || stdout
│     │
│     ├─ if code === 0:
│     │  ├─ Try JSON.parse(effectiveOutput) → return structured output
│     │  └─ resolveResult({callbackResult, cachedFindings, findingsPath, workDir, autoApprove, effectiveOutput})
│     │     ├─ Priority 1: _callbackResult → source: "callback"
│     │     ├─ Priority 2: cachedFindings → source: "findings"
│     │     ├─ Priority 3: disk findings → source: "findings"
│     │     ├─ Priority 4: requestFindings() retry → source: "findings"
│     │     └─ Priority 5: stdoutFallback() → source: "stdout"
│     │
│     └─ if code !== 0:
│        └─ return {status: 'failed', exitCode, stderr, stdout}
│
└─ HTTP Response: 200 JSON {status, exitCode, output, source}
```

### 8.2 WS `task` → `executeCLIStreaming()` → streaming progress + result

```
WS message { type: "task", event_id, prompt, cwd?, autoApprove?, session_id? }
│
├─ Guard: if currentTask → send "busy" message, return
├─ Reset _callbackResult = null
│
├─ Credential Setup (same as HTTP, but sends WS progress for each step):
│  ├─ GitHub: generateInstallationToken() → setup → progress "GitHub credentials configured"
│  ├─ GitLab: readGitLabToken() → setup → progress "GitLab credentials configured"
│  └─ CLI logins: setupCLILogins()
│
├─ executeCLIStreaming(ws, eventId, prompt, {autoApprove, cwd, sessionId})
│  │
│  ├─ buildCLICommand(prompt, {autoApprove, sessionId}) → {binary, args}
│  ├─ prepareResultsDir(cwd) — clean/create results/
│  ├─ fs.watch(results/) — preemptive read of findings.md into cachedFindings
│  │
│  ├─ spawn(binary, args, {env, cwd, timeout, stdio: [ignore, pipe, pipe]})
│  ├─ currentTask = { eventId, child }
│  │
│  ├─ stdout.on('data'):
│  │  ├─ Accumulate raw stdout
│  │  ├─ Line-buffered: split on \n, keep partial line in buffer
│  │  ├─ For each complete line → parseStreamLine(line)
│  │  ├─ Extract sessionId → currentTask.sessionId
│  │  ├─ Accumulate parsed text into streamTextAccum
│  │  └─ ★ wsSend(ws, {type:'progress', event_id, message: text})
│  │
│  ├─ stderr.on('data'): accumulate stderr
│  │
│  └─ child.on('close', code):
│     ├─ Close fs.watch
│     ├─ Capture sessionId from currentTask (before it's cleared)
│     ├─ Flush remaining lineBuffer → parse + send final progress
│     ├─ effectiveOutput = streamTextAccum || stdout
│     │
│     ├─ if code === 0:
│     │  ├─ Try JSON.parse(effectiveOutput) → return structured output
│     │  └─ resolveResult(...) — same priority chain as HTTP path
│     │
│     └─ if code !== 0:
│        └─ return {status: 'failed', sessionId, exitCode, stderr, stdout}
│
├─ ★ wsSend(ws, {type:'result', event_id, session_id, status, output, source})
└─ currentTask = null
```

### 8.3 WS `followup` → `executeCLIStreaming()` (with `--resume`)

```
WS message { type: "followup", session_id, message, event_id }
│
├─ Guard: if !session_id → send error "No session_id for followup"
│
├─ executeCLIStreaming(ws, eventId, message, {autoApprove: true, cwd: currentTask?.cwd || DEFAULT_WORK_DIR, sessionId})
│  └─ (same flow as task, but buildCLICommand adds --resume <sessionId>)
│
├─ wsSend(ws, {type:'result', event_id, session_id, output, source})
└─ currentTask = null
```

### 8.4 WS `cancel` → SIGTERM/SIGKILL

```
WS message { type: "cancel" }
│
├─ if currentTask && currentTask.child:
│  ├─ child.kill('SIGTERM')
│  ├─ setTimeout(5000): if !child.killed → child.kill('SIGKILL')
│  └─ child.on('exit'): clearTimeout
└─ currentTask = null
```

### 8.5 WS Disconnect → Orphan Cleanup

```
ws.on('close'):
│
├─ if currentTask && currentTask.child:
│  ├─ Log "Killing orphaned process..."
│  ├─ child.kill('SIGTERM')
│  ├─ setTimeout(5000): if !child.killed → child.kill('SIGKILL')
│  └─ child.on('exit'): clearTimeout
└─ currentTask = null
```

### 8.6 `/callback` → `_callbackResult` / WS Forward

```
POST /callback { type?: "result"|"message", content: string }
│
├─ type === "result":
│  ├─ _callbackResult = content  (stored for resolveResult)
│  └─ if currentTask.ws → wsSend({type:'partial_result', event_id, content})
│
└─ type === "message":
   └─ if currentTask.ws → wsSend({type:'progress', event_id, message: content, source:'agent_message'})
```

---

## 9. Known Issues / Gaps (Pre-Refactor)

1. **`currentTask.ws` never assigned.** The `/callback` handler reads `currentTask.ws` (L1095, L1106) to forward messages via WS, but `executeCLIStreaming` only sets `{ eventId, child }` (L928). The WS forward path for `/callback` is effectively dead.

2. **`currentTask.cwd` never assigned.** The `followup` handler falls back to `currentTask?.cwd || DEFAULT_WORK_DIR` (L1306), but `cwd` is never stored on `currentTask`.

3. **No concurrency guard on `followup`.** Unlike `task`, the `followup` handler does not check `if (currentTask)` before spawning. A followup arriving while a task runs will overwrite `currentTask`.

4. **`readFindings` (L592) not used by main paths.** Both `executeCLI` and `executeCLIStreaming` use `resolveResult` which reads findings directly. `readFindings` with its freshness check is only defined but not called from the main execution paths (the freshness check in `resolveResult` path 3 reads directly without `readFindings`).

5. **`parseClaudeStreamLine` (L172) backward-compat wrapper.** Not called anywhere in this file. Exists for external consumers or legacy code.

---

_This document is the authoritative pre-refactor inventory. Every function, state variable, endpoint, message type, and execution path listed above must be accounted for in the post-refactor codebase._
