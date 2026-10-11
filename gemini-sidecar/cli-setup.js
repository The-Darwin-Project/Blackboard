// gemini-sidecar/cli-setup.js
// @ai-rules:
// 1. [Pattern]: Startup init — runs once at process start. Writes to ~/.claude and ~/.gemini.
// 2. [Constraint]: Idempotent — checks fs.existsSync before creating; skips overwrite of existing settings/rules.
// 3. [Gotcha]: Staged rules from /tmp/agent-rules/GEMINI.md copied to both CLI dirs; copyFileSync only when target missing.
// 4. [Pattern]: MCPs (TeamChat + Blackboard + Journal): agy -> ~/.gemini/config/mcp_config.json (via writeAgyMcpServer), Claude -> ~/.claude.json (via writeClaudeMcpServer). Hooks: agy -> ~/.gemini/config/hooks.json (command), Claude -> PreToolUse+Stop+SessionStart (HTTP to sidecar). PostToolUse is broken in Claude Code (github.com/anthropics/claude-code/issues/6305).
// 5. [Pattern]: filterSkillsByRole uses .disabled rename (re-entrant). swapActiveRules copies role-specific rules for dynamic switching.
// 7. [Pattern]: filterSkillsByMode renames non-matching skill dirs to .disabled per task; restoreAllSkills re-enables. Both ~/.gemini/skills and ~/.claude/skills updated in lockstep (Gemini first — Claude entries are symlinks).
// 8. [Constraint]: Empty mode ('') skips filtering entirely (backward compatible with legacy dispatches).
// 9. [Doc]: Skill vs MCP mode filtering (independent layers, same Brain `mode` on WS task):
//    - Skills: filterSkillsByMode — SKILL.md `modes:` frontmatter; skills without `modes:` stay enabled.
//    - MCP: team-chat-mcp.js notInModes on tools/list — e.g. message mode drops team_send_results + team_huddle.
//    - Stop hook: http-handler.js allows exit without team_send_results when task.mode === message.
//    Wake tryWake uses mode implement so pair-programming skills + full MCP apply.
// 10. [Constraint]: writeAgyMcpServer is a no-op unless AGENT_CLI === 'agy' (it writes a plaintext credential store).
//    Gate new agy writes there, not at call sites.

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');
const { AGENT_CLI } = require('./config');

/**
 * Resolve a command name to its absolute path via `which`.
 * In headless mode (-p), Claude Code's MCP server spawner may not inherit
 * the full PATH. Absolute paths prevent silent spawn failures.
 * Results are memoized -- `which` is called at most once per binary name.
 */
const _resolvedPaths = new Map();
function resolveCommand(name) {
    if (_resolvedPaths.has(name)) return _resolvedPaths.get(name);
    let resolved = name;
    try {
        resolved = execFileSync('which', [name], { encoding: 'utf8' }).trim();
    } catch {
        console.warn(`resolveCommand: '${name}' not found in PATH, using relative`);
    }
    _resolvedPaths.set(name, resolved);
    return resolved;
}

const CLAUDE_JSON_PATH = path.join(os.homedir(), '.claude.json');
const AGY_MCP_PATH = path.join(os.homedir(), '.gemini', 'config', 'mcp_config.json');
const AGY_HOOKS_PATH = path.join(os.homedir(), '.gemini', 'config', 'hooks.json');

/**
 * Write an MCP server config into ~/.claude.json (the file Claude Code reads).
 * Read-modify-write: preserves existing keys (userID, skillUsage, etc.).
 * NOT atomic -- callers must be sequential (no concurrent writes).
 * Safe in Node.js single-thread when callers don't yield between read and write.
 * @param {string} name - Server name (e.g. 'TeamChat', 'GitHub')
 * @param {object} config - { command, args, env }
 */
function writeClaudeMcpServer(name, config) {
    if (name === '__proto__' || name === 'constructor') return;
    const dir = path.dirname(CLAUDE_JSON_PATH);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

    let data = {};
    if (fs.existsSync(CLAUDE_JSON_PATH)) {
        try { data = JSON.parse(fs.readFileSync(CLAUDE_JSON_PATH, 'utf8')); } catch { /* fresh */ }
    }
    data.mcpServers = data.mcpServers || {};
    data.mcpServers[name] = config;

    const tmpPath = `${CLAUDE_JSON_PATH}.tmp.${process.pid}`;
    fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2), { mode: 0o600 });
    fs.renameSync(tmpPath, CLAUDE_JSON_PATH);
    try { fs.chmodSync(CLAUDE_JSON_PATH, 0o600); } catch { /* ignore */ }
}

