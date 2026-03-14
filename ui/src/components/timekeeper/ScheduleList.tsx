// BlackBoard/ui/src/components/timekeeper/ScheduleList.tsx
import { Pause, Play, Pencil, Trash2 } from 'lucide-react';
import type { ScheduleItem } from '../../api/client';

interface Props {
  schedules: ScheduleItem[];
  onEdit: (sched: ScheduleItem) => void;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
}

function formatNextFire(fireAt: number): string {
  const diff = fireAt - Date.now() / 1000;
  if (diff < 0) return 'Overdue';
  if (diff < 3600) return `In ${Math.round(diff / 60)}m`;
  if (diff < 86400) return `In ${Math.round(diff / 3600)}h`;
  return new Date(fireAt * 1000).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

export default function ScheduleList({ schedules, onEdit, onToggle, onDelete }: Props) {
  if (schedules.length === 0) {
    return (
      <div className="text-center text-text-secondary py-12">
        No schedules yet. Click <span className="text-accent font-semibold">+ New Schedule</span> to create one.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-text-secondary text-xs border-b border-border">
            <th className="text-left py-2 px-3 w-8"></th>
            <th className="text-left py-2 px-3">Name</th>
            <th className="text-left py-2 px-3">Service</th>
            <th className="text-left py-2 px-3">Next Fire</th>
            <th className="text-left py-2 px-3">Schedule</th>
            <th className="text-left py-2 px-3">By</th>
            <th className="text-right py-2 px-3 w-28">Actions</th>
          </tr>
        </thead>
        <tbody>
          {schedules.map((s) => {
            const isPending = s.enabled && s.fire_at - Date.now() / 1000 < 14400;
            return (
              <tr
                key={s.id}
                className="border-b border-border/50 hover:bg-bg-secondary/50 transition-colors"
              >
                <td className="py-2 px-3">
                  <span
                    className={`inline-block w-2.5 h-2.5 rounded-full ${
                      !s.enabled
                        ? 'bg-gray-500'
                        : isPending
                          ? 'bg-amber-400'
                          : 'bg-status-healthy'
                    }`}
                    title={!s.enabled ? 'Paused' : isPending ? 'Pending fire' : 'Active'}
                  />
                </td>
                <td className="py-2 px-3">
                  <div className="font-medium text-text-primary">{s.name}</div>
                  <div className="text-xs text-text-secondary mt-0.5 truncate max-w-[300px]">
                    {s.instructions.slice(0, 80)}
                    {s.instructions.length > 80 ? '...' : ''}
                  </div>
                </td>
                <td className="py-2 px-3 text-text-secondary">{s.service || 'general'}</td>
                <td className="py-2 px-3">
                  <span className={`text-xs font-mono ${isPending ? 'text-amber-400' : 'text-text-secondary'}`}>
                    {s.enabled ? formatNextFire(s.fire_at) : '—'}
                  </span>
                </td>
                <td className="py-2 px-3">
                  <span className="text-xs font-mono text-text-secondary">
                    {s.schedule_type === 'recurring' ? s.cron : 'One-shot'}
                  </span>
                </td>
                <td className="py-2 px-3 text-xs text-text-secondary truncate max-w-[140px]">
                  {s.created_by}
                </td>
                <td className="py-2 px-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={() => onEdit(s)}
                      className="p-1 rounded hover:bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
                      title="Edit"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => onToggle(s.id)}
                      className="p-1 rounded hover:bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
                      title={s.enabled ? 'Pause' : 'Resume'}
                    >
                      {s.enabled ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                    </button>
                    <button
                      onClick={() => onDelete(s.id)}
                      className="p-1 rounded hover:bg-bg-tertiary text-red-400 hover:text-red-300 transition-colors cursor-pointer"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
