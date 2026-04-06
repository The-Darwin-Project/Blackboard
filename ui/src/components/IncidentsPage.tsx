// BlackBoard/ui/src/components/IncidentsPage.tsx
// @ai-rules:
// 1. [Pattern]: Read-only table view of Smartsheet incidents created by Darwin.
// 2. [Pattern]: 3 states: loading, empty, populated. Row click opens Smartsheet.
/**
 * Incidents page -- lists Darwin-created Smartsheet incidents.
 */
import { ExternalLink } from 'lucide-react';
import { useIncidents } from '../hooks/useIncidents';
import type { Incident } from '../api/client';

const PRIORITY_COLORS: Record<string, string> = {
  Blocker: '#ef4444',
  Critical: '#ef4444',
  Major: '#f59e0b',
  Minor: '#64748b',
  Normal: '#94a3b8',
  Undefined: '#64748b',
};

const COLUMNS = [
  { key: 'date' as keyof Incident, label: 'Date', width: '12%', wrap: false },
  { key: 'platform' as keyof Incident, label: 'Platform', width: '10%', wrap: true },
  { key: 'summary' as keyof Incident, label: 'Summary', width: '37%', wrap: true },
  { key: 'status' as keyof Incident, label: 'Status', width: '8%', wrap: false },
  { key: 'priority' as keyof Incident, label: 'Priority', width: '10%', wrap: false },
  { key: 'affected_versions' as keyof Incident, label: 'Versions', width: '12%', wrap: true },
  { key: 'fix_pr' as keyof Incident, label: 'Fix PR', width: '8%', wrap: false },
];

export default function IncidentsPage() {
  const { data: incidents, isLoading, isError } = useIncidents();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-text-muted text-sm">
        Loading incidents...
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center h-full text-red-400 text-sm">
        Failed to load incidents.
      </div>
    );
  }

  if (!incidents || incidents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-text-muted">
        <span className="text-sm">No incidents created yet.</span>
        <span className="text-xs">Darwin creates incidents for persistent automated failures.</span>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text-primary">
          Incidents <span className="text-text-muted font-normal">({incidents.length})</span>
        </h2>
      </div>

      <div className="border border-border rounded-lg overflow-hidden">
        <table className="w-full text-xs" style={{ tableLayout: 'fixed' }}>
          <colgroup>
            {COLUMNS.map(col => (
              <col key={col.key} style={{ width: col.width }} />
            ))}
          </colgroup>
          <thead>
            <tr className="bg-bg-secondary border-b border-border">
              {COLUMNS.map(col => (
                <th key={col.key} className="px-3 py-2 text-left font-medium text-text-muted whitespace-nowrap">
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {incidents.map((row, i) => (
              <tr key={row.issue_key || i}
                className="border-b border-border hover:bg-bg-tertiary cursor-pointer transition-colors"
                onClick={() => row.sheet_url && window.open(row.sheet_url, '_blank')}>
                {COLUMNS.map(col => {
                  const val = row[col.key] ?? '';
                  const td = col.wrap
                    ? "px-3 py-2 break-words text-text-secondary"
                    : "px-3 py-2 overflow-hidden whitespace-nowrap text-ellipsis text-text-secondary";
                  if (col.key === 'priority') {
                    return (
                      <td key={col.key} className={td}>
                        <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium"
                          style={{
                            color: PRIORITY_COLORS[val] || '#94a3b8',
                            background: `${PRIORITY_COLORS[val] || '#94a3b8'}18`,
                          }}>
                          {val}
                        </span>
                      </td>
                    );
                  }
                  if (col.key === 'fix_pr' && val) {
                    const mrMatch = val.match(/merge_requests\/(\d+)/);
                    const label = mrMatch ? `!${mrMatch[1]}` : 'MR';
                    return (
                      <td key={col.key} className={td}>
                        <a href={val} target="_blank" rel="noopener noreferrer"
                          className="text-accent hover:underline inline-flex items-center gap-1"
                          title={val}
                          onClick={e => e.stopPropagation()}>
                          <ExternalLink size={10} className="shrink-0" />{label}
                        </a>
                      </td>
                    );
                  }
                  return (
                    <td key={col.key} className={td}>
                      {val}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