/**
 * Write an MCP server config into ~/.gemini/config/mcp_config.json (the file agy reads).
 * Read-modify-write: preserves existing keys.
 * Uses 0o600 mode permissions and atomic write via temporary file.
 * @param {string} name - Server name (e.g. 'TeamChat', 'GitHub')
 * @param {object} config - { command, args, env }
 */
function writeAgyMcpServer(name, config) {
    if (name === '__proto__' || name === 'constructor') return;
    // Single chokepoint for every agy MCP write (cli-setup + all credentials.js call sites):
    // this file holds GitHub/GitLab/ArgoCD/Jenkins/K8s credentials in plaintext, so a claude or
    // gemini sidecar must not create it at all.
    if (AGENT_CLI !== 'agy') return;
    const agyMcpPath = AGY_MCP_PATH;
    const dir = path.dirname(agyMcpPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
    try { fs.chmodSync(dir, 0o700); } catch { /* ignore */ }

    let data = {};
    if (fs.existsSync(agyMcpPath)) {
        try { data = JSON.parse(fs.readFileSync(agyMcpPath, 'utf8')); } catch { /* fresh */ }
    }
    data.mcpServers = data.mcpServers || {};
    data.mcpServers[name] = config;

    const tmpPath = `${agyMcpPath}.tmp.${process.pid}`;
    fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2), { mode: 0o600 });
    fs.renameSync(tmpPath, agyMcpPath);

    try {
        const fallbackDir = path.join(os.homedir(), '.gemini', 'antigravity');
        const fallbackLink = path.join(fallbackDir, 'mcp_config.json');
        if (fs.existsSync(fallbackDir)) {
            try {
                const stat = fs.lstatSync(fallbackLink);
                if (stat.isSymbolicLink()) {
                    const target = fs.readlinkSync(fallbackLink);
                    if (target !== agyMcpPath) {
                        fs.unlinkSync(fallbackLink);
                        fs.symlinkSync(agyMcpPath, fallbackLink);
                    }
                } else {
                    fs.unlinkSync(fallbackLink);
                    fs.symlinkSync(agyMcpPath, fallbackLink);
                }
            } catch (e) {
                if (e.code === 'ENOENT') {
                    try { fs.symlinkSync(agyMcpPath, fallbackLink); } catch { /* ignore */ }
                }
            }
        }
    } catch { /* ignore */ }
}

/**
 * Write hooks for Antigravity (agy) CLI into ~/.gemini/config/hooks.json.
 * Provides defense-in-depth:
 * - PreToolUse hook for validate-mutations.sh (merge-approval guard for all roles, mutation denylist for read-only roles)
 * - Stop hook for require-results.sh (ensures team_send_results is called before exiting)
 */
function writeAgyHooks(hooksDir = process.env.AGY_HOOKS_DIR || '/app/hooks') {
    if (AGENT_CLI !== 'agy') return;
    const agyHooksPath = AGY_HOOKS_PATH;
    const dir = path.dirname(agyHooksPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
    try { fs.chmodSync(dir, 0o700); } catch { /* ignore */ }

    let data = {};
    if (fs.existsSync(agyHooksPath)) {
        try { data = JSON.parse(fs.readFileSync(agyHooksPath, 'utf8')); } catch { /* fresh start */ }
    }

    const validateHook = path.join(hooksDir, 'validate-mutations.sh');
    const requireHook = path.join(hooksDir, 'require-results.sh');
    const clusterHook = path.join(hooksDir, 'cluster-context.sh');
    const inboxHook = path.join(hooksDir, 'check-inbox.sh');

    data['validate-mutations'] = {
        PreToolUse: [
            {
                matcher: '*',
                hooks: [
                    {
                        name: 'validate-mutations',
                        type: 'command',
                        command: validateHook,
                        timeout: 8,
                        description: 'Block shell mutations for read-only roles and enforce merge-approval guard',
                    },
                ],
            },
        ],
    };
    data['require-results'] = {
        Stop: [
            {
                name: 'require-results',
                type: 'command',
                command: requireHook,
                timeout: 5,
                description: 'Block exit if team_send_results not called',
            },
        ],
    };
    data['cluster-context'] = {
        SessionStart: [
            {
                matcher: '*',
                hooks: [
                    {
                        name: 'cluster-context',
                        type: 'command',
                        command: clusterHook,
                        timeout: 5,
                        description: 'Inject cluster context at session start',
                    },
                ],
            },
        ],
    };
    data['team-inbox'] = {
        SessionStart: [
            {
                matcher: '*',
                hooks: [
                    {
                        name: 'team-inbox-start',
                        type: 'command',
                        command: inboxHook,
                        timeout: 5,
                        description: 'Check team inbox at session start',
                    },
                ],
            },
        ],
        PostToolUse: [
            {
                matcher: '*',
                hooks: [
                    {
                        name: 'team-inbox',
                        type: 'command',
                        command: inboxHook,
                        timeout: 5,
                        description: 'Check team inbox after tool use',
                    },
                ],
            },
        ],
    };

    const tmpPath = `${agyHooksPath}.tmp.${process.pid}`;
    fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2), { mode: 0o600 });
    fs.renameSync(tmpPath, agyHooksPath);
    try { fs.chmodSync(agyHooksPath, 0o600); } catch { /* ignore */ }
}

