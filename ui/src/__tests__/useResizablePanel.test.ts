// BlackBoard/ui/src/__tests__/useResizablePanel.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useResizablePanel } from '../hooks/useResizablePanel';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe('useResizablePanel', () => {
  it('initializes with default size when no storageKey', () => {
    const { result } = renderHook(() =>
      useResizablePanel({ direction: 'horizontal', min: 100, max: 800, defaultSize: 400 }),
    );
    expect(result.current.size).toBe(400);
    expect(result.current.isResizing).toBe(false);
  });

  it('reads initial size from localStorage when storageKey provided', () => {
    localStorage.setItem('test:width', '600');
    const { result } = renderHook(() =>
      useResizablePanel({ direction: 'horizontal', min: 100, max: 800, defaultSize: 400, storageKey: 'test:width' }),
    );
    expect(result.current.size).toBe(600);
  });

  it('falls back to defaultSize on invalid localStorage value', () => {
    localStorage.setItem('test:width', 'NaN');
    const { result } = renderHook(() =>
      useResizablePanel({ direction: 'horizontal', min: 100, max: 800, defaultSize: 400, storageKey: 'test:width' }),
    );
    expect(result.current.size).toBe(400);
  });

  it('persists size to localStorage', () => {
    const { result } = renderHook(() =>
      useResizablePanel({ direction: 'horizontal', min: 100, max: 800, defaultSize: 400, storageKey: 'test:persist' }),
    );
    expect(localStorage.getItem('test:persist')).toBe('400');
    expect(result.current.size).toBe(400);
  });

  it('does not persist when storageKey is omitted', () => {
    renderHook(() =>
      useResizablePanel({ direction: 'vertical', min: 80, max: 400, defaultSize: 120 }),
    );
    expect(localStorage.length).toBe(0);
  });

  it('does not persist when enabled is false', () => {
    renderHook(() =>
      useResizablePanel({ direction: 'horizontal', min: 100, max: 800, defaultSize: 400, storageKey: 'test:disabled', enabled: false }),
    );
    expect(localStorage.getItem('test:disabled')).toBeNull();
  });

  it('startResize sets isResizing to true', () => {
    const { result } = renderHook(() =>
      useResizablePanel({ direction: 'horizontal', min: 100, max: 800, defaultSize: 400 }),
    );
    act(() => {
      result.current.startResize({ preventDefault: vi.fn() } as unknown as React.MouseEvent);
    });
    expect(result.current.isResizing).toBe(true);
  });

  it('returns a panelRef', () => {
    const { result } = renderHook(() =>
      useResizablePanel({ direction: 'vertical', min: 80, max: 400, defaultSize: 120 }),
    );
    expect(result.current.panelRef).toBeDefined();
    expect(result.current.panelRef.current).toBeNull();
  });
});
