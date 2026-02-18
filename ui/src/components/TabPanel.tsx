// BlackBoard/ui/src/components/TabPanel.tsx
// @ai-rules:
// 1. [Pattern]: Generic reusable tab container -- no business logic, only layout.
// 2. [Constraint]: Dark theme styling matches existing bg-bg-secondary / border-border tokens.
/**
 * Reusable tab panel with bottom-border active indicator.
 * Used by Dashboard for left (Activity/Chat) and middle (Tickets/Architecture) panels.
 */
import { useRef, type ReactNode } from 'react';

export interface Tab {
  id: string;
  label: string;
}

interface TabPanelProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (id: string) => void;
  children: ReactNode;
}

export default function TabPanel({ tabs, activeTab, onTabChange, children }: TabPanelProps) {
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden' }}>
      {/* Tab bar */}
      <div role="tablist" style={{
        display: 'flex',
        borderBottom: '1px solid #334155',
        flexShrink: 0,
        background: '#0f172a',
      }}>
        {tabs.map((tab, i) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              ref={(el) => { tabRefs.current[i] = el; }}
              role="tab"
              aria-selected={isActive}
              tabIndex={isActive ? 0 : -1}
              onClick={() => onTabChange(tab.id)}
              onKeyDown={(e) => {
                const len = tabs.length;
                let next = -1;
                if (e.key === 'ArrowRight') { e.preventDefault(); next = (i + 1) % len; }
                if (e.key === 'ArrowLeft') { e.preventDefault(); next = (i - 1 + len) % len; }
                if (next >= 0) { onTabChange(tabs[next].id); tabRefs.current[next]?.focus(); }
              }}
              onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.color = '#94a3b8'; }}
              onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.color = '#64748b'; }}
              style={{
                flex: 1,
                padding: '8px 12px',
                background: 'transparent',
                border: 'none',
                borderBottom: isActive ? '2px solid #3b82f6' : '2px solid transparent',
                color: isActive ? '#e2e8f0' : '#64748b',
                fontSize: 12,
                fontWeight: isActive ? 600 : 400,
                cursor: 'pointer',
                transition: 'all 0.15s',
                whiteSpace: 'nowrap',
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
      {/* Content */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {children}
      </div>
    </div>
  );
}