/**
 * Register TeamChat MCP server + inbox hooks into a CLI settings object.
 * @param {object} settings - The settings object to modify (claude or agy)
 * @param {string} cli - 'claude' or 'agy'
 */
function registerMCPsAndHooks(settings, cli) {
    const role = process.env.AGENT_ROLE || '';
    const port = process.env.PORT || '9090';
    const peerPort = process.env.PEER_SIDECAR_PORT || '';
    const nodeCmd = resolveCommand('node');

    const teamChatConfig = {
        command: nodeCmd, args: ['/app/team-chat-mcp.js'],
        env: { AGENT_ROLE: role, SIDECAR_PORT: port, AGENT_CLI: cli, PEER_PORT: peerPort },
    };
    const blackboardConfig = {
        command: nodeCmd, args: ['/app/blackboard-mcp.js'],
        env: { SIDECAR_PORT: port, AGENT_ROLE: role },
    };
    const journalConfig = {
        command: nodeCmd, args: ['/app/journal-mcp.js'],
        env: { SIDECAR_PORT: port },
    };

    const playwrightCmd = resolveCommand('playwright-mcp');
    const playwrightConfig = {
        command: playwrightCmd,
        args: ['--headless', '--no-sandbox'],
    };

    if (cli === 'agy') {
        writeAgyMcpServer('TeamChat', teamChatConfig);
        writeAgyMcpServer('DarwinBlackboard', blackboardConfig);
        writeAgyMcpServer('DarwinJournal', journalConfig);
        writeAgyMcpServer('Playwright', playwrightConfig);
        writeAgyHooks();
        console.log(`MCPs (TeamChat + Blackboard + Journal) + hooks registered for agy (role=${role}, peer=${peerPort || 'none'})`);
        return;
    }

    writeClaudeMcpServer('TeamChat', teamChatConfig);
    writeClaudeMcpServer('DarwinBlackboard', blackboardConfig);
    writeClaudeMcpServer('DarwinJournal', journalConfig);
    writeClaudeMcpServer('Playwright', playwrightConfig);

    settings.hooks = settings.hooks || {};
    const hookUrl = `http://localhost:${port}`;
    settings.hooks.PreToolUse = [{ matcher: '', hooks: [{ type: 'http', url: `${hookUrl}/hooks/pre-tool-use`, timeout: 5 }] }];
    settings.hooks.Stop = [{ hooks: [{ type: 'http', url: `${hookUrl}/hooks/stop`, timeout: 5 }] }];
    settings.hooks.SessionStart = [{ matcher: '', hooks: [{ type: 'http', url: `${hookUrl}/hooks/session-start`, timeout: 10 }] }];
    console.log(`MCPs (TeamChat + Blackboard + Journal) + hooks registered for ${cli} (role=${role}, peer=${peerPort || 'none'})`);
}

/**
 * Initialize CLI settings at startup:
 * - Claude settings.json (~/.claude/settings.json) to skip onboarding
 * - Copy agent rules from /tmp/agent-rules/GEMINI.md to ~/.gemini/GEMINI.md and ~/.claude/CLAUDE.md
 */
