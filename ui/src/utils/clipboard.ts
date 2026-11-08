// BlackBoard/ui/src/utils/clipboard.ts
// @ai-rules:
// 1. [Constraint]: Pure helpers, zero React deps. Kept out of component files so they satisfy react-refresh/only-export-components.
// 2. [Constraint]: ANSI/VT escape SEQUENCES (CSI, OSC, DCS/APC/PM/SOS, other ESC pairs) are stripped as a whole BEFORE
//    control characters are removed; removing ESC alone would leave residue such as "[31m" in the clipboard.
// 3. [Pattern]: sanitizeClipboardText is strict (single value: ALL controls removed). sanitizeClipboardLog is for multi-line
//    stream logs: it preserves "\n" and "\t", normalizes "\r\n" to "\n", and strips every other unsafe character.
// 4. [Gotcha]: copyLogLines never throws and never leaves an unhandled rejection (missing navigator.clipboard, sync throw, rejected writeText).

// OSC (ESC ] / 0x9d), DCS/SOS/PM/APC (ESC P X ^ _), CSI (ESC [ / 0x9b), then any other two-byte ESC sequence.
// String-type sequences are bounded to the current line so an unterminated one cannot swallow the rest of the log.
const ANSI_SEQUENCES = new RegExp(
  [
    '(?:\\u001b\\]|\\u009d)[^\\u0007\\u001b\\u009c\\n]*(?:\\u0007|\\u001b\\\\|\\u009c)?',
    '\\u001b[PX^_][^\\u0007\\u001b\\u009c\\n]*(?:\\u001b\\\\|\\u009c)?',
    '(?:\\u001b\\[|\\u009b)[\\u0030-\\u003f]*[\\u0020-\\u002f]*[\\u0040-\\u007e]',
    '\\u001b[\\u0020-\\u002f]*[\\u0030-\\u007e]',
  ].join('|'),
  'g',
);

/** Strips C0/DEL/C1 controls, line/paragraph separators and bidi controls from clipboard text. */
// eslint-disable-next-line no-control-regex
export const CLIPBOARD_UNSAFE_CHARS = /[\u0000-\u001f\u007f-\u009f\u2028\u2029\u202a-\u202e\u2066-\u2069]/g;

/** Same as CLIPBOARD_UNSAFE_CHARS but keeps TAB (\u0009) and LF (\u000a). */
// eslint-disable-next-line no-control-regex
const LOG_UNSAFE_CHARS = /[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u2028\u2029\u202a-\u202e\u2066-\u2069]/g;

export const stripAnsiSequences = (text: string): string => text.replace(ANSI_SEQUENCES, '');

export const sanitizeClipboardText = (text: string): string =>
  stripAnsiSequences(text).replace(CLIPBOARD_UNSAFE_CHARS, '');

/** Sanitizes multi-line log text; preserves "\n" and "\t". */
export const sanitizeClipboardLog = (text: string): string =>
  stripAnsiSequences(text).replace(/\r\n/g, '\n').replace(LOG_UNSAFE_CHARS, '');

/** Copies stream log lines (joined by "\n") to the clipboard. No-op for empty input; never throws or rejects unhandled. */
export function copyLogLines(lines: readonly string[]): void {
  if (lines.length === 0) return;
  try {
    const pending = navigator.clipboard?.writeText(sanitizeClipboardLog(lines.join('\n')));
    void Promise.resolve(pending).catch(() => {});
  } catch {
    // Clipboard unavailable or blocked; copy is best-effort.
  }
}
