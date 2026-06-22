// BlackBoard/ui/src/components/notebook/NotebookPanel.tsx
// @ai-rules:
// 1. [Pattern]: React Query for GET/PATCH/DELETE. invalidateQueries on mutation success.
// 2. [Pattern]: Inline edit on click → input, blur/Enter → PATCH. Hover-reveal dismiss → DELETE.
// 3. [Gotcha]: During Nightwatcher drain (~seconds per 12h), PATCH/DELETE may 404 — acceptable UX.
import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Trash2, FileText, Pencil, Check, X } from 'lucide-react';
import { getNotebook, updateNote, deleteNote } from '../../api/client';
import type { FieldNote } from '../../api/types';

const CATEGORY_COLORS: Record<string, string> = {
  'env-quirk': 'bg-amber-500/20 text-amber-300',
  correction: 'bg-red-500/20 text-red-300',
  'cross-event': 'bg-purple-500/20 text-purple-300',
  workflow: 'bg-blue-500/20 text-blue-300',
  convention: 'bg-emerald-500/20 text-emerald-300',
};

export default function NotebookPanel() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['notebook'],
    queryFn: getNotebook,
    refetchInterval: 30_000,
  });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');

  const patchMutation = useMutation({
    mutationFn: (vars: { id: string; content: string }) =>
      updateNote(vars.id, { content: vars.content }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notebook'] });
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteNote(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notebook'] }),
  });

  const startEdit = useCallback((note: FieldNote) => {
    setEditingId(note.note_id);
    setEditContent(note.content);
  }, []);

  const commitEdit = useCallback((noteId: string) => {
    if (editContent.trim()) {
      patchMutation.mutate({ id: noteId, content: editContent.trim() });
    } else {
      setEditingId(null);
    }
  }, [editContent, patchMutation]);

  if (isLoading) {
    return <div className="flex items-center justify-center h-full text-text-muted text-sm">Loading field notes...</div>;
  }
  if (isError) {
    return <div className="flex items-center justify-center h-full text-red-400 text-sm">Failed to load field notes.</div>;
  }

  const notes = data?.notes ?? [];

  if (notes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-text-muted">
        <FileText size={28} className="opacity-40" />
        <p className="text-sm">No field notes yet.</p>
        <p className="text-xs opacity-60">FRIDAY will capture knowledge during event processing.</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <h2 className="text-sm font-semibold text-text-primary mb-3">
        Field Notes <span className="text-text-muted font-normal">({notes.length})</span>
      </h2>
      <div className="space-y-2">
        {notes.map(note => (
          <div key={note.note_id} className="group relative rounded-lg border border-border bg-bg-secondary p-3 hover:border-border-hover transition-colors">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium ${CATEGORY_COLORS[note.category] ?? 'bg-gray-500/20 text-gray-300'}`}>
                    {note.category}
                  </span>
                  <span className="text-[10px] text-text-muted truncate">
                    evt:{note.event_id.slice(0, 8)}
                  </span>
                  <span className="text-[10px] text-text-muted">
                    {new Date(note.timestamp).toLocaleString()}
                  </span>
                </div>
                {editingId === note.note_id ? (
                  <div className="flex items-start gap-1">
                    <textarea
                      className="flex-1 bg-bg-primary border border-border rounded px-2 py-1 text-xs text-text-primary resize-none focus:outline-none focus:border-accent"
                      value={editContent}
                      onChange={e => setEditContent(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); commitEdit(note.note_id); }
                        if (e.key === 'Escape') setEditingId(null);
                      }}
                      rows={3}
                      maxLength={2000}
                      autoFocus
                    />
                    <button onClick={() => commitEdit(note.note_id)} className="p-1 text-emerald-400 hover:text-emerald-300" title="Save">
                      <Check size={14} />
                    </button>
                    <button onClick={() => setEditingId(null)} className="p-1 text-text-muted hover:text-text-secondary" title="Cancel">
                      <X size={14} />
                    </button>
                  </div>
                ) : (
                  <p className="text-xs text-text-secondary whitespace-pre-wrap break-words">{note.content}</p>
                )}
              </div>
              {editingId !== note.note_id && (
                <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                  <button onClick={() => startEdit(note)} className="p-1 text-text-muted hover:text-accent" title="Edit">
                    <Pencil size={12} />
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(note.note_id)}
                    className="p-1 text-text-muted hover:text-red-400"
                    title="Dismiss"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
