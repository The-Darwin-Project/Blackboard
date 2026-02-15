// BlackBoard/ui/src/components/ReportToolbar.tsx
// @ai-rules:
// 1. [Pattern]: Share uses navigator.share() with fallback to clipboard copy + toast.
// 2. [Pattern]: Print uses window.print() -- @media print CSS in index.css handles the rest.
/**
 * Report viewer toolbar with Copy MD, Share, and Print buttons.
 */
import { useState } from 'react';

interface ReportToolbarProps {
  markdown: string;
  eventId: string;
}

export default function ReportToolbar({ markdown, eventId }: ReportToolbarProps) {
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2000);
  };

  const handleCopyMd = () => {
    navigator.clipboard.writeText(markdown).then(
      () => showToast('Markdown copied!'),
      () => showToast('Copy failed'),
    );
  };

  const handleShare = async () => {
    const url = `${window.location.origin}/reports?id=${encodeURIComponent(eventId)}`;
    const title = `Darwin Report: ${eventId}`;
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
        return;
      } catch {
        // User cancelled or share failed -- fall back to clipboard
      }
    }
    navigator.clipboard.writeText(url).then(
      () => showToast('Link copied!'),
      () => showToast('Copy failed'),
    );
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div data-no-print style={{
      padding: '8px 16px', borderTop: '1px solid #334155',
      display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0,
      background: '#0f172a',
    }}>
      <button onClick={handleCopyMd} style={{
        background: '#334155', border: 'none', borderRadius: 6,
        color: '#94a3b8', padding: '6px 14px', cursor: 'pointer', fontSize: 12, fontWeight: 600,
      }}>Copy MD</button>
      <button onClick={handleShare} style={{
        background: '#334155', border: 'none', borderRadius: 6,
        color: '#94a3b8', padding: '6px 14px', cursor: 'pointer', fontSize: 12, fontWeight: 600,
      }}>Share</button>
      <button onClick={handlePrint} style={{
        background: '#334155', border: 'none', borderRadius: 6,
        color: '#94a3b8', padding: '6px 14px', cursor: 'pointer', fontSize: 12, fontWeight: 600,
      }}>Print / PDF</button>

      {/* Toast */}
      {toast && (
        <span style={{
          marginLeft: 8, fontSize: 12, color: '#4ade80',
          animation: 'fadeIn 0.2s ease-in',
        }}>{toast}</span>
      )}
    </div>
  );
}
