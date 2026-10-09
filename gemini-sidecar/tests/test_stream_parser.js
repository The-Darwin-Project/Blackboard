// gemini-sidecar/tests/test_stream_parser.js
// @ai-rules:
// 1. [Constraint]: Pure unit tests for stream-parser.js — uses node:test + node:assert/strict.
// 2. [Pattern]: Tests stream parser across Gemini, Claude, and Antigravity (agy) schemas.
// 3. [Coverage]: Tests agy init, step_update (text_delta, tool_info, error), result (success text: null, error text: [error]...),
//    raw fallback, and parseClaudeStreamLine wrapper.

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const { parseStreamLine, parseClaudeStreamLine } = require('../stream-parser.js');

describe('stream-parser: Gemini format', () => {
  it('parses init event', () => {
    const line = JSON.stringify({ type: 'init', session_id: 'gemini-sess-123' });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: null,
      sessionId: 'gemini-sess-123',
      toolCalls: null,
      done: false,
    });
  });

  it('parses assistant message event', () => {
    const line = JSON.stringify({ type: 'message', role: 'assistant', content: 'Gemini says hello' });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: 'Gemini says hello',
      sessionId: null,
      toolCalls: null,
      done: false,
    });
  });

  it('parses tool_use event', () => {
    const line = JSON.stringify({
      type: 'tool_use',
      tool_name: 'read_file',
      parameters: { file_path: '/path/to/file.txt' },
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: '[tool] read_file: /path/to/file.txt',
      sessionId: null,
      toolCalls: null,
      done: false,
    });
  });

  it('parses tool_result event', () => {
    const line = JSON.stringify({
      type: 'tool_result',
      tool_name: 'read_file',
      output: 'file content preview',
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: '[read_file] → file content preview',
      sessionId: null,
      toolCalls: null,
      done: false,
    });
  });

  it('parses error event', () => {
    const line = JSON.stringify({ type: 'error', message: 'Quota exceeded warning' });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: '[error] Quota exceeded warning',
      sessionId: null,
      toolCalls: null,
      done: false,
    });
  });

  it('parses result event', () => {
    const line = JSON.stringify({
      type: 'result',
      status: 'success',
      result: 'Final Gemini summary',
      stats: { tool_calls: 3 },
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: 'Final Gemini summary',
      sessionId: null,
      toolCalls: 3,
      done: true,
    });
  });
});

describe('stream-parser: Claude format', () => {
  it('parses system init event', () => {
    const line = JSON.stringify({
      type: 'system',
      subtype: 'init',
      session_id: 'claude-sess-456',
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: null,
      sessionId: 'claude-sess-456',
      toolCalls: null,
      done: false,
    });
  });

  it('parses assistant text message', () => {
    const line = JSON.stringify({
      type: 'assistant',
      message: {
        content: [{ type: 'text', text: 'Claude response text' }],
      },
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: 'Claude response text',
      sessionId: null,
      toolCalls: null,
      done: false,
    });
  });

  it('parses assistant tool_use message', () => {
    const line = JSON.stringify({
      type: 'assistant',
      message: {
        content: [{ type: 'tool_use', name: 'Bash', input: { command: 'ls -la' } }],
      },
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: '[tool] Bash: ls -la',
      sessionId: null,
      toolCalls: null,
      done: false,
    });
  });

  it('parses user tool_result with file preview', () => {
    const line = JSON.stringify({
      type: 'user',
      tool_use_result: {
        file: {
          filePath: '/app/index.js',
          content: 'console.log("hello world");',
        },
      },
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: '[/app/index.js] → console.log("hello world");',
      sessionId: null,
      toolCalls: null,
      done: false,
    });
  });
});

