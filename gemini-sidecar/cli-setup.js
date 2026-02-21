// gemini-sidecar/cli-setup.js
// @ai-rules:
// 1. [Pattern]: Startup init — runs once at process start. Writes to ~/.claude and ~/.gemini.
// 2. [Constraint]: Idempotent — checks fs.existsSync before creating; skips overwrite of existing settings/rules.
// 3. [Gotcha]: Staged rules from /tmp/agent-rules/GEMINI.md copied to both CLI dirs; copyFileSync only when target missing.
// 4. [Gotcha]: trustedFolders.json uses object format (path -> trust level), not array; invalid format causes CLI warnings.

const fs = require('fs');
const path = require('path');
const os = require('os');

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
        fs.writeFileSync(geminiSettingsPath, JSON.stringify(geminiSettings, null, 2));
        console.log('Gemini settings.json created (trust disabled)');
    } catch (err) {
        console.error(`Gemini settings.json error: ${err.message}`);
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
}

module.exports = { initializeCLISettings };
