// ui/src/components/approval/ApprovalDecisionCard.tsx
// @ai-rules:
// 1. [Constraint]: Component must be <= 100 lines.
// 2. [Pattern]: Hooks MUST be strictly above early return null!

import { useState, useRef, useEffect, useMemo } from 'react';
import type { ConversationTurn, ApprovalOption, DecisionPayload } from '../../api/types';
import { ApiError, submitApprovalDecision } from '../../api/client';
import { ApprovalWriteInBox } from './ApprovalWriteInBox';

interface Props { eventId: string; turn: ConversationTurn; onStatusChange?: () => void; }
interface ErrState { type: 'drift' | 'blocked' | 'other'; detail: string; liveSha?: string; reqSha?: string; }

export function ApprovalDecisionCard({ eventId, turn, onStatusChange }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [writeInText, setWriteInText] = useState('');
  const [writeInImage, setWriteInImage] = useState<string | null>(null);
  const [err, setErr] = useState<ErrState | null>(null);
  const [busy, setBusy] = useState(false);
  const inFlightRef = useRef(false);
  const reqSeqRef = useRef(0);

  useEffect(() => {
    setSelectedId(null); setWriteInText(''); setWriteInImage(null);
    setErr(null); setBusy(false);
    inFlightRef.current = false; reqSeqRef.current++;
  }, [eventId, turn.turn]);

  const options = useMemo<ApprovalOption[]>(() => {
    const base = turn.approval_options?.length ? turn.approval_options : [
      { id: 'approve', label: 'Approve plan', effect: 'approve' },
      { id: 'reject', label: 'Reject plan', effect: 'reject' }
    ] as ApprovalOption[];
    return [...base, { id: '__write_in__', label: 'Write-in custom instruction', effect: 'steer' }];
  }, [turn.approval_options]);

  const canSubmit = selectedId && (selectedId !== '__write_in__' || writeInText.trim() || writeInImage);

  const handleSubmit = async (expectedSha?: string) => {
    if (!canSubmit || inFlightRef.current) return;
    const seq = ++reqSeqRef.current;
    setBusy(true); setErr(null); inFlightRef.current = true;
    try {
      const payload: DecisionPayload = {
        option_id: selectedId,
        ...(turn.approval_id && { approval_id: turn.approval_id }),
        ...(selectedId === '__write_in__' && { write_in_text: writeInText.trim() }),
        ...(selectedId === '__write_in__' && writeInImage && { image: writeInImage }),
        ...(expectedSha && { expected_sha: expectedSha })
      };
      await submitApprovalDecision(eventId, payload);
      if (seq === reqSeqRef.current) onStatusChange?.();
    } catch (e: unknown) {
      if (seq !== reqSeqRef.current) return;
      const apiErr = e instanceof ApiError ? e : null;
      const body = apiErr?.body as Record<string, unknown> | undefined;
      const status = apiErr?.status ?? 0;
      const detail = apiErr?.detail || (body?.detail as string) || (e instanceof Error ? e.message : String(e));
      if (status === 409 && (body?.code === 'sha_drift' || (!body?.code && body?.live_sha))) {
        setErr({ type: 'drift', detail, liveSha: body?.live_sha as string, reqSha: body?.approval_requested_sha as string });
      } else if (status === 409 && (body?.code === 'closed' || body?.code === 'sha_unresolvable')) {
        setErr({ type: 'blocked', detail });
      } else setErr({ type: 'other', detail });
    } finally {
      if (seq === reqSeqRef.current) { setBusy(false); inFlightRef.current = false; }
    }
  };

  return (
    <fieldset data-pending-approval="true" style={{ marginTop: 12, padding: 12, borderRadius: 6, border: '1px solid #3b82f688', background: '#1e3a8a33' }} disabled={busy}>
      <legend style={{ fontSize: 12, fontWeight: 600, color: '#60a5fa', padding: '0 4px' }}>Approval Required</legend>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {options.map(o => (
          <label key={o.id} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: busy ? 'not-allowed' : 'pointer' }}>
            <input type="radio" name="approval_option" checked={selectedId === o.id} onChange={() => setSelectedId(o.id)} disabled={busy} />
            <span style={{ fontSize: 14, color: '#e2e8f0' }}>{o.label}</span>
          </label>
        ))}
      </div>
      {selectedId === '__write_in__' && <ApprovalWriteInBox text={writeInText} setText={setWriteInText} image={writeInImage} setImage={setWriteInImage} disabled={busy} />}
      <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <button type="button" disabled={!canSubmit} onClick={() => handleSubmit()} style={{ padding: '6px 16px', background: '#3b82f6', color: 'white', border: 'none', borderRadius: 4, cursor: canSubmit ? 'pointer' : 'not-allowed', opacity: canSubmit ? 1 : 0.5 }}>Submit</button>
        {err?.type === 'drift' && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', background: '#78350f', padding: '6px 12px', borderRadius: 4 }}>
            <span style={{ color: '#fde68a', fontSize: 13 }}>HEAD SHA drifted ({err.reqSha?.slice(0,8)} &rarr; {err.liveSha?.slice(0,8)}): {err.detail}</span>
            <button type="button" onClick={() => handleSubmit(err.liveSha)} style={{ padding: '4px 10px', background: '#f59e0b', color: '#451a03', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>Confirm New SHA</button>
          </div>
        )}
        {err?.type === 'blocked' && <div role="alert" style={{ color: '#ef4444', fontSize: 13 }}>Approval blocked: {err.detail}</div>}
        {err?.type === 'other' && (
          <div role="alert" style={{ display: 'flex', gap: 8, alignItems: 'center', background: '#7f1d1d', padding: '6px 12px', borderRadius: 4 }}>
            <span style={{ color: '#fca5a5', fontSize: 13 }}>{err.detail}</span>
            <button aria-label="Dismiss approval error" type="button" onClick={() => setErr(null)} style={{ background: 'transparent', border: 'none', color: '#fca5a5', cursor: 'pointer' }}>×</button>
          </div>
        )}
      </div>
    </fieldset>
  );
}
