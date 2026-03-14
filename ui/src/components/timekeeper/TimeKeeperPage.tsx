// BlackBoard/ui/src/components/timekeeper/TimeKeeperPage.tsx
import { useState } from 'react';
import { Plus } from 'lucide-react';
import { useSchedules, useCreateSchedule, useUpdateSchedule, useDeleteSchedule, useToggleSchedule } from '../../hooks/useTimeKeeper';
import type { ScheduleCreatePayload, ScheduleItem } from '../../api/client';
import ScheduleStats from './ScheduleStats';
import ScheduleList from './ScheduleList';
import ScheduleForm from './ScheduleForm';

export default function TimeKeeperPage() {
  const { data: schedules = [], isLoading } = useSchedules();
  const createMutation = useCreateSchedule();
  const updateMutation = useUpdateSchedule();
  const deleteMutation = useDeleteSchedule();
  const toggleMutation = useToggleSchedule();

  const [showForm, setShowForm] = useState(false);
  const [editItem, setEditItem] = useState<ScheduleItem | null>(null);

  function handleCreate(payload: ScheduleCreatePayload) {
    createMutation.mutate(payload, { onSuccess: () => setShowForm(false) });
  }

  function handleUpdate(payload: ScheduleCreatePayload) {
    if (!editItem) return;
    updateMutation.mutate({ id: editItem.id, payload }, { onSuccess: () => setEditItem(null) });
  }

  function handleDelete(id: string) {
    if (!confirm('Delete this schedule?')) return;
    deleteMutation.mutate(id);
  }

  return (
    <div className="h-full flex flex-col p-6 gap-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">TimeKeeper</h1>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent text-white text-sm font-semibold hover:bg-accent/80 transition-colors cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          New Schedule
        </button>
      </div>

      <ScheduleStats schedules={schedules} />

      {isLoading ? (
        <div className="text-center text-text-secondary py-12">Loading schedules...</div>
      ) : (
        <div className="flex-1 rounded-xl bg-bg-secondary border border-border overflow-hidden">
          <ScheduleList
            schedules={schedules}
            onEdit={(s) => setEditItem(s)}
            onToggle={(id) => toggleMutation.mutate(id)}
            onDelete={handleDelete}
          />
        </div>
      )}

      <div className="text-xs text-text-secondary">
        Showing {schedules.length} schedules (max {import.meta.env.VITE_TK_MAX_PER_USER || 10}/user, {import.meta.env.VITE_TK_MAX_TOTAL || 50} system)
      </div>

      {showForm && (
        <ScheduleForm
          onClose={() => setShowForm(false)}
          onSubmit={handleCreate}
          isSubmitting={createMutation.isPending}
        />
      )}

      {editItem && (
        <ScheduleForm
          onClose={() => setEditItem(null)}
          onSubmit={handleUpdate}
          editItem={editItem}
          isSubmitting={updateMutation.isPending}
        />
      )}
    </div>
  );
}
