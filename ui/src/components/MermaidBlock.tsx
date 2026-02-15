// BlackBoard/ui/src/components/MermaidBlock.tsx
// @ai-rules:
// 1. [Gotcha]: mermaid.initialize() called once at module scope -- NOT inside useEffect or per-render.
// 2. [Pattern]: Shared by ConversationFeed and ReportContent for fenced mermaid code blocks.
/**
 * Renders a single Mermaid diagram inside MarkdownPreview.
 * Extracted from ConversationFeed for reuse across report views.
 */
import { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({ startOnLoad: false, theme: 'dark' });

export default function MermaidBlock({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const idRef = useRef(`mermaid-${Math.random().toString(36).slice(2, 8)}`);

  useEffect(() => {
    if (ref.current) {
      mermaid.render(idRef.current, code).then(({ svg }) => {
        if (ref.current) ref.current.innerHTML = svg;
      }).catch((err) => {
        if (ref.current) ref.current.textContent = String(err);
      });
    }
  }, [code]);

  return <div ref={ref} style={{ display: 'flex', justifyContent: 'center', padding: '8px 0' }} />;
}
