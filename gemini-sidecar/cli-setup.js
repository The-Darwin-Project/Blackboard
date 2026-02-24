// gemini-sidecar/cli-setup.js
// @ai-rules:
// 1. [Pattern]: Startup init — runs once at process start. Writes to ~/.claude and ~/.gemini.
// 2. [Constraint]: Idempotent — checks fs.existsSync before creating; skips overwrite of existing settings/rules.
// 3. [Gotcha]: Staged rules from /tmp/agent-rules/GEMINI.md copied to both CLI dirs; copyFileSync only when target missing.
// 4. [Gotcha]: trustedFolders.json uses object format (path -> trust level), not array; invalid format causes CLI warnings.
// 5. [Pattern]: filterSkillsByRole reads YAML frontmatter `roles:` from each SKILL.md and removes skills not matching AGENT_ROLE.
// 6. [Pattern]: TeamChat MCP: Gemini -> settings.json, Claude -> ~/.claude.json (via writeClaudeMcpServer). Hooks: Gemini AfterTool, Claude PreToolUse (both in settings.json).

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
function registerTeamChat(settings, cli) {
    const role = process.env.AGENT_ROLE || '';
    const port = process.env.PORT || '9090';
    const peerPort = process.env.PEER_SIDECAR_PORT || '';

    const mcpConfig = {
        command: resolveCommand('node'), args: ['/app/team-chat-mcp.js'],
        env: { AGENT_ROLE: role, SIDECAR_PORT: port, AGENT_CLI: cli, PEER_PORT: peerPort },
    };
    if (cli === 'gemini') {
        settings.mcpServers = settings.mcpServers || {};
        settings.mcpServers.TeamChat = mcpConfig;
    } else {
        writeClaudeMcpServer('TeamChat', mcpConfig);
    }

    settings.hooks = settings.hooks || {};
    if (cli === 'gemini') {
        settings.hooks.AfterTool = settings.hooks.AfterTool || [];
        if (!settings.hooks.AfterTool.some(h => h.hooks?.some(hh => hh.name === 'team-inbox'))) {
            settings.hooks.AfterTool.push({
                matcher: '*',
                hooks: [{ name: 'team-inbox', type: 'command',
                           command: '/app/hooks/check-inbox.sh', timeout: 2000,
                           description: 'Check for pending team messages after each tool call' }],
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
        settings.hooks.PreToolUse = settings.hooks.PreToolUse || [];
        if (!settings.hooks.PreToolUse.some(h => h.hooks?.some(hh => hh.command === '/app/hooks/check-inbox.sh'))) {
            settings.hooks.PreToolUse.push({
                matcher: '',
                hooks: [{ type: 'command', command: '/app/hooks/check-inbox.sh' }],
            });
        }
        settings.hooks.SessionStart = settings.hooks.SessionStart || [];
        if (!settings.hooks.SessionStart.some(h => h.hooks?.some(hh => hh.command === '/app/hooks/check-inbox.sh'))) {
            settings.hooks.SessionStart.push({
                matcher: 'compact',
                hooks: [{ type: 'command', command: '/app/hooks/check-inbox.sh' }],
            });
        }
    }
    console.log(`TeamChat MCP + hooks registered for ${cli} (role=${role}, peer=${peerPort || 'none'})`);
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
        registerTeamChat(geminiSettings, 'gemini');
        fs.writeFileSync(geminiSettingsPath, JSON.stringify(geminiSettings, null, 2));
        console.log('Gemini settings.json created (trust disabled, TeamChat MCP registered)');
    } catch (err) {
        console.error(`Gemini settings.json error: ${err.message}`);
    }
    // Update Claude settings with TeamChat hooks (MCP goes to ~/.claude.json via writeClaudeMcpServer)
    try {
        let claudeSettings = {};
        if (fs.existsSync(claudeSettingsPath)) {
            try { claudeSettings = JSON.parse(fs.readFileSync(claudeSettingsPath, 'utf8')); } catch { /* fresh start */ }
        }
        registerTeamChat(claudeSettings, 'claude');
        fs.writeFileSync(claudeSettingsPath, JSON.stringify(claudeSettings, null, 2));
        console.log('Claude settings.json updated (TeamChat hooks registered)');
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
        };
        fs.writeFileSync(trustedFoldersPath, JSON.stringify(trustedFolders, null, 2));
        console.log('Gemini trustedFolders.json created (object format)');
    } catch (err) {
        console.error(`Gemini trustedFolders.json error: ${err.message}`);
    }

    filterSkillsByRole(geminiDir, claudeDir);
}

/**
 * Remove skills that don't match AGENT_ROLE.
 * Reads `roles: [...]` from each SKILL.md frontmatter.
 * If roles is present and AGENT_ROLE is not in the list, delete the skill directory.
 */
function filterSkillsByRole(geminiDir, claudeDir) {
    const role = (process.env.AGENT_ROLE || '').toLowerCase();
    if (!role) return;

    const geminiSkillsDir = path.join(geminiDir, 'skills');
    const claudeSkillsDir = path.join(claudeDir, 'skills');
    if (!fs.existsSync(geminiSkillsDir)) return;

    let kept = 0, removed = 0;
    for (const entry of fs.readdirSync(geminiSkillsDir)) {
        const skillMd = path.join(geminiSkillsDir, entry, 'SKILL.md');
        if (!fs.existsSync(skillMd)) continue;

        const head = fs.readFileSync(skillMd, 'utf8').slice(0, 500);
        const match = head.match(/^roles:\s*\[([^\]]*)\]/m);
        if (!match) { kept++; continue; }

        const roles = match[1].split(',').map(r => r.trim().toLowerCase());
        if (roles.includes(role)) { kept++; continue; }

        fs.rmSync(path.join(geminiSkillsDir, entry), { recursive: true, force: true });
        const claudeLink = path.join(claudeSkillsDir, entry);
        if (fs.existsSync(claudeLink)) fs.rmSync(claudeLink, { recursive: true, force: true });
        removed++;
    }
    if (removed > 0) {
        console.log(`Skills filtered for ${role}: ${kept} kept, ${removed} removed`);
    }
}

module.exports = { initializeCLISettings, resolveCommand, writeClaudeMcpServer };