describe('stream-parser: Antigravity CLI (agy) format', () => {
  it('event: "init" extracts sessionId from conversation_id', () => {
    const line = JSON.stringify({
      event: 'init',
      conversation_id: 'agy-conv-789',
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: null,
      sessionId: 'agy-conv-789',
      toolCalls: null,
      done: false,
    });
  });

  it('event: "init" handles missing conversation_id', () => {
    const line = JSON.stringify({ event: 'init' });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: null,
      sessionId: null,
      toolCalls: null,
      done: false,
    });
  });

  it('event: "step_update" with text_delta extracts incremental text', () => {
    const line = JSON.stringify({
      event: 'step_update',
      step_update: {
        conversation_id: 'agy-conv-789',
        text_delta: 'Thinking about the architecture...',
      },
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: 'Thinking about the architecture...',
      sessionId: 'agy-conv-789',
      toolCalls: null,
      done: false,
    });
  });

  it('event: "step_update" with tool_info extracts tool preview with path hint', () => {
    const line = JSON.stringify({
      event: 'step_update',
      step_update: {
        conversation_id: 'agy-conv-789',
        tool_info: {
          name: 'view_file',
          parameters: { AbsolutePath: '/var/log/audit.log' },
          output: 'Audit line 1\nAudit line 2',
        },
      },
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: '[tool] view_file: /var/log/audit.log → Audit line 1 Audit line 2',
      sessionId: 'agy-conv-789',
      toolCalls: 1,
      done: false,
    });
  });

  it('event: "step_update" with tool_info extracts CommandLine hint', () => {
    const line = JSON.stringify({
      event: 'step_update',
      step_update: {
        conversation_id: 'agy-conv-789',
        tool_info: {
          tool_name: 'run_command',
          parameters: { CommandLine: 'git status -s' },
        },
      },
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: '[tool] run_command: git status -s',
      sessionId: 'agy-conv-789',
      toolCalls: 1,
      done: false,
    });
  });

  it('event: "step_update" with error extracts [error] message', () => {
    const line = JSON.stringify({
      event: 'step_update',
      step_update: {
        conversation_id: 'agy-conv-789',
        error: 'Permission denied accessing socket',
      },
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: '[error] Permission denied accessing socket',
      sessionId: 'agy-conv-789',
      toolCalls: null,
      done: false,
    });
  });

  it('event: "result" returns text: null on success (no output doubling) and done: true', () => {
    const line = JSON.stringify({
      event: 'result',
      result: {
        conversation_id: 'agy-conv-789',
        status: 'SUCCESS',
        response: 'Full accumulated response text that would double if returned',
        num_turns: 4,
      },
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: null,
      sessionId: 'agy-conv-789',
      toolCalls: 4,
      done: true,
    });
  });

  it('event: "result" returns text: "[error] ..." on error', () => {
    const line = JSON.stringify({
      event: 'result',
      result: {
        conversation_id: 'agy-conv-789',
        status: 'ERROR',
        error: 'Execution timed out',
        num_turns: 2,
      },
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: '[error] Execution timed out',
      sessionId: 'agy-conv-789',
      toolCalls: 2,
      done: true,
    });
  });

  it('event: "result" returns fallback error message if error field missing', () => {
    const line = JSON.stringify({
      event: 'result',
      result: {
        conversation_id: 'agy-conv-789',
        status: 'ERROR',
      },
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: '[error] Execution failed',
      sessionId: 'agy-conv-789',
      toolCalls: null,
      done: true,
    });
  });

  it('event: "result" with CANCELLED status returns [error] CANCELLED', () => {
    const line = JSON.stringify({
      event: 'result',
      result: {
        conversation_id: 'agy-conv-789',
        status: 'CANCELLED',
      },
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: '[error] CANCELLED',
      sessionId: 'agy-conv-789',
      toolCalls: null,
      done: true,
    });
  });

  it('event: "result" handles missing .result payload safely', () => {
    const line = JSON.stringify({
      event: 'result',
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: '[error] Execution failed',
      sessionId: null,
      toolCalls: null,
      done: true,
    });
  });

  it('event: "step_update" with simultaneous text_delta and tool_info assembles parts joined by newline', () => {
    const line = JSON.stringify({
      event: 'step_update',
      step_update: {
        conversation_id: 'agy-conv-789',
        text_delta: 'I will now run the command.',
        tool_info: {
          name: 'run_command',
          parameters: { CommandLine: 'ls -la' },
        },
      },
    });
    const res = parseStreamLine(line);
    assert.deepEqual(res, {
      text: 'I will now run the command.\n[tool] run_command: ls -la',
      sessionId: 'agy-conv-789',
      toolCalls: 1,
      done: false,
    });
  });
});

describe('stream-parser: raw fallback & wrapper', () => {
  it('falls back to raw text for non-JSON lines', () => {
    const raw = 'Plain text log message from subprocess';
    const res = parseStreamLine(raw);
    assert.deepEqual(res, {
      text: raw,
      sessionId: null,
      toolCalls: null,
      done: false,
    });
  });

  it('parseClaudeStreamLine returns text string or null', () => {
    const raw = 'Some random log';
    assert.equal(parseClaudeStreamLine(raw), raw);

    const initLine = JSON.stringify({ event: 'init', conversation_id: '123' });
    assert.equal(parseClaudeStreamLine(initLine), null);

    const textLine = JSON.stringify({
      event: 'step_update',
      step_update: { text_delta: 'hello' },
    });
    assert.equal(parseClaudeStreamLine(textLine), 'hello');
  });
});
