// BlackBoard/ui/src/components/timekeeper/ScheduleForm.tsx
import { useState } from 'react';
import { createPortal } from 'react-dom';
import { X, Sparkles, Loader2 } from 'lucide-react';
import { useRefineInstructions } from '../../hooks/useTimeKeeper';
import { useAuth } from '../../contexts/AuthContext';
import type { ScheduleCreatePayload, ScheduleItem } from '../../api/client';

interface Props {
  onClose: () => void;
  onSubmit: (payload: ScheduleCreatePayload) => void;
  editItem?: ScheduleItem | null;
  isSubmitting?: boolean;
}

const TEMPLATES = [
  { label: 'Review MR', service: '', instructions: 'Review merge request. If pipeline passed, merge. If failed, investigate and notify maintainers.' },
  { label: 'Security Audit', service: '', instructions: 'Audit dependencies for security vulnerabilities. Report high/critical findings. Create issue if remediation needed.' },
  { label: 'Health Check', service: '', instructions: 'Verify service is healthy. Check for anomalies in resource usage or error rates. Report findings.' },
  { label: 'Release Gate', service: '', instructions: 'Verify all open MRs for this release are merged. Confirm pipeline is green on main. Report blockers.' },
  { label: 'Custom', service: '', instructions: '' },
] as const;

