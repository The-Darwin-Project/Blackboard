// BlackBoard/ui/src/components/memory/LessonsView.tsx
// @ai-rules:
// 1. [Pattern]: Table view of lessons learned with creation form and delete.
// 2. [Pattern]: 3 states: loading, empty, populated. Same pattern as IncidentsPage.
import { useState } from 'react';
import { Plus, Trash2, BookOpen } from 'lucide-react';
import { useLessons, useCreateLesson, useDeleteLesson } from '../../hooks/useMemory';

interface LessonForm {
  title: string;
  pattern: string;
  anti_pattern: string;
  keywords: string;
  event_references: string;
}

const EMPTY_FORM: LessonForm = { title: '', pattern: '', anti_pattern: '', keywords: '', event_references: '' };

export default function LessonsView() {
  const { data: lessons, isLoading, isError } = useLessons();
  const createMutation = useCreateLesson();
  const deleteMutation = useDeleteLesson();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<LessonForm>(EMPTY_FORM);
  const [expanded, setExpanded] = useState<string | null>(null);

  if (isLoading) {
    return <div className="flex items-center justify-center h-full text-text-muted text-sm">Loading lessons...</div>;
  }
  if (isError) {
    return <div className="flex items-center justify-center h-full text-red-400 text-sm">Failed to load lessons.</div>;
  }

  const submitLesson = () => {
    createMutation.mutate({
      title: form.title,
      pattern: form.pattern,
      anti_pattern: form.anti_pattern || undefined,
      keywords: form.keywords ? form.keywords.split(',').map(k => k.trim()).filter(Boolean) : undefined,
      event_references: form.event_references ? form.event_references.split(',').map(e => e.trim()).filter(Boolean) : undefined,
    }, {
      onSuccess: () => { setForm(EMPTY_FORM); setShowForm(false); },
    });
  };

  const items = lessons || [];

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text-primary">
          Lessons Learned <span className="text-text-muted font-normal">({items.length})</span>
        </h2>
        <button onClick={() => setShowForm(!showForm)}
          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded text-xs font-medium bg-accent/20 text-accent hover:bg-accent/30 transition-colors">
          <Plus size={12} /> New Lesson
        </button>
      </div>

      {showForm && (
        <div className="mb-4 border border-border rounded-lg p-4 bg-bg-secondary space-y-2">
          <div>
            <label className="block text-[10px] text-text-muted mb-1">Title</label>
            <input className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-xs text-text-primary"
              value={form.title} onChange={e => setForm({ ...form, title: e.target.value })}
              placeholder="Pipeline failure triage: infrastructure vs. compliance" />
          </div>
          <div>
            <label className="block text-[10px] text-text-muted mb-1">Pattern (what the correct behavior should be)</label>
            <textarea className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-xs text-text-primary resize-none"
              rows={3} value={form.pattern} onChange={e => setForm({ ...form, pattern: e.target.value })}
              placeholder="When multiple tasks fail in a pipeline, infrastructure failures take precedence..." />
          </div>
          <div>
            <label className="block text-[10px] text-text-muted mb-1">Anti-pattern (what the wrong behavior looks like)</label>
            <textarea className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-xs text-text-primary resize-none"
              rows={2} value={form.anti_pattern} onChange={e => setForm({ ...form, anti_pattern: e.target.value })}
              placeholder="Selecting the most parseable output as root cause..." />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[10px] text-text-muted mb-1">Keywords (comma-separated)</label>
              <input className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-xs text-text-primary"
                value={form.keywords} onChange={e => setForm({ ...form, keywords: e.target.value })}
                placeholder="pipeline, infrastructure, image-pull" />
            </div>
            <div>
              <label className="block text-[10px] text-text-muted mb-1">Event References (comma-separated)</label>
              <input className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-xs text-text-primary"
                value={form.event_references} onChange={e => setForm({ ...form, event_references: e.target.value })}
                placeholder="evt-1b7bb120, evt-f2e5db65" />
            </div>
          </div>
          <div className="flex gap-2 pt-1">
            <button onClick={submitLesson} disabled={!form.title || !form.pattern || createMutation.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-green-500/20 text-green-400 hover:bg-green-500/30 transition-colors disabled:opacity-50">
              {createMutation.isPending ? 'Storing...' : 'Store Lesson'}
            </button>
            <button onClick={() => { setShowForm(false); setForm(EMPTY_FORM); }}
              className="px-3 py-1.5 rounded text-xs font-medium text-text-muted hover:bg-bg-tertiary transition-colors">
              Cancel
            </button>
          </div>
        </div>
      )}

      {items.length === 0 && !showForm ? (
        <div className="flex flex-col items-center justify-center py-16 gap-2 text-text-muted">
          <BookOpen size={24} className="opacity-50" />
          <span className="text-sm">No lessons learned yet.</span>
          <span className="text-xs">Create one manually or use the Extract wizard to extract from a document.</span>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((l) => {
            const p = l.payload;
            const isExpanded = expanded === p.lesson_id;
            return (
              <div key={p.lesson_id}
                className="border border-border rounded-lg bg-bg-secondary hover:bg-bg-tertiary transition-colors cursor-pointer"
                onClick={() => setExpanded(isExpanded ? null : p.lesson_id)}>
                <div className="px-4 py-3 flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-text-primary">{p.title}</div>
                    <div className="text-[11px] text-text-muted mt-1 line-clamp-2">{p.pattern}</div>
                    {p.keywords.length > 0 && (
                      <div className="flex gap-1 mt-1.5 flex-wrap">
                        {p.keywords.map(kw => (
                          <span key={kw} className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-accent/10 text-accent">{kw}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  <button onClick={(e) => {
                      e.stopPropagation();
                      if (window.confirm(`Delete lesson "${p.title}"? This cannot be undone.`)) {
                        deleteMutation.mutate(p.lesson_id);
                      }
                    }}
                    className="p-1.5 rounded text-text-muted hover:text-red-400 hover:bg-red-400/10 transition-colors"
                    title="Delete lesson">
                    <Trash2 size={12} />
                  </button>
                </div>
                {isExpanded && (
                  <div className="px-4 pb-3 border-t border-border pt-3 space-y-2 text-xs">
                    {p.anti_pattern && (
                      <div><span className="text-text-muted">Anti-pattern:</span> <span className="text-text-secondary">{p.anti_pattern}</span></div>
                    )}
                    {p.event_references.length > 0 && (
                      <div><span className="text-text-muted">Events:</span> <span className="text-text-secondary font-mono">{p.event_references.join(', ')}</span></div>
                    )}
                    <div><span className="text-text-muted">Created:</span> <span className="text-text-secondary">{new Date(p.created_at * 1000).toLocaleString()}</span></div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
