// BlackBoard/ui/src/components/EventHistoryTable.tsx
// @ai-rules:
// 1. [Pattern]: TanStack Table with client-side sorting on loaded data. Server always returns newest-first.
// 2. [Constraint]: Sort is on loaded pages only -- shows "Sorting loaded results" label when non-time sort active.
// 3. [Pattern]: Semantic <table> elements for accessibility. aria-sort on sortable headers.
import { useState } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from '@tanstack/react-table';
import type { ReportMeta } from '../api/types';
import { DOMAIN_COLORS, SEVERITY_COLORS } from '../constants/colors';
import SourceIcon from './SourceIcon';
import { resolveSubjectType, resolveDescription } from '../utils/eventFormat';

interface Props {
  reports: ReportMeta[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const col = createColumnHelper<ReportMeta>();

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

const columns = [
  col.accessor('closed_at', {
    header: 'Time',
    cell: (info) => (
      <span title={new Date(info.getValue()).toLocaleString()}>
        {relativeTime(info.getValue())}
      </span>
    ),
    sortingFn: (a, b) => new Date(a.original.closed_at).getTime() - new Date(b.original.closed_at).getTime(),
  }),
  col.accessor('service', {
    header: 'Service',
    cell: (info) => (
      <span className="font-medium">{info.getValue()}</span>
    ),
  }),
  col.display({
    id: 'description',
    header: 'Description',
    cell: (info) => {
      const desc = resolveDescription(info.row.original.display_text, info.row.original.reason);
      return (
        <span className="text-text-muted truncate block max-w-[300px]" title={desc}>
          {desc || <span className="italic text-text-muted/50">—</span>}
        </span>
      );
    },
  }),
  col.accessor('source', {
    header: 'Source',
    cell: (info) => (
      <span className="flex items-center gap-1.5">
        <SourceIcon source={info.getValue()} subjectType={resolveSubjectType(info.row.original.subject_type, info.row.original.service)} size={16} />
        {info.getValue()}
      </span>
    ),
  }),
  col.accessor('domain', {
    header: 'Domain',
    cell: (info) => {
      const d = info.getValue() as keyof typeof DOMAIN_COLORS;
      const c = DOMAIN_COLORS[d] || DOMAIN_COLORS.complicated;
      return (
        <span style={{ background: c.bg, color: c.text, padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600, textTransform: 'uppercase' }}>
          {d}
        </span>
      );
    },
  }),
  col.accessor('severity', {
    header: 'Severity',
    cell: (info) => {
      const s = SEVERITY_COLORS[info.getValue()] || SEVERITY_COLORS.info;
      return (
        <span style={{ background: s.bg, color: s.text, padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600 }}>
          {s.label}
        </span>
      );
    },
    sortingFn: (a, b) => {
      const order: Record<string, number> = { critical: 0, warning: 1, info: 2 };
      return (order[a.original.severity] ?? 3) - (order[b.original.severity] ?? 3);
    },
  }),
  col.accessor('turns', {
    header: 'Turns',
    cell: (info) => info.getValue(),
  }),
  col.accessor('event_id', {
    header: 'Event',
    cell: (info) => (
      <span className="font-mono text-xs">{info.getValue()}</span>
    ),
  }),
];

export default function EventHistoryTable({ reports, selectedId, onSelect }: Props) {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'closed_at', desc: true }]);

  const table = useReactTable({
    data: reports,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const isNonTimeSort = sorting.length > 0 && sorting[0].id !== 'closed_at';

  return (
    <div className="flex-1 overflow-auto">
      {isNonTimeSort && (
        <div className="px-3 py-1 text-xs text-text-muted bg-bg-tertiary border-b border-border-primary">
          Sorting loaded results
        </div>
      )}
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-bg-secondary border-b border-border-primary">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((header) => (
                <th
                  key={header.id}
                  onClick={header.column.getToggleSortingHandler()}
                  aria-sort={header.column.getIsSorted() === 'asc' ? 'ascending' : header.column.getIsSorted() === 'desc' ? 'descending' : 'none'}
                  className="px-3 py-2 text-left text-xs font-medium text-text-muted cursor-pointer hover:text-text-secondary select-none"
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  {header.column.getIsSorted() === 'asc' ? ' \u2191' : header.column.getIsSorted() === 'desc' ? ' \u2193' : ''}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-10 text-center text-text-muted text-sm">
                No events match your filters.
              </td>
            </tr>
          )}
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              onClick={() => onSelect(row.original.event_id)}
              onKeyDown={(e) => { if (e.key === 'Enter') onSelect(row.original.event_id); }}
              tabIndex={0}
              className={`cursor-pointer border-b border-border-primary transition-colors ${
                row.original.event_id === selectedId
                  ? 'bg-accent/10'
                  : 'hover:bg-bg-tertiary'
              }`}
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-3 py-2 text-text-secondary">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