function initializeCLISettings() {
    const claudeDir = path.join(os.homedir(), '.claude');
    fs.mkdirSync(claudeDir, { recursive: true });
    const claudeSettingsPath = path.join(claudeDir, 'settings.json');
    if (!fs.existsSync(claudeSettingsPath)) {
        fs.writeFileSync(claudeSettingsPath, JSON.stringify({ theme: 'dark', hasCompletedOnboarding: true }));
        console.log('Claude settings.json created (skip onboarding)');
    }

    const geminiDir = path.join(os.homedir(), '.gemini');
    fs.mkdirSync(geminiDir, { recursive: true });
    // Copy agent rules from staging mount into writable CLI dirs so save_memory can append
    const stagedRulesPath = '/tmp/agent-rules/GEMINI.md';
    if (fs.existsSync(stagedRulesPath)) {
        const geminiRulesPath = path.join(geminiDir, 'GEMINI.md');
        if (!fs.existsSync(geminiRulesPath)) {
            fs.copyFileSync(stagedRulesPath, geminiRulesPath);
            console.log(`Agent rules copied: ${stagedRulesPath} -> ${geminiRulesPath}`);
        }
        const claudeRulesPath = path.join(claudeDir, 'CLAUDE.md');
        if (!fs.existsSync(claudeRulesPath)) {
            fs.copyFileSync(stagedRulesPath, claudeRulesPath);
            console.log(`Agent rules copied: ${stagedRulesPath} -> ${claudeRulesPath}`);
        }
    }

    // Update Claude settings with TeamChat hooks (MCP goes to ~/.claude.json via writeClaudeMcpServer)
    try {
        let claudeSettings = {};
        if (fs.existsSync(claudeSettingsPath)) {
            try { claudeSettings = JSON.parse(fs.readFileSync(claudeSettingsPath, 'utf8')); } catch { /* fresh start */ }
        }
        registerMCPsAndHooks(claudeSettings, 'claude');
        fs.writeFileSync(claudeSettingsPath, JSON.stringify(claudeSettings, null, 2));
        console.log('Claude settings.json updated (MCPs + HTTP hooks registered)');
    } catch (err) {
        console.error(`Claude TeamChat registration error: ${err.message}`);
    }
    // Antigravity (agy) MCP registration (MCP goes to ~/.gemini/config/mcp_config.json via writeAgyMcpServer)
    // Only for AGENT_CLI=agy sidecars -- see the credential note on writeAgyMcpServer.
    if (AGENT_CLI === 'agy') {
        try {
            registerMCPsAndHooks({}, 'agy');
        } catch (err) {
            console.error(`agy MCP registration error: ${err.message}`);
        }
    }

    filterSkillsByRole((process.env.AGENT_ROLE || '').toLowerCase());
}

const AGY_SKILLS_DIR = path.join(os.homedir(), '.gemini', 'skills');
const GEMINI_SKILLS_DIR = AGY_SKILLS_DIR;
const CLAUDE_SKILLS_DIR = path.join(os.homedir(), '.claude', 'skills');
const DISABLED_SUFFIX = '.disabled';

function safeRename(src, dest) {
    try {
        fs.renameSync(src, dest);
    } catch (err) {
        if (err.code === 'EXDEV') {
            fs.cpSync(src, dest, { recursive: true });
            fs.rmSync(src, { recursive: true, force: true });
        } else {
            throw err;
        }
    }
}

/**
 * Hide skills that don't match a role by renaming dirs to *.disabled.
 * Re-entrant: calls restoreAllSkills() first so role switches work cleanly.
 * @param {string} role - lowercase role name. Empty string skips filtering.
 */
function filterSkillsByRole(role) {
    if (!role) return;
    restoreAllSkills();
    if (!fs.existsSync(AGY_SKILLS_DIR)) return;

    let kept = 0, disabled = 0;
    for (const entry of fs.readdirSync(AGY_SKILLS_DIR)) {
        if (entry.endsWith(DISABLED_SUFFIX)) continue;
        const skillMd = path.join(AGY_SKILLS_DIR, entry, 'SKILL.md');
        if (!fs.existsSync(skillMd)) continue;

        const head = fs.readFileSync(skillMd, 'utf8').slice(0, 500);
        const match = head.match(/^roles:\s*\[([^\]]*)\]/m);
        if (!match) { kept++; continue; }

        const roles = match[1].split(',').map(r => r.trim().toLowerCase());
        if (roles.includes(role)) { kept++; continue; }

        safeRename(
            path.join(AGY_SKILLS_DIR, entry),
            path.join(AGY_SKILLS_DIR, entry + DISABLED_SUFFIX),
        );
        const claudeEntry = path.join(CLAUDE_SKILLS_DIR, entry);
        if (fs.existsSync(claudeEntry)) {
            safeRename(claudeEntry, claudeEntry + DISABLED_SUFFIX);
        }
        disabled++;
    }
    if (disabled > 0) {
        console.log(`Skills filtered for role '${role}': ${kept} kept, ${disabled} disabled`);
    }
}

