// gemini-sidecar/ws-utils.js
// @ai-rules:
// 1. [Pattern]: Safe WebSocket send — checks readyState === OPEN before sending; no-op if closed/closing.
// 2. [Constraint]: Always JSON.stringify data; callers must pass serializable objects.
// 3. [Gotcha]: Does not throw on closed socket; silently skips send. Callers rely on no exception.

const WebSocket = require('ws');

function wsSend(ws, data) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

module.exports = { wsSend };
