// BlackBoard/ui/src/components/TabPanel.tsx
// @ai-rules:
// 1. [Pattern]: Generic reusable tab container -- no business logic, only layout.
// 2. [Constraint]: Dark theme styling matches existing bg-bg-secondary / border-border tokens.
/**
 * Reusable tab panel with bottom-border active indicator.
 * Used by Dashboard for left (Activity/Chat) and middle (Tickets/Architecture) panels.
 */
import type { ReactNode } from 'react';

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
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden' }}>
      {/* Tab bar */}
      <div style={{
        display: 'flex',
        borderBottom: '1px solid #334155',
        flexShrink: 0,
        background: '#0f172a',
      }}>
        {tabs.map((tab) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
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