/**
 * Copy role-specific rules file to the active CLI config locations.
 * Source: /tmp/agent-rules/{role}.md (full ConfigMap mount for ephemeral agents).
 * No-op for local sidecars where /tmp/agent-rules/GEMINI.md is already mounted as subPath.
 * @param {string} role - lowercase role name
 */
function swapActiveRules(role) {
    const sourceFile = `/tmp/agent-rules/${role}.md`;
    if (!fs.existsSync(sourceFile)) return;
    const geminiTarget = path.join(os.homedir(), '.gemini', 'GEMINI.md');
    const claudeTarget = path.join(os.homedir(), '.claude', 'CLAUDE.md');
    fs.copyFileSync(sourceFile, geminiTarget);
    fs.copyFileSync(sourceFile, claudeTarget);
    console.log(`Rules swapped to ${role}: ${sourceFile}`);
}

/**
 * Hide skills that don't match the current task mode by renaming dirs to *.disabled.
 * Reads `modes: [...]` from each SKILL.md frontmatter.
 * Skills WITHOUT a `modes:` field load in all modes (backward compatible).
 * Empty mode ('') skips filtering entirely.
 * Renames in both Antigravity (~/.gemini/skills) and Claude skill dirs (Claude entries are symlinks).
 *
 * See @ai-rules item 9 (Skill vs MCP matrix). MCP filtering is separate in team-chat-mcp.js.
 */
function filterSkillsByMode(mode) {
    if (!mode) return;
    if (!fs.existsSync(AGY_SKILLS_DIR)) return;

    let disabled = 0, active = 0;
    for (const entry of fs.readdirSync(AGY_SKILLS_DIR)) {
        if (entry.endsWith(DISABLED_SUFFIX)) continue;
        const skillMd = path.join(AGY_SKILLS_DIR, entry, 'SKILL.md');
        if (!fs.existsSync(skillMd)) continue;

        const head = fs.readFileSync(skillMd, 'utf8').slice(0, 500);
        const match = head.match(/^modes:\s*\[([^\]]*)\]/m);
        if (!match) { active++; continue; }

        const modes = match[1].split(',').map(m => m.trim().toLowerCase());
        if (modes.includes(mode.toLowerCase())) { active++; continue; }

        safeRename(
            path.join(AGY_SKILLS_DIR, entry),
            path.join(AGY_SKILLS_DIR, entry + DISABLED_SUFFIX),
        );
        const claudeEntry = path.join(CLAUDE_SKILLS_DIR, entry);
        if (fs.existsSync(claudeEntry)) {
            safeRename(claudeEntry, claudeEntry + DISABLED_SUFFIX);
        }
        disabled++;
    }
    if (disabled > 0) {
        console.log(`Skills filtered for mode '${mode}': ${disabled} disabled, ${active} active`);
    }
}

/**
 * Restore all *.disabled skill dirs back to their original names.
 * Processes Antigravity first so symlink targets exist when Claude entries are restored.
 * Idempotent — safe to call when no .disabled dirs exist.
 */
function restoreAllSkills() {
    let restored = 0;
    for (const dir of [AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR]) {
        if (!fs.existsSync(dir)) continue;
        for (const entry of fs.readdirSync(dir)) {
            if (!entry.endsWith(DISABLED_SUFFIX)) continue;
            const baseName = entry.slice(0, -DISABLED_SUFFIX.length);
            safeRename(path.join(dir, entry), path.join(dir, baseName));
            if (dir === AGY_SKILLS_DIR) restored++;
        }
    }
    if (restored > 0) {
        console.log(`Skills restored: ${restored} re-enabled`);
    }
}

module.exports = { initializeCLISettings, resolveCommand, writeClaudeMcpServer, writeAgyMcpServer, writeAgyHooks, registerMCPsAndHooks, filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills, AGY_SKILLS_DIR, GEMINI_SKILLS_DIR };
