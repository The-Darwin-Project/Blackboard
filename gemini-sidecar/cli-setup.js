// gemini-sidecar/cli-setup.js
// @ai-rules:
// 1. [Pattern]: Startup init — runs once at process start. Writes to ~/.claude and ~/.gemini.
// 2. [Constraint]: Idempotent — checks fs.existsSync before creating; skips overwrite of existing settings/rules.
// 3. [Gotcha]: Staged rules from /tmp/agent-rules/GEMINI.md copied to both CLI dirs; copyFileSync only when target missing.
// 4. [Gotcha]: trustedFolders.json uses object format (path -> trust level), not array; invalid format causes CLI warnings.
// 5. [Pattern]: filterSkillsByRole uses .disabled rename (re-entrant). swapActiveRules copies role-specific rules for dynamic switching.
// 6. [Pattern]: MCPs (TeamChat + Blackboard + Journal): Gemini -> settings.json, Claude -> ~/.claude.json (via writeClaudeMcpServer). Hooks: Gemini AfterTool (command), Claude PostToolUse+Stop+SessionStart (HTTP to sidecar).
// 7. [Pattern]: filterSkillsByMode renames non-matching skill dirs to .disabled per task; restoreAllSkills re-enables. Both ~/.gemini/skills and ~/.claude/skills updated in lockstep (Gemini first — Claude entries are symlinks).
// 8. [Constraint]: Empty mode ('') skips filtering entirely (backward compatible with legacy dispatches).

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');

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

/**
 * Write an MCP server config into ~/.claude.json (the file Claude Code reads).
 * Read-modify-write: preserves existing keys (userID, skillUsage, etc.).
 * NOT atomic -- callers must be sequential (no concurrent writes).
 * Safe in Node.js single-thread when callers don't yield between read and write.
 * @param {string} name - Server name (e.g. 'TeamChat', 'GitHub')
 * @param {object} config - { command, args, env }
 */
function writeClaudeMcpServer(name, config) {
    let data = {};
    if (fs.existsSync(CLAUDE_JSON_PATH)) {
        try { data = JSON.parse(fs.readFileSync(CLAUDE_JSON_PATH, 'utf8')); } catch { /* fresh */ }
    }
    data.mcpServers = data.mcpServers || {};
    data.mcpServers[name] = config;
    fs.writeFileSync(CLAUDE_JSON_PATH, JSON.stringify(data, null, 2));
}

/**
 * Register TeamChat MCP server + inbox hooks into a CLI settings object.
 * @param {object} settings - The settings object to modify (gemini or claude)
 * @param {string} cli - 'gemini' or 'claude'
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

    if (cli === 'gemini') {
        settings.mcpServers = settings.mcpServers || {};
        settings.mcpServers.TeamChat = teamChatConfig;
        settings.mcpServers.DarwinBlackboard = blackboardConfig;
        settings.mcpServers.DarwinJournal = journalConfig;
    } else {
        writeClaudeMcpServer('TeamChat', teamChatConfig);
        writeClaudeMcpServer('DarwinBlackboard', blackboardConfig);
        writeClaudeMcpServer('DarwinJournal', journalConfig);
    }

    settings.hooks = settings.hooks || {};
    if (cli === 'gemini') {
        settings.hooks.AfterTool = settings.hooks.AfterTool || [];
        if (!settings.hooks.AfterTool.some(h => h.hooks?.some(hh => hh.name === 'team-inbox'))) {
            settings.hooks.AfterTool.push({
                matcher: '*',
                hooks: [{ name: 'team-inbox', type: 'command',
                           command: '/app/hooks/check-inbox.sh', timeout: 2000,
                           description: 'Check for pending team messages and blackboard turns after each tool call' }],
            });
        }
        settings.hooks.SessionStart = settings.hooks.SessionStart || [];
        if (!settings.hooks.SessionStart.some(h => h.hooks?.some(hh => hh.name === 'team-inbox-reinject'))) {
            settings.hooks.SessionStart.push({
                matcher: 'compact',
                hooks: [{ name: 'team-inbox-reinject', type: 'command',
                           command: '/app/hooks/check-inbox.sh', timeout: 2000 }],
            });
        }
    } else {
        const hookUrl = `http://localhost:${port}`;
        settings.hooks.PostToolUse = [{ matcher: '', hooks: [{ type: 'http', url: `${hookUrl}/hooks/post-tool-use`, timeout: 5 }] }];
        settings.hooks.Stop = [{ hooks: [{ type: 'http', url: `${hookUrl}/hooks/stop`, timeout: 5 }] }];
        settings.hooks.SessionStart = [{ matcher: 'compact', hooks: [{ type: 'http', url: `${hookUrl}/hooks/session-start`, timeout: 10 }] }];
    }
    console.log(`MCPs (TeamChat + Blackboard + Journal) + hooks registered for ${cli} (role=${role}, peer=${peerPort || 'none'})`);
}

/**
 * Initialize CLI settings at startup:
 * - Claude settings.json (~/.claude/settings.json) to skip onboarding
 * - Gemini settings.json (~/.gemini/settings.json) with trust disabled and MCP servers
 * - Gemini trustedFolders.json
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

    // Pre-create Gemini settings. Trust is disabled so the trust dialog never appears.
    // Auth is handled by env vars in headless mode (no interactive wizard needed).
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
    const geminiSettingsPath = path.join(geminiDir, 'settings.json');
    try {
        let geminiSettings = {};
        if (fs.existsSync(geminiSettingsPath)) {
            try { geminiSettings = JSON.parse(fs.readFileSync(geminiSettingsPath, 'utf8')); } catch { /* fresh start */ }
        }
        // Disable trust folder prompt (all agent working dirs are safe)
        geminiSettings.security = geminiSettings.security || {};
        geminiSettings.security.folderTrust = { enabled: false };
        // Preserve any existing MCP server configs
        geminiSettings.mcpServers = geminiSettings.mcpServers || {};
        registerMCPsAndHooks(geminiSettings, 'gemini');
        fs.writeFileSync(geminiSettingsPath, JSON.stringify(geminiSettings, null, 2));
        console.log('Gemini settings.json created (trust disabled, MCPs + hooks registered)');
    } catch (err) {
        console.error(`Gemini settings.json error: ${err.message}`);
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
    // Trusted folders: JSON object format (path -> trust level), not array.
    // Even with trust disabled, an invalid file causes a warning on every run.
    const trustedFoldersPath = path.join(geminiDir, 'trustedFolders.json');
    try {
        const trustedFolders = {
            '/data/gitops': 'TRUST_FOLDER',
            '/data/gitops-architect': 'TRUST_FOLDER',
            '/data/gitops-sysadmin': 'TRUST_FOLDER',
            '/data/gitops-developer': 'TRUST_FOLDER',
            '/data/gitops-qe': 'TRUST_FOLDER',
            '/data/workspace': 'TRUST_FOLDER',
        };
        fs.writeFileSync(trustedFoldersPath, JSON.stringify(trustedFolders, null, 2));
        console.log('Gemini trustedFolders.json created (object format)');
    } catch (err) {
        console.error(`Gemini trustedFolders.json error: ${err.message}`);
    }

    filterSkillsByRole((process.env.AGENT_ROLE || '').toLowerCase());
}

