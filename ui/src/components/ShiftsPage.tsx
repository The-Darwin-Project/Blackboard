// BlackBoard/ui/src/components/ShiftsPage.tsx
// @ai-rules:
// 1. [Pattern]: Page shell following IncidentsPage 3-state pattern (loading, error/empty, populated).
// 2. [Pattern]: ShiftStatusBanner at top, ShiftCalendar below. Detail view on card click.
// 3. [Pattern]: Week navigation via ISO week string. "Today" pill jumps to current week.
/**
 * Shifts page -- Nightwatcher shift calendar and detail views.
 */
import { useState, useMemo } from 'react';
import { Clock, ChevronLeft, ChevronRight, Moon } from 'lucide-react';
import { useCurrentShift, useShiftsList, useShiftDetail } from '../hooks/useShifts';
import { SHIFT_STATUS_COLORS } from '../constants/colors';
import type { ShiftReportSummary, ShiftReportFull } from '../api/types';

function getISOWeek(date: Date): string {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const weekNum = Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(weekNum).padStart(2, '0')}`;
}

function getWeekDates(weekStr: string): Date[] {
  const [yearStr, weekPart] = weekStr.split('-W');
  const jan4 = new Date(Date.UTC(parseInt(yearStr), 0, 4));
  const monday = new Date(jan4.getTime());
  monday.setUTCDate(jan4.getUTCDate() - ((jan4.getUTCDay() + 6) % 7) + (parseInt(weekPart) - 1) * 7);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday.getTime());
    d.setUTCDate(monday.getUTCDate() + i);
    return d;
  });
}

function shiftWeek(week: string, delta: number): string {
  const dates = getWeekDates(week);
  const d = new Date(dates[0].getTime());
  d.setUTCDate(d.getUTCDate() + delta * 7);
  return getISOWeek(d);
}

export default function ShiftsPage() {
  const [week, setWeek] = useState(() => getISOWeek(new Date()));
  const [selectedShift, setSelectedShift] = useState<{ date: string; window: string } | null>(null);

  const { data: current } = useCurrentShift();
  const { data: shifts, isLoading } = useShiftsList(week);
  const { data: detail } = useShiftDetail(selectedShift?.date ?? '', selectedShift?.window ?? '');

  const todayStr = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const weekDates = useMemo(() => getWeekDates(week), [week]);
  const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  const shiftMap = useMemo(() => {
    const map: Record<string, ShiftReportSummary> = {};
    for (const s of shifts ?? []) map[`${s.shift_date}:${s.window}`] = s;
    return map;
  }, [shifts]);

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {/* Status Banner */}
      {current && (
        <div className="flex items-center gap-3 p-3 rounded-lg bg-bg-secondary border border-border">
          <Moon className="w-4 h-4 text-indigo-400" />
          <span className="text-xs text-text-secondary">
            {current.pending_count > 0
              ? `${current.pending_count} escalations pending`
              : 'No pending escalations'}
          </span>
          {current.next_sweep_utc && (
            <span className="text-xs text-text-muted ml-auto flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Next sweep: {new Date(current.next_sweep_utc).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })} UTC
            </span>
          )}
        </div>
      )}

      {/* Week Navigation */}
      <div className="flex items-center gap-2">
        <button onClick={() => setWeek(w => shiftWeek(w, -1))}
          className="p-1.5 rounded hover:bg-bg-tertiary text-text-muted">
          <ChevronLeft className="w-4 h-4" />
        </button>
        <span className="text-sm font-medium text-text-primary min-w-[90px] text-center">{week}</span>
        <button onClick={() => setWeek(w => shiftWeek(w, 1))}
          className="p-1.5 rounded hover:bg-bg-tertiary text-text-muted">
          <ChevronRight className="w-4 h-4" />
        </button>
        <button onClick={() => setWeek(getISOWeek(new Date()))}
          className="px-2 py-1 rounded text-xs text-accent hover:bg-accent/10">Today</button>
      </div>

      {/* Calendar Grid */}
      {isLoading ? (
        <div className="grid grid-cols-7 gap-2">
          {Array.from({ length: 14 }).map((_, i) => (
            <div key={i} className="h-24 rounded-lg bg-bg-secondary animate-pulse" />
          ))}
        </div>
      ) : (
        <div>
          {/* Day headers */}
          <div className="grid grid-cols-7 gap-2 mb-1">
            {weekDates.map((d, i) => (
              <div key={i} className="text-center">
                <div className="text-[10px] text-text-muted">{dayNames[i]}</div>
                <div className={`text-xs font-medium ${d.toISOString().slice(0, 10) === todayStr ? 'text-accent' : 'text-text-secondary'}`}>
                  {d.getUTCDate()}
                </div>
              </div>
            ))}
          </div>
          {/* Morning row */}
          <div className="grid grid-cols-7 gap-2 mb-2">
            {weekDates.map((d) => {
              const dateStr = d.toISOString().slice(0, 10);
              const shift = shiftMap[`${dateStr}:morning`];
              return <ShiftCard key={`m-${dateStr}`} dateStr={dateStr} window="morning" shift={shift}
                onClick={() => setSelectedShift({ date: dateStr, window: 'morning' })}
                isSelected={selectedShift?.date === dateStr && selectedShift?.window === 'morning'} />;
            })}
          </div>
          {/* Evening row */}
          <div className="grid grid-cols-7 gap-2">
            {weekDates.map((d) => {
              const dateStr = d.toISOString().slice(0, 10);
              const shift = shiftMap[`${dateStr}:evening`];
              return <ShiftCard key={`e-${dateStr}`} dateStr={dateStr} window="evening" shift={shift}
                onClick={() => setSelectedShift({ date: dateStr, window: 'evening' })}
                isSelected={selectedShift?.date === dateStr && selectedShift?.window === 'evening'} />;
            })}
          </div>
        </div>
      )}

      {/* Detail Panel */}
      {selectedShift && detail && <ShiftDetailPanel report={detail} onClose={() => setSelectedShift(null)} />}
    </div>
  );
}

function ShiftCard({ dateStr, window: w, shift, onClick, isSelected }: {
  dateStr: string; window: string; shift?: ShiftReportSummary;
  onClick: () => void; isSelected: boolean;
}) {
  const status = shift?.status ?? 'empty';
  const colors = SHIFT_STATUS_COLORS[status] || SHIFT_STATUS_COLORS.empty;
  const isFuture = new Date(`${dateStr}T${w === 'morning' ? '06' : '18'}:00:00Z`) > new Date();

  return (
    <button onClick={onClick}
      className={`p-2 rounded-lg text-left transition-all h-24 flex flex-col justify-between
        ${isSelected ? 'ring-1 ring-accent' : ''}
        ${isFuture && !shift ? 'border border-dashed' : 'border'}
      `}
      style={{ borderColor: colors.border, background: colors.bg }}>
      <div className="text-[10px] font-medium" style={{ color: colors.text }}>
        {w === 'morning' ? '06:00' : '18:00'}
      </div>
      {shift && shift.status !== 'empty' ? (
        <>
          <div className="text-xs text-text-primary font-medium">
            {shift.escalation_count} → {shift.incident_count}
          </div>
          {shift.noise_reduction_pct > 0 && (
            <div className="w-full bg-bg-tertiary rounded-full h-1.5">
              <div className="h-1.5 rounded-full bg-green-500"
                style={{ width: `${Math.min(shift.noise_reduction_pct, 100)}%` }} />
            </div>
          )}
          <div className="text-[10px] text-text-muted">
            {shift.noise_reduction_pct > 0 ? `${shift.noise_reduction_pct.toFixed(0)}% reduced` : 'no reduction'}
          </div>
        </>
      ) : (
        <div className="text-[10px] text-text-muted">{isFuture ? 'pending' : 'no data'}</div>
      )}
    </button>
  );
}

function ShiftDetailPanel({ report, onClose }: { report: ShiftReportFull; onClose: () => void }) {
  const duration = report.metrics?.sweep_duration_s;
  return (
    <div className="bg-bg-secondary border border-border rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">
          {report.shift_date} {report.window} shift
        </h3>
        <button onClick={onClose} className="text-xs text-text-muted hover:text-text-secondary">Close</button>
      </div>

      {/* Metrics bar */}
      <div className="flex gap-4 text-xs text-text-secondary">
        <span>{report.metrics?.escalation_count ?? 0} escalations</span>
        <span>{report.metrics?.incident_count ?? 0} incidents</span>
        <span>{(report.metrics?.noise_reduction_pct ?? 0).toFixed(0)}% reduced</span>
        {duration != null && <span>{duration.toFixed(1)}s sweep</span>}
      </div>

      {/* Incidents */}
      {report.incidents.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide">Consolidated Incidents</h4>
          {report.incidents.map((inc, i) => (
            <details key={i} className="bg-bg-tertiary rounded-lg p-3">
              <summary className="cursor-pointer text-sm text-text-primary flex items-center gap-2">
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                  inc.priority === 'Critical' ? 'bg-red-500/20 text-red-400' :
                  inc.priority === 'Major' ? 'bg-amber-500/20 text-amber-400' :
                  'bg-slate-500/20 text-slate-400'
                }`}>{inc.priority}</span>
                <span className="text-[10px] text-text-muted">{inc.platform}</span>
                <span className="flex-1 truncate">{inc.summary}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                  inc.status === 'Self-Resolved' ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'
                }`}>{inc.status || 'New'}</span>
              </summary>
              <div className="mt-2 text-xs text-text-secondary space-y-1">
                <p>{inc.description}</p>
                <p className="text-text-muted">
                  {inc.affected_events.length} events: {inc.affected_events.join(', ')}
                </p>
                {(inc.jira_url || inc.smartsheet_url) && (
                  <a href={inc.jira_url || inc.smartsheet_url} target="_blank" rel="noopener noreferrer"
                    className="text-accent hover:underline">View in Jira</a>
                )}
              </div>
            </details>
          ))}
        </div>
      )}

      {/* Investigations */}
      {report.investigations.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide">On-Call Investigations</h4>
          {report.investigations.map((inv, i) => (
            <details key={i} className="bg-bg-tertiary rounded-lg p-3">
              <summary className="cursor-pointer text-sm text-text-primary flex items-center gap-2">
                <span className="text-[10px] text-text-muted">{inv.service}</span>
                <span className="flex-1 truncate">{inv.task}</span>
                <span className="text-[10px] text-text-muted">{inv.duration_seconds.toFixed(1)}s</span>
              </summary>
              <pre className="mt-2 text-xs text-text-secondary whitespace-pre-wrap bg-bg-primary rounded p-2 max-h-60 overflow-y-auto">
                {inv.agent_result}
              </pre>
            </details>
          ))}
        </div>
      )}

      {/* Manifest */}
      {report.manifest.length > 0 && (
        <details className="bg-bg-tertiary rounded-lg p-3">
          <summary className="cursor-pointer text-xs font-medium text-text-muted uppercase tracking-wide">
            Raw Manifest ({report.manifest.length} escalations)
          </summary>
          <div className="mt-2 space-y-1 max-h-60 overflow-y-auto">
            {report.manifest.map((e) => (
              <div key={e.event_id} className="text-xs text-text-secondary flex gap-2">
                <span className="font-mono text-text-muted">{e.event_id}</span>
                <span className="truncate flex-1">{e.service}</span>
                <span className="text-text-muted">{e.platform}</span>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Shift Summary */}
      {report.summary_text && (
        <div className="text-xs text-text-secondary bg-bg-tertiary rounded-lg p-3">
          <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide mb-1">Slack Summary</h4>
          <p className="whitespace-pre-wrap">{report.summary_text}</p>
        </div>
      )}
    </div>
  );
}
