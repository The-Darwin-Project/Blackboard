// gemini-sidecar/state.js
// @ai-rules:
// 1. [Pattern]: All shared mutable state accessed via getters/setters — NEVER import or mutate internal vars directly.
// 2. [Constraint]: Single source of truth for _callbackResult, currentTask, _pendingHuddleReply across the sidecar.
// 3. [Gotcha]: pendingHuddleReply holds the HTTP response object — keeps /callback request open until huddle_reply arrives or 45s timeout.
// 4. [Gotcha]: currentTask shape includes { eventId, child?, ws?, taskId?, cwd? }; set by ws-client or ws-server before executeCLIStreaming.

let _callbackResult = null;
let currentTask = null;
let _pendingHuddleReply = null; // { res, timeout } -- held HTTP response for huddle_message

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
};
