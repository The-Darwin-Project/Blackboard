// BlackBoard/ui/src/components/ops/ContextMenu.tsx
// @ai-rules:
// 1. [Pattern]: Generic right-click menu. Items driven by node type. Positioned at cursor, clamped to viewport.
// 2. [Pattern]: Each item has icon (lucide), label, color, and optional danger flag for destructive actions.
// 3. [Constraint]: Dismissed on outside click, Esc, or item click. Keyboard accessible (arrow keys + Enter).
// 4. [Pattern]: Separators rendered as thin horizontal lines between action groups.
import { useEffect, useRef, useCallback, type ReactNode } from 'react';

export interface ContextMenuItem {
  id: string;
  label: string;
  icon: ReactNode;
  onClick: () => void;
  color?: string;
  danger?: boolean;
  separator?: boolean;
  disabled?: boolean;
}

interface ContextMenuProps {
  x: number;
  y: number;
  items: ContextMenuItem[];
  onClose: () => void;
}

export default function ContextMenu({ x, y, items, onClose }: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const focusIdx = useRef(0);

  const clampPosition = useCallback(() => {
    if (!menuRef.current) return { left: x, top: y };
    const rect = menuRef.current.getBoundingClientRect();
    const left = Math.min(x, window.innerWidth - rect.width - 8);
    const top = Math.min(y, window.innerHeight - rect.height - 8);
    return { left: Math.max(4, left), top: Math.max(4, top) };
  }, [x, y]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return; }
      const actionItems = items.filter(i => !i.separator && !i.disabled);
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        focusIdx.current = (focusIdx.current + 1) % actionItems.length;
        (menuRef.current?.querySelectorAll('[role="menuitem"]')[focusIdx.current] as HTMLElement)?.focus();
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        focusIdx.current = (focusIdx.current - 1 + actionItems.length) % actionItems.length;
        (menuRef.current?.querySelectorAll('[role="menuitem"]')[focusIdx.current] as HTMLElement)?.focus();
      }
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [items, onClose]);

  useEffect(() => {
    const first = menuRef.current?.querySelector('[role="menuitem"]') as HTMLElement;
    first?.focus();
  }, []);

  const pos = clampPosition();

  return (
    <div ref={menuRef} role="menu"
      className="fixed z-50 min-w-[200px] max-w-[280px] rounded-lg border border-border bg-bg-secondary shadow-2xl overflow-hidden"
      style={{ left: pos.left, top: pos.top, backdropFilter: 'blur(8px)' }}>
      {items.map((item) => {
        if (item.separator) {
          return <div key={item.id} className="h-px bg-border mx-2 my-1" />;
        }
        const textColor = item.danger ? 'text-red-400' : (item.color ? '' : 'text-text-secondary');
        return (
          <button key={item.id} role="menuitem" tabIndex={0}
            disabled={item.disabled}
            onClick={() => { item.onClick(); onClose(); }}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); item.onClick(); onClose(); } }}
            className={`w-full flex items-center gap-3 px-3 py-2 text-left text-xs transition-colors outline-none
              ${item.disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer hover:bg-bg-tertiary focus:bg-bg-tertiary'}
              ${textColor}`}
            style={item.color && !item.danger ? { color: item.color } : undefined}>
            <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center">{item.icon}</span>
            <span className="truncate">{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}
