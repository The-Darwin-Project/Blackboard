// gemini-sidecar/state.js
// @ai-rules:
// 1. [Pattern]: All shared mutable state accessed via getters/setters — NEVER import or mutate internal vars directly.
// 2. [Constraint]: Single source of truth for _callbackResult, currentTask, _pendingHuddleReply, _inboundMessages, _teammateMessages.
// 3. [Gotcha]: pendingHuddleReply holds the HTTP response object — keeps /callback request open until huddle_reply arrives or 10min timeout.
// 4. [Gotcha]: currentTask shape includes { eventId, child?, ws?, taskId?, cwd? }; set by ws-client or ws-server before executeCLIStreaming.
// 5. [Pattern]: Two separate message queues — _inboundMessages (Manager proactive, drained by own GET /messages)
//    and _teammateMessages (peer forwards, drained by own GET via hook and team_read_teammate_notes). Never cross-drain.
// 6. [Pattern]: _lastTaskContext preserves sessionId/eventId/cwd after task completion for wake-on-message resume.

let _callbackResult = null;
let currentTask = null;
let _pendingHuddleReply = null; // { res, timeout } -- held HTTP response for huddle_message
let _inboundMessages = [];      // Manager proactive messages (own inbox, drained by GET /messages)
let _teammateMessages = [];     // Teammate-forwarded messages (drained by own GET /teammate-notes)
let _lastTaskContext = null;    // { sessionId, eventId, cwd } -- saved before clearCurrentTask for wake-on-message
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
  pushTeammateMessage: (msg) => { if (_teammateMessages.length < MAX_QUEUE_SIZE) _teammateMessages.push({ ...msg, timestamp: new Date().toISOString() }); },
  drainTeammateMessages: () => { const msgs = _teammateMessages; _teammateMessages = []; return msgs; },
  saveLastTaskContext: (ctx) => { _lastTaskContext = ctx; },
  getLastTaskContext: () => _lastTaskContext,
  clearLastTaskContext: () => { _lastTaskContext = null; },
};