export default function ScheduleForm({ onClose, onSubmit, editItem, isSubmitting }: Props) {
  const { user } = useAuth();
  const userEmail = user?.profile?.email || '';

  const [name, setName] = useState(editItem?.name ?? '');
  const [scheduleType, setScheduleType] = useState<'one_shot' | 'recurring'>(editItem?.schedule_type ?? 'one_shot');
  const [cron, setCron] = useState(editItem?.cron ?? '');
  const [fireAt, setFireAt] = useState(() => {
    if (editItem?.fire_at) {
      const d = new Date(editItem.fire_at * 1000);
      return d.toISOString().slice(0, 16);
    }
    return '';
  });
  const [repoUrl, setRepoUrl] = useState(editItem?.repo_url ?? '');
  const [mrUrl, setMrUrl] = useState(editItem?.mr_url ?? '');
  const [service, setService] = useState(editItem?.service ?? '');
  const [instructions, setInstructions] = useState(editItem?.instructions ?? '');
  const [approvalMode, setApprovalMode] = useState<'autonomous' | 'notify_and_wait'>(editItem?.approval_mode ?? 'autonomous');
  const [onFailure, setOnFailure] = useState<string>(editItem?.on_failure ?? 'notify');
  const [notifyEmails, setNotifyEmails] = useState(
    editItem?.notify_emails?.join(', ') || userEmail,
  );

  const refineMutation = useRefineInstructions();
  const [refinedText, setRefinedText] = useState<string | null>(null);
  const [refineReason, setRefineReason] = useState('');
  const [refineError, setRefineError] = useState('');

  function handleTemplate(tpl: (typeof TEMPLATES)[number]) {
    setInstructions(tpl.instructions);
    if (tpl.service) setService(tpl.service);
  }

  async function handleRefine() {
    if (!instructions.trim()) return;
    setRefineError('');
    setRefinedText(null);
    try {
      const res = await refineMutation.mutateAsync({
        raw_intent: instructions,
        repo_url: repoUrl || null,
        mr_url: mrUrl || null,
        service: service || null,
      });
      setRefinedText(res.refined);
      setRefineReason(res.reasoning);
    } catch (err: any) {
      const msg = err?.detail || err?.message || 'Refine failed. Check backend connection.';
      setRefineError(String(msg));
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const emails = notifyEmails
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const payload: ScheduleCreatePayload = {
      name,
      schedule_type: scheduleType,
      cron: scheduleType === 'recurring' ? cron : null,
      fire_at: scheduleType === 'one_shot' ? new Date(fireAt).getTime() / 1000 : null,
      repo_url: repoUrl || null,
      mr_url: mrUrl || null,
      service: service || null,
      instructions,
      approval_mode: approvalMode,
      on_failure: onFailure as ScheduleCreatePayload['on_failure'],
      notify_emails: emails,
    };
    onSubmit(payload);
  }

  const selectClass = 'w-full rounded-lg bg-bg-primary border border-border text-text-primary text-sm px-3 py-2 focus:outline-none focus:ring-1 focus:ring-accent';
  const inputClass = selectClass;
  const labelClass = 'block text-xs font-semibold text-text-secondary mb-1';

  const modal = (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.6)' }}>
      <div className="bg-bg-secondary border border-border rounded-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-lg font-bold text-text-primary">
            {editItem ? 'Edit Schedule' : 'Create New Schedule'}
          </h2>
          <button onClick={onClose} className="text-text-secondary hover:text-text-primary cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-5">
          {/* Templates */}
          {!editItem && (
            <div>
              <span className={labelClass}>Start from template</span>
              <div className="flex flex-wrap gap-2 mt-1">
                {TEMPLATES.map((t) => (
                  <button
                    key={t.label}
                    type="button"
                    onClick={() => handleTemplate(t)}
                    className="px-3 py-1.5 rounded-lg bg-bg-tertiary text-xs text-text-secondary hover:text-text-primary hover:bg-bg-primary border border-border transition-colors cursor-pointer"
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* WHEN */}
          <fieldset className="border border-border/50 rounded-lg p-4 space-y-3">
            <legend className="text-xs font-bold text-text-secondary px-2">WHEN</legend>
            <div className="flex gap-3 items-center">
              <label className="flex items-center gap-2 text-sm text-text-primary cursor-pointer">
                <input type="radio" checked={scheduleType === 'one_shot'} onChange={() => setScheduleType('one_shot')} />
                One-shot
              </label>
              <label className="flex items-center gap-2 text-sm text-text-primary cursor-pointer">
                <input type="radio" checked={scheduleType === 'recurring'} onChange={() => setScheduleType('recurring')} />
                Recurring
              </label>
            </div>
            {scheduleType === 'one_shot' ? (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelClass}>Date *</label>
                  <input
                    type="date"
                    value={fireAt.split('T')[0] || ''}
                    onChange={(e) => {
                      const timePart = fireAt.split('T')[1] || '09:00';
                      setFireAt(`${e.target.value}T${timePart}`);
                    }}
                    className={`${inputClass} color-scheme-dark`}
                    style={{ colorScheme: 'dark' }}
                    required
                  />
                </div>
                <div>
                  <label className={labelClass}>Time (UTC) *</label>
                  <input
                    type="time"
                    value={fireAt.split('T')[1] || ''}
                    onChange={(e) => {
                      const datePart = fireAt.split('T')[0] || new Date().toISOString().slice(0, 10);
                      setFireAt(`${datePart}T${e.target.value}`);
                    }}
                    className={`${inputClass} color-scheme-dark`}
                    style={{ colorScheme: 'dark' }}
                    required
                  />
                </div>
              </div>
            ) : (
              <div>
                <input type="text" value={cron} onChange={(e) => setCron(e.target.value)} placeholder="0 9 * * MON" className={inputClass} required />
                <span className="text-xs text-text-secondary mt-1 block">Cron expression (min: hourly)</span>
              </div>
            )}
          </fieldset>

          {/* WHAT */}
          <fieldset className="border border-border/50 rounded-lg p-4 space-y-3">
            <legend className="text-xs font-bold text-text-secondary px-2">WHAT</legend>
            <div>
              <label className={labelClass}>Schedule Name *</label>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} className={inputClass} required minLength={5} maxLength={120} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelClass}>Service</label>
                <input type="text" value={service} onChange={(e) => setService(e.target.value)} placeholder="general" className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>Repository URL</label>
                <input type="url" value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)} placeholder="https://..." className={inputClass} />
              </div>
            </div>
            <div>
              <label className={labelClass}>MR URL</label>
              <input type="url" value={mrUrl} onChange={(e) => setMrUrl(e.target.value)} placeholder="https://..." className={inputClass} />
            </div>
          </fieldset>

          {/* DESIRED OUTCOME */}
          <fieldset className="border border-border/50 rounded-lg p-4 space-y-3">
            <legend className="text-xs font-bold text-text-secondary px-2">DESIRED OUTCOME</legend>
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              className={`${inputClass} h-28 resize-y`}
              required
              minLength={10}
              maxLength={2000}
              placeholder="Describe the expected outcome..."
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-secondary">{instructions.length} / 2000</span>
              <button
                type="button"
                onClick={handleRefine}
                disabled={refineMutation.isPending || instructions.length < 3}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent/20 text-accent text-xs font-semibold hover:bg-accent/30 disabled:opacity-40 transition-colors cursor-pointer"
              >
                {refineMutation.isPending ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Refining...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    Refine with AI
                  </>
                )}
              </button>
            </div>
            {refineMutation.isPending && (
              <div className="rounded-lg bg-accent/5 border border-accent/20 px-3 py-3 flex items-center gap-3">
                <Loader2 className="w-4 h-4 animate-spin text-accent shrink-0" />
                <div>
                  <p className="text-xs text-accent font-semibold">Brain is refining your instructions...</p>
                  <p className="text-xs text-text-secondary mt-0.5">Aligning with agent capabilities and decision patterns</p>
                </div>
              </div>
            )}
            {refineError && (
              <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2">
                <p className="text-xs text-red-400">{refineError}</p>
              </div>
            )}
            {refinedText && (
              <div className="rounded-lg bg-bg-primary border border-accent/30 p-3 space-y-2">
                <p className="text-xs text-accent font-semibold">AI Suggestion</p>
                <p className="text-sm text-text-primary whitespace-pre-wrap">{refinedText}</p>
                <div className="flex gap-2">
                  <button type="button" onClick={() => setRefinedText(null)} className="text-xs text-text-secondary hover:text-text-primary cursor-pointer">
                    Keep Mine
                  </button>
                  <button
                    type="button"
                    onClick={() => { setInstructions(refinedText); setRefinedText(null); }}
                    className="text-xs text-accent font-semibold hover:underline cursor-pointer"
                  >
                    Accept
                  </button>
                </div>
              </div>
            )}
          </fieldset>

          {/* GUARDRAILS */}
          <fieldset className="border border-border/50 rounded-lg p-4 space-y-3">
            <legend className="text-xs font-bold text-text-secondary px-2">GUARDRAILS</legend>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelClass}>Approval Mode</label>
                <select value={approvalMode} onChange={(e) => setApprovalMode(e.target.value as any)} className={selectClass}>
                  <option value="autonomous">Autonomous</option>
                  <option value="notify_and_wait">Notify &amp; Wait</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>On Failure</label>
                <select value={onFailure} onChange={(e) => setOnFailure(e.target.value)} className={selectClass}>
                  <option value="notify">Notify humans</option>
                  <option value="close_event">Close event</option>
                  <option value="retry_once">Retry once</option>
                  <option value="escalate_human">Escalate to human</option>
                </select>
              </div>
            </div>
            <div>
              <label className={labelClass}>Notify Emails (comma-separated)</label>
              <input type="text" value={notifyEmails} onChange={(e) => setNotifyEmails(e.target.value)} placeholder="alice@example.com, bob@example.com" className={inputClass} />
            </div>
          </fieldset>

          {/* Submit */}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-text-secondary hover:text-text-primary transition-colors cursor-pointer">
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 rounded-lg bg-accent text-white text-sm font-semibold hover:bg-accent/80 disabled:opacity-50 transition-colors cursor-pointer"
            >
              {isSubmitting ? 'Creating...' : editItem ? 'Save Changes' : 'Create Schedule'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
