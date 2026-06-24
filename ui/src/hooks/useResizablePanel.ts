// BlackBoard/ui/src/hooks/useResizablePanel.ts
// @ai-rules:
// 1. [Pattern]: Generic resize hook used by EventSidebar, EventChatPanel, ActivityPanel, ChatInput.
// 2. [Constraint]: panelRef typed as RefObject<HTMLElement> (not HTMLDivElement) — ChatInput uses <form>.
// 3. [Pattern]: When storageKey omitted, skip localStorage entirely. When enabled=false, skip writes.
import { useState, useEffect, useCallback, useRef, type RefObject } from 'react';

export interface UseResizablePanelOptions {
  direction: 'horizontal' | 'vertical';
  min: number;
  max: number;
  defaultSize: number;
  storageKey?: string;
  enabled?: boolean;
}

export interface UseResizablePanelReturn {
  size: number;
  isResizing: boolean;
  startResize: (e: React.MouseEvent) => void;
  panelRef: RefObject<HTMLElement>;
}

export function useResizablePanel(options: UseResizablePanelOptions): UseResizablePanelReturn {
  const { direction, min, max, defaultSize, storageKey, enabled = true } = options;

  const [size, setSize] = useState(() => {
    if (!storageKey) return defaultSize;
    const stored = localStorage.getItem(storageKey);
    return stored ? (parseInt(stored, 10) || defaultSize) : defaultSize;
  });
  const [isResizing, setIsResizing] = useState(false);
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (storageKey && enabled) {
      localStorage.setItem(storageKey, String(size));
    }
  }, [size, storageKey, enabled]);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;
    const cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize';
    const onMove = (e: MouseEvent) => {
      if (!panelRef.current) return;
      const rect = panelRef.current.getBoundingClientRect();
      const raw = direction === 'horizontal'
        ? e.clientX - rect.left
        : rect.bottom - e.clientY;
      setSize(Math.min(max, Math.max(min, raw)));
    };
    const onUp = () => setIsResizing(false);
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    document.body.style.cursor = cursor;
    document.body.style.userSelect = 'none';
    return () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing, direction, min, max]);

  return { size, isResizing, startResize, panelRef };
}
