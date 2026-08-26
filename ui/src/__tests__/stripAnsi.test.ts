import { describe, it, expect } from 'vitest';
import { stripAnsi } from '../utils/stripAnsi';

const ESC = '';

describe('stripAnsi', () => {
  it('strips SGR color codes', () => {
    expect(stripAnsi(`${ESC}[31mHello${ESC}[0m`)).toBe('Hello');
  });

  it('leaves plain text unchanged', () => {
    expect(stripAnsi('plain text, no escapes')).toBe('plain text, no escapes');
  });

  it('handles an empty string', () => {
    expect(stripAnsi('')).toBe('');
  });

  it('strips bold/color combinations with multiple params', () => {
    expect(stripAnsi(`${ESC}[1;32mBOLD GREEN${ESC}[0m normal`)).toBe('BOLD GREEN normal');
  });

  it('strips multiple sequences in one string', () => {
    expect(stripAnsi(`${ESC}[31mred${ESC}[0m and ${ESC}[34mblue${ESC}[0m`)).toBe('red and blue');
  });

  it('strips cursor/erase sequences (e.g. erase-line)', () => {
    expect(stripAnsi(`${ESC}[2Kline`)).toBe('line');
  });

  it('preserves newlines while stripping escapes on each line', () => {
    expect(stripAnsi(`${ESC}[31mline1\nline2${ESC}[0m`)).toBe('line1\nline2');
  });
});
