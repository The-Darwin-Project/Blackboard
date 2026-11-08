// BlackBoard/ui/src/__tests__/clipboard.test.ts
// @ai-rules:
// 1. [Pattern]: Unit tests for utils/clipboard.ts (ANSI stripping, strict vs log sanitization, copyLogLines safety).
// 2. [Constraint]: Asserts exact outputs (not just "does not contain ESC") so residue such as "[31m" is caught.
import { describe, it, expect, vi, afterEach } from 'vitest';
import {
  stripAnsiSequences,
  sanitizeClipboardText,
  sanitizeClipboardLog,
  copyLogLines,
} from '../utils/clipboard';

const ESC = '\u001b';
const BEL = '\u0007';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('stripAnsiSequences', () => {
  it.each([
    ['SGR color', `${ESC}[31mred${ESC}[0m`, 'red'],
    ['SGR with multiple params', `${ESC}[1;38;5;196mbold${ESC}[0m`, 'bold'],
    ['cursor movement', `a${ESC}[2K${ESC}[1Gb`, 'ab'],
    ['private-mode CSI', `${ESC}[?25lhidden${ESC}[?25h`, 'hidden'],
    ['8-bit CSI (0x9b)', `\u009b31mred\u009b0m`, 'red'],
    ['OSC terminated by BEL', `${ESC}]0;window title${BEL}text`, 'text'],
    ['OSC terminated by ST', `${ESC}]8;;http://x${ESC}\\link${ESC}]8;;${ESC}\\`, 'link'],
    ['DCS terminated by ST', `${ESC}Pq#0;2;0;0;0${ESC}\\after`, 'after'],
    ['two-byte ESC sequence', `${ESC}7saved${ESC}8`, 'saved'],
  ])('removes the whole %s sequence', (_label, input, expected) => {
    expect(stripAnsiSequences(input)).toBe(expected);
  });

  it('leaves plain text, brackets and digits untouched', () => {
    expect(stripAnsiSequences('[31m is literal text, 100% [ok]')).toBe('[31m is literal text, 100% [ok]');
  });

  it('bounds an unterminated OSC to its own line', () => {
    expect(stripAnsiSequences(`${ESC}]0;never closed\nnext line`)).toBe('\nnext line');
  });
});

describe('sanitizeClipboardText (strict, single value)', () => {
  it('removes ANSI sequences completely, leaving no "[31m" residue', () => {
    expect(sanitizeClipboardText(`evt${ESC}[31m-123${ESC}[0m`)).toBe('evt-123');
  });

  it('removes CR, LF, TAB, other C0/C1 controls, separators and bidi controls', () => {
    expect(sanitizeClipboardText('a\r\nb\tc\u0000d\u007fe\u0085f\u2028g\u2029h\u202ei\u2066j')).toBe('abcdefghij');
  });
});

describe('sanitizeClipboardLog (multi-line)', () => {
  it('preserves LF and TAB while stripping ANSI sequences', () => {
    expect(sanitizeClipboardLog(`${ESC}[32mline1${ESC}[0m\n\tline2\nline3`)).toBe('line1\n\tline2\nline3');
  });

  it('normalizes CRLF to LF and strips lone CR', () => {
    expect(sanitizeClipboardLog('a\r\nb\rc')).toBe('a\nbc');
  });

  it('strips NUL, DEL, C1, line/paragraph separators and bidi controls', () => {
    expect(sanitizeClipboardLog('a\u0000b\u007fc\u0085d\u2028e\u2029f\u202ag\u2069h')).toBe('abcdefgh');
  });
});

describe('copyLogLines', () => {
  it('writes the sanitized lines joined by newline', () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    copyLogLines([`${ESC}[31mone${ESC}[0m`, 'two\tcols', 'three']);
    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText).toHaveBeenCalledWith('one\ntwo\tcols\nthree');
  });

  it('does not call the clipboard for an empty list', () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    copyLogLines([]);
    expect(writeText).not.toHaveBeenCalled();
  });

  it('does not throw when navigator.clipboard is undefined', () => {
    vi.stubGlobal('navigator', {});
    expect(() => copyLogLines(['x'])).not.toThrow();
  });

  it('does not throw when writeText throws synchronously', () => {
    vi.stubGlobal('navigator', { clipboard: { writeText: () => { throw new Error('blocked'); } } });
    expect(() => copyLogLines(['x'])).not.toThrow();
  });

  it('attaches a rejection handler to a plain (non-spy) rejecting writeText promise', async () => {
    // vi.fn() spies observe returned promises, which masks unhandled rejections; use a bare function instead.
    const attached = vi.fn();
    const rejected = Promise.reject(new Error('denied'));
    const origCatch = rejected.catch.bind(rejected);
    rejected.catch = ((...args: Parameters<typeof origCatch>) => {
      attached();
      return origCatch(...args);
    }) as typeof rejected.catch;
    const origThen = rejected.then.bind(rejected);
    rejected.then = ((...args: Parameters<typeof origThen>) => {
      if (args[1]) attached();
      return origThen(...args);
    }) as typeof rejected.then;
    vi.stubGlobal('navigator', { clipboard: { writeText: () => rejected } });
    expect(() => copyLogLines(['x'])).not.toThrow();
    await new Promise((r) => setTimeout(r, 10));
    expect(attached).toHaveBeenCalled();
  });

  it('swallows a rejected writeText (no unhandled rejection)', async () => {
    const unhandled = vi.fn();
    process.on('unhandledRejection', unhandled);
    try {
      const writeText = vi.fn().mockRejectedValue(new Error('denied'));
      vi.stubGlobal('navigator', { clipboard: { writeText } });
      expect(() => copyLogLines(['x'])).not.toThrow();
      await new Promise((r) => setTimeout(r, 10));
      expect(writeText).toHaveBeenCalledTimes(1);
      expect(unhandled).not.toHaveBeenCalled();
    } finally {
      process.off('unhandledRejection', unhandled);
    }
  });
});
