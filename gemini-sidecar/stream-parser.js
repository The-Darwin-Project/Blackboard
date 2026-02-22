// gemini-sidecar/stream-parser.js
// @ai-rules:
// 1. [Constraint]: Pure JSON parsing functions — no side effects, no state, no I/O.
// 2. [Pattern]: Unified parseStreamLine handles both Gemini and Claude stream-json schemas; returns { text, sessionId, toolCalls, done } or null.
// 3. [Pattern]: parseClaudeStreamLine is backward-compat wrapper — returns parsed.text only for legacy callers.
// 4. [Gotcha]: Non-JSON input returns { text: line, ... } (raw line as text); JSON parse errors are caught, not thrown.

/**
 * Unified stream-json line parser for both Gemini and Claude CLIs.
 * Returns { text, sessionId, toolCalls, done } or null if not user-facing.
 *
 * Gemini stream-json schema (probed 2026-02-13, updated 2026-02-22):
 *   {"type":"init","session_id":"...","model":"auto-gemini-2.5"}
 *   {"type":"message","role":"assistant","content":"...","delta":true}
 *   {"type":"tool_use","tool_name":"read_file","tool_id":"...","parameters":{...}}
 *   {"type":"tool_result","tool_name":"read_file","output":"..."}
 *   {"type":"error","message":"Non-fatal warning or error"}
 *   {"type":"result","status":"success","stats":{"tool_calls":0,...}}
 *
 * Claude stream-json schema (verified via podman 2026-02-22):
 *   {"type":"system","subtype":"init","session_id":"...","tools":[...],"model":"..."}
 *   {"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","id":"...","input":{...}}]}}
 *   {"type":"user","message":{"content":[{"tool_use_id":"...","type":"tool_result","content":"..."}]}}
 *   {"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
 *   {"type":"result","subtype":"success","result":"...","duration_ms":...}
 */
function parseStreamLine(line) {
    try {
        const obj = JSON.parse(line);

        // --- Init events (both CLIs emit session_id) ---
        if (obj.type === 'init' || (obj.type === 'system' && obj.subtype === 'init')) {
            return { text: null, sessionId: obj.session_id || null, toolCalls: null, done: false };
        }

        // --- Gemini: assistant message ---
        if (obj.type === 'message' && obj.role === 'assistant' && obj.content) {
            return { text: obj.content, sessionId: null, toolCalls: null, done: false };
        }

        // --- Claude: assistant message (text + tool_use blocks) ---
        if (obj.type === 'assistant' && obj.message?.content) {
            const parts = [];
            for (const block of obj.message.content) {
                if (block.type === 'text' && block.text) {
                    parts.push(block.text);
                } else if (block.type === 'tool_use' && block.name) {
                    const hint = block.input?.file_path || block.input?.command || block.input?.query || '';
                    const suffix = hint ? `: ${hint.toString().slice(0, 120)}` : '';
                    parts.push(`[tool] ${block.name}${suffix}`);
                }
            }
            return { text: parts.join('\n') || null, sessionId: null, toolCalls: null, done: false };
        }

        // --- Claude: user message with tool_result (tool output) ---
        if (obj.type === 'user' && obj.tool_use_result) {
            const file = obj.tool_use_result?.file;
            if (file?.filePath) {
                const preview = (file.content || '').slice(0, 200).replace(/\n/g, ' ');
                return { text: `[${file.filePath}] → ${preview}${(file.content || '').length > 200 ? '...' : ''}`, sessionId: null, toolCalls: null, done: false };
            }
            return null;
        }

        // --- Gemini: tool_use event (top-level, not nested in assistant message) ---
        if (obj.type === 'tool_use' && obj.tool_name) {
            const hint = obj.parameters?.file_path || obj.parameters?.command || obj.parameters?.query || '';
            const suffix = hint ? `: ${hint.toString().slice(0, 120)}` : '';
            return { text: `[tool] ${obj.tool_name}${suffix}`, sessionId: null, toolCalls: null, done: false };
        }

        // --- Both CLIs: tool_result event (brief summary of tool output) ---
        if (obj.type === 'tool_result') {
            const name = obj.tool_name || 'tool';
            let raw = obj.output || '';
            if (!raw && Array.isArray(obj.content)) {
                raw = obj.content.filter(c => c.type === 'text').map(c => c.text).join('\n');
            } else if (!raw && typeof obj.content === 'string') {
                raw = obj.content;
            }
            const len = raw.length;
            const preview = raw.slice(0, 200).replace(/\n/g, ' ');
            const suffix = preview ? ` → ${preview}${len > 200 ? '...' : ''}` : '';
            return { text: `[${name}]${suffix}`, sessionId: null, toolCalls: null, done: false };
        }

        // --- Gemini: error event (non-fatal warnings) ---
        if (obj.type === 'error') {
            const msg = obj.message || obj.error || JSON.stringify(obj);
            return { text: `[error] ${msg}`, sessionId: null, toolCalls: null, done: false };
        }

        // --- Result events (both CLIs) ---
        if (obj.type === 'result') {
            const toolCalls = obj.stats?.tool_calls ?? null;
            let text = null;
            if (obj.result) {
                text = typeof obj.result === 'string' ? obj.result : JSON.stringify(obj.result);
            }
            return { text, sessionId: null, toolCalls, done: true };
        }
    } catch (e) {
        // Not JSON -- return raw line as text
        return { text: line, sessionId: null, toolCalls: null, done: false };
    }
    return null;
}

// Backward compat wrapper -- existing code calls parseClaudeStreamLine()
function parseClaudeStreamLine(line) {
    const parsed = parseStreamLine(line);
    return parsed?.text || null;
}

module.exports = { parseStreamLine, parseClaudeStreamLine };