/**
 * Hide skills that don't match a role by renaming dirs to *.disabled.
 * Re-entrant: calls restoreAllSkills() first so role switches work cleanly.
 * @param {string} role - lowercase role name. Empty string skips filtering.
 */
function filterSkillsByRole(role) {
    if (!role) return;
    restoreAllSkills();
    if (!fs.existsSync(GEMINI_SKILLS_DIR)) return;

    let kept = 0, disabled = 0;
    for (const entry of fs.readdirSync(GEMINI_SKILLS_DIR)) {
        if (entry.endsWith(DISABLED_SUFFIX)) continue;
        const skillMd = path.join(GEMINI_SKILLS_DIR, entry, 'SKILL.md');
        if (!fs.existsSync(skillMd)) continue;

        const head = fs.readFileSync(skillMd, 'utf8').slice(0, 500);
        const match = head.match(/^roles:\s*\[([^\]]*)\]/m);
        if (!match) { kept++; continue; }

        const roles = match[1].split(',').map(r => r.trim().toLowerCase());
        if (roles.includes(role)) { kept++; continue; }

        safeRename(
            path.join(GEMINI_SKILLS_DIR, entry),
            path.join(GEMINI_SKILLS_DIR, entry + DISABLED_SUFFIX),
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

const GEMINI_SKILLS_DIR = path.join(os.homedir(), '.gemini', 'skills');
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
 * Hide skills that don't match the current task mode by renaming dirs to *.disabled.
 * Reads `modes: [...]` from each SKILL.md frontmatter.
 * Skills WITHOUT a `modes:` field load in all modes (backward compatible).
 * Empty mode ('') skips filtering entirely.
 * Renames in both Gemini and Claude skill dirs (Claude entries are symlinks).
 */
function filterSkillsByMode(mode) {
    if (!mode) return;
    if (!fs.existsSync(GEMINI_SKILLS_DIR)) return;

    let disabled = 0, active = 0;
    for (const entry of fs.readdirSync(GEMINI_SKILLS_DIR)) {
        if (entry.endsWith(DISABLED_SUFFIX)) continue;
        const skillMd = path.join(GEMINI_SKILLS_DIR, entry, 'SKILL.md');
        if (!fs.existsSync(skillMd)) continue;

        const head = fs.readFileSync(skillMd, 'utf8').slice(0, 500);
        const match = head.match(/^modes:\s*\[([^\]]*)\]/m);
        if (!match) { active++; continue; }

        const modes = match[1].split(',').map(m => m.trim().toLowerCase());
        if (modes.includes(mode.toLowerCase())) { active++; continue; }

        safeRename(
            path.join(GEMINI_SKILLS_DIR, entry),
            path.join(GEMINI_SKILLS_DIR, entry + DISABLED_SUFFIX),
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
 * Processes Gemini first so symlink targets exist when Claude entries are restored.
 * Idempotent — safe to call when no .disabled dirs exist.
 */
function restoreAllSkills() {
    let restored = 0;
    for (const dir of [GEMINI_SKILLS_DIR, CLAUDE_SKILLS_DIR]) {
        if (!fs.existsSync(dir)) continue;
        for (const entry of fs.readdirSync(dir)) {
            if (!entry.endsWith(DISABLED_SUFFIX)) continue;
            const baseName = entry.slice(0, -DISABLED_SUFFIX.length);
            safeRename(path.join(dir, entry), path.join(dir, baseName));
            if (dir === GEMINI_SKILLS_DIR) restored++;
        }
    }
    if (restored > 0) {
        console.log(`Skills restored: ${restored} re-enabled`);
    }
}

module.exports = { initializeCLISettings, resolveCommand, writeClaudeMcpServer, filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills };
