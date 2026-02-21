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
 * Gemini stream-json schema (probed 2026-02-13):
 *   {"type":"init","session_id":"...","model":"auto-gemini-2.5"}
 *   {"type":"message","role":"assistant","content":"...","delta":true}
 *   {"type":"result","status":"success","stats":{"tool_calls":0,...}}
 *
 * Claude stream-json schema:
 *   {"type":"system","subtype":"init","session_id":"..."}
 *   {"type":"content_block_delta","delta":{"type":"text_delta","text":"..."}}
 *   {"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
 *   {"type":"result","result":"..."}
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

        // --- Claude: content_block_delta (incremental token) ---
        if (obj.type === 'content_block_delta' && obj.delta?.text) {
            return { text: obj.delta.text, sessionId: null, toolCalls: null, done: false };
        }

        // --- Claude: assistant message (summarized) ---
        if (obj.type === 'assistant' && obj.message?.content) {
            const texts = obj.message.content
                .filter(c => c.type === 'text')
                .map(c => c.text);
            return { text: texts.join('\n') || null, sessionId: null, toolCalls: null, done: false };
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
