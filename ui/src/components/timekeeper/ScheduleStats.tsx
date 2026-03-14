// BlackBoard/ui/src/components/timekeeper/ScheduleStats.tsx
import type { ScheduleItem } from '../../api/client';

interface Props {
  schedules: ScheduleItem[];
}

export default function ScheduleStats({ schedules }: Props) {
  const active = schedules.filter((s) => s.enabled).length;
  const paused = schedules.filter((s) => !s.enabled).length;
  const now = Date.now() / 1000;
  const firedToday = schedules.filter(
    (s) => s.last_fired && now - s.last_fired < 86400,
  ).length;

  const stats = [
    { label: 'Active', value: active, color: 'text-status-healthy' },
    { label: 'Paused', value: paused, color: 'text-text-secondary' },
    { label: 'Fired Today', value: firedToday, color: 'text-accent' },
    { label: 'Total', value: schedules.length, color: 'text-text-primary' },
  ];

  return (
    <div className="flex gap-3">
      {stats.map((s) => (
        <div
          key={s.label}
          className="flex items-center gap-2 rounded-lg bg-bg-secondary px-3 py-2 border border-border"
        >
          <span className={`text-lg font-bold ${s.color}`}>{s.value}</span>
          <span className="text-xs text-text-secondary">{s.label}</span>
        </div>
      ))}
    </div>
  );
}
