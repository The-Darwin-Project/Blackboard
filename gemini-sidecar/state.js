// gemini-sidecar/state.js
// @ai-rules:
// 1. [Pattern]: All shared mutable state accessed via getters/setters — NEVER import or mutate internal vars directly.
// 2. [Constraint]: Single source of truth for _callbackResult, currentTask, _pendingHuddleReply, _inboundMessages, _teammateMessages, _blackboard*.
// 3. [Gotcha]: pendingHuddleReply holds the HTTP response object — keeps /callback request open until huddle_reply arrives or 10min timeout.
// 4. [Gotcha]: currentTask shape includes { eventId, child?, ws?, taskId?, cwd? }; set by ws-client or ws-server before executeCLIStreaming.
// 5. [Pattern]: Two separate message queues — _inboundMessages (Manager proactive, drained by own GET /messages)
//    and _teammateMessages (peer forwards, drained by own GET via hook and team_read_teammate_notes). Never cross-drain.
// 6. [Pattern]: _lastTaskContext preserves sessionId/eventId/cwd after task completion for wake-on-message resume.
// 7. [Pattern]: Blackboard cache fed by WebSocket blackboard_update from Brain. Shared hookHighwater between MCP + PostToolUse hook prevents duplicate injection.
// 8. [Pattern]: peek* methods are non-destructive reads (for Stop hook). drain* methods consume and clear (for PostToolUse hook).

let _callbackResult = null;
let currentTask = null;
let _pendingHuddleReply = null; // { res, timeout } -- held HTTP response for huddle_message
let _inboundMessages = [];      // Manager proactive messages (own inbox, drained by GET /messages)
let _teammateMessages = [];     // Teammate-forwarded messages (drained by own GET /teammate-notes)
let _lastTaskContext = null;    // { sessionId, eventId, cwd } -- saved before clearCurrentTask for wake-on-message
let _blackboardTurns = [];      // Turns pushed by Brain via WebSocket blackboard_update
let _blackboardStatus = 'unknown';
let _blackboardTotal = 0;
let _hookHighwater = 0;         // Shared between PostToolUse hook and bb_catch_up MCP to prevent duplicate injection
const MAX_QUEUE_SIZE = 100;

module.exports = {
  getCallbackResult: () => _callbackResult,
  setCallbackResult: (v) => { _callbackResult = v; },
  resetCallbackResult: () => { _callbackResult = null; },
  getCurrentTask: () => currentTask,
  setCurrentTask: (t) => { currentTask = t; },
  clearCurrentTask: () => { currentTask = null; },
  getPendingHuddleReply: () => _pendingHuddleReply,
  setPendingHuddleReply: (v) => { _pendingHuddleReply = v; },
  clearPendingHuddleReply: () => { _pendingHuddleReply = null; },
  pushInboundMessage: (msg) => { if (_inboundMessages.length < MAX_QUEUE_SIZE) _inboundMessages.push({ ...msg, timestamp: new Date().toISOString() }); },
  drainInboundMessages: () => { const msgs = _inboundMessages; _inboundMessages = []; return msgs; },
  peekInboundMessages: () => [..._inboundMessages],
  pushTeammateMessage: (msg) => { if (_teammateMessages.length < MAX_QUEUE_SIZE) _teammateMessages.push({ ...msg, timestamp: new Date().toISOString() }); },
  drainTeammateMessages: () => { const msgs = _teammateMessages; _teammateMessages = []; return msgs; },
  peekTeammateMessages: () => [..._teammateMessages],
  saveLastTaskContext: (ctx) => { _lastTaskContext = ctx; },
  getLastTaskContext: () => _lastTaskContext,
  clearLastTaskContext: () => { _lastTaskContext = null; },
  pushBlackboardTurn: (turn, status, total) => {
    if (_blackboardTurns.length < MAX_QUEUE_SIZE) _blackboardTurns.push(turn);
    if (status) _blackboardStatus = status;
    if (total) _blackboardTotal = total;
  },
  getBlackboardTurnsSince: (n) => _blackboardTurns.filter(t => (t.turn || 0) > n),
  getBlackboardStatus: () => ({ status: _blackboardStatus, total: _blackboardTotal, highwater: _hookHighwater }),
  getHookHighwater: () => _hookHighwater,
  setHookHighwater: (n) => { _hookHighwater = n; },
};
