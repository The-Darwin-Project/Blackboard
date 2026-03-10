// BlackBoard/ui/src/components/CollapsibleSection.tsx
// @ai-rules:
// 1. [Pattern]: Generic collapsible wrapper. Used by ReportContent for metadata sections.
// 2. [Constraint]: Pure presentational -- no data fetching, no API calls.
// 3. [Pattern]: Chevron rotates on open/close. Smooth height transition via CSS.
import { useState, type ReactNode } from 'react';
import { ChevronRight } from 'lucide-react';

interface CollapsibleSectionProps {
  title: string;
  defaultOpen?: boolean;
  badge?: ReactNode;
  children: ReactNode;
}

export default function CollapsibleSection({
  title, defaultOpen = false, badge, children,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div style={{
      border: '1px solid #1e293b',
      borderRadius: 8,
      marginBottom: 8,
      background: '#0f172a',
      overflow: 'hidden',
    }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '10px 14px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: '#e2e8f0',
          fontSize: 13,
          fontWeight: 600,
          textAlign: 'left',
        }}
      >
        <ChevronRight
          size={16}
          style={{
            transition: 'transform 0.2s',
            transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
            color: '#64748b',
            flexShrink: 0,
          }}
        />
        {title}
        {badge && <span style={{ marginLeft: 'auto' }}>{badge}</span>}
      </button>
      {open && (
        <div style={{ padding: '0 14px 12px 38px' }}>
          {children}
        </div>
      )}
    </div>
  );
}
