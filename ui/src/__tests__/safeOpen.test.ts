// BlackBoard/ui/src/__tests__/safeOpen.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { safeOpen } from '../utils/safeOpen';

describe('safeOpen', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('open', vi.fn());
  });

  it('opens https URLs', () => {
    safeOpen('https://gitlab.example.com/mr/1');
    expect(window.open).toHaveBeenCalledWith(
      'https://gitlab.example.com/mr/1', '_blank', 'noopener,noreferrer',
    );
  });

  it('opens http URLs', () => {
    safeOpen('http://jira.example.com/browse/FOO-1');
    expect(window.open).toHaveBeenCalledWith(
      'http://jira.example.com/browse/FOO-1', '_blank', 'noopener,noreferrer',
    );
  });

  it('blocks javascript: URLs', () => {
    safeOpen('javascript:alert(1)');
    expect(window.open).not.toHaveBeenCalled();
  });

  it('blocks data: URLs', () => {
    safeOpen('data:text/html,<script>alert(1)</script>');
    expect(window.open).not.toHaveBeenCalled();
  });

  it('blocks blob: URLs', () => {
    safeOpen('blob:http://localhost/abc');
    expect(window.open).not.toHaveBeenCalled();
  });

  it('handles malformed URLs gracefully', () => {
    safeOpen('http://[');
    expect(window.open).not.toHaveBeenCalled();
  });

  it('handles null', () => {
    safeOpen(null);
    expect(window.open).not.toHaveBeenCalled();
  });

  it('handles undefined', () => {
    safeOpen(undefined);
    expect(window.open).not.toHaveBeenCalled();
  });

  it('handles empty string', () => {
    safeOpen('');
    expect(window.open).not.toHaveBeenCalled();
  });
});
