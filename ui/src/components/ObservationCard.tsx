// BlackBoard/ui/src/components/ObservationCard.tsx
// @ai-rules:
// 1. [Pattern]: Self-contained card with recharts sparkline + stats.
// 2. [Constraint]: Uses snake_case props matching API types.
// 3. [Pattern]: Kebab menu for rename/delete. Checkbox for bulk selection.
// 4. [Pattern]: Inline rename input — PATCH on Enter/blur, validates client-side.
/**
 * Single observation series card with sparkline, kebab menu, and selection checkbox.
 */
import { useMemo, useState, useRef, useEffect } from 'react';
import { LineChart, Line, ResponsiveContainer, Tooltip, YAxis } from 'recharts';
import { TrendingUp, TrendingDown, Minus, MoreVertical, Pencil, Trash2, Download } from 'lucide-react';
import type { ObservationSeries } from '../api/types';

const TREND_CONFIG = {
  rising: { icon: TrendingUp, color: '#f59e0b', label: 'Rising' },
  falling: { icon: TrendingDown, color: '#22c55e', label: 'Falling' },
  stable: { icon: Minus, color: '#64748b', label: 'Stable' },
} as const;

// Fallback only — the server (BlackboardState.OBS_NAME_PATTERN) is the source of
// truth, delivered via ObservationsResponse.name_pattern. Used if that's unavailable.
const FALLBACK_OBS_NAME_PATTERN = '^[a-z][a-z0-9_]{1,63}$';

// Fallback only — the server (BlackboardState.OBS_MAX_REPORT_SERIES) is the source of
// truth, delivered via ObservationsResponse.max_report_series. Used if that's unavailable.
const FALLBACK_MAX_REPORT_SERIES = 10;

interface Props {
  series: ObservationSeries;
  namePattern?: string;
  maxReportSeries?: number;
  selected?: boolean;
  selectionDisabled?: boolean;
  onToggleSelect?: (name: string) => void;
  onDelete?: (name: string) => void;
  onRename?: (oldName: string, newName: string) => void;
  onExport?: (name: string) => void;
}

export default function ObservationCard({
  series, namePattern, maxReportSeries, selected, selectionDisabled, onToggleSelect, onDelete, onRename, onExport,
}: Props) {
  const nameRe = useMemo(() => {
    // Guard against a future backend regex change that's Python-valid but JS-invalid --
    // fall back rather than throwing inside this render-path useMemo.
    try {
      return new RegExp(namePattern || FALLBACK_OBS_NAME_PATTERN);
    } catch {
      return new RegExp(FALLBACK_OBS_NAME_PATTERN);
    }
  }, [namePattern]);
  const { icon: TrendIcon, color: trendColor, label: trendLabel } = TREND_CONFIG[series.trend];
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(series.name);
  const [renameError, setRenameError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (renaming) inputRef.current?.focus();
  }, [renaming]);

  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  const commitRename = () => {
    const trimmed = renameValue.trim();
    if (trimmed === series.name) { setRenaming(false); return; }
    if (!nameRe.test(trimmed)) {
      setRenameError(`Must match ${namePattern || FALLBACK_OBS_NAME_PATTERN}`);
      return;
    }
    setRenameError('');
    onRename?.(series.name, trimmed);
    setRenaming(false);
  };

  const chartData = series.points.map(p => ({
    value: p.value,
    ts: p.timestamp.replace('T', ' ').replace('Z', ''),
  }));

  return (
    <div className="bg-bg-secondary border border-border rounded-lg p-4 relative group">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          {onToggleSelect && (
            <input
              type="checkbox"
              checked={selected ?? false}
              disabled={selectionDisabled && !selected}
              title={selectionDisabled && !selected ? `Maximum ${maxReportSeries ?? FALLBACK_MAX_REPORT_SERIES} series per report` : undefined}
              onChange={() => onToggleSelect(series.name)}
              className="accent-amber-500 flex-shrink-0"
            />
          )}
          {renaming ? (
            <div className="flex flex-col">
              <input
                ref={inputRef}
                value={renameValue}
                onChange={e => { setRenameValue(e.target.value); setRenameError(''); }}
                onKeyDown={e => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') setRenaming(false); }}
                onBlur={commitRename}
                className="text-sm font-medium text-text-primary bg-bg-tertiary border border-border-primary rounded px-1.5 py-0.5 w-full"
              />
              {renameError && <span className="text-xs text-red-400 mt-0.5">{renameError}</span>}
            </div>
          ) : (
            <h3 className="text-sm font-medium text-text-primary truncate">{series.name}</h3>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          <div className="flex items-center gap-1 text-xs" style={{ color: trendColor }}>
            <TrendIcon size={14} />
            <span>{trendLabel}</span>
          </div>

          {(onDelete || onRename || onExport) && (
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setMenuOpen(o => !o)}
                className="p-1 rounded hover:bg-bg-tertiary text-text-muted opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <MoreVertical size={14} />
              </button>
              {menuOpen && (
                <div className="absolute right-0 top-7 z-20 bg-bg-tertiary border border-border rounded-md shadow-lg py-1 min-w-[120px]">
                  {onRename && (
                    <button
                      onClick={() => { setMenuOpen(false); setRenameValue(series.name); setRenaming(true); }}
                      className="flex items-center gap-2 w-full px-3 py-1.5 text-xs text-text-primary hover:bg-bg-secondary"
                    >
                      <Pencil size={12} /> Rename
                    </button>
                  )}
                  {onExport && (
                    <button
                      onClick={() => { setMenuOpen(false); onExport(series.name); }}
                      className="flex items-center gap-2 w-full px-3 py-1.5 text-xs text-text-primary hover:bg-bg-secondary"
                    >
                      <Download size={12} /> Export CSV
                    </button>
                  )}
                  {onDelete && (
                    <button
                      onClick={() => {
                        setMenuOpen(false);
                        if (confirm(`Delete observation "${series.name}"? This cannot be undone.`)) {
                          onDelete(series.name);
                        }
                      }}
                      className="flex items-center gap-2 w-full px-3 py-1.5 text-xs text-red-400 hover:bg-bg-secondary"
                    >
                      <Trash2 size={12} /> Delete
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="h-16 mb-3">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <YAxis domain={['auto', 'auto']} hide />
            <Tooltip
              contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 6, fontSize: 12 }}
              labelStyle={{ color: '#94a3b8' }}
              formatter={(val: number | undefined) => [`${val ?? 0} ${series.unit}`, series.name]}
              labelFormatter={(label) => String(label)}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={trendColor}
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 3, fill: trendColor }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs text-text-secondary">
        <div>
          <span className="text-text-muted">Latest</span>
          <div className="text-text-primary font-mono">
            {series.latest_value} {series.unit}
          </div>
        </div>
        <div>
          <span className="text-text-muted">Range</span>
          <div className="text-text-primary font-mono">
            {series.min}–{series.max}
          </div>
        </div>
        <div>
          <span className="text-text-muted">Points</span>
          <div className="text-text-primary font-mono">
            {series.count} / {series.span_minutes}m
          </div>
        </div>
      </div>
    </div>
  );
}
