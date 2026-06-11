// BlackBoard/ui/src/components/MermaidBlock.tsx
// @ai-rules:
// 1. [Gotcha]: mermaid.initialize() called once at module scope -- NOT inside useEffect or per-render.
// 2. [Pattern]: Shared by ConversationFeed and ReportContent for fenced mermaid code blocks.
// 3. [Gotcha]: mermaid.render() requires a unique ID per call -- reusing IDs across renders causes
//    lazy-loader errors in Mermaid 11.x that stringify as "imported module: <chunk URL>".
// 4. [Gotcha]: mermaid.render() inserts a temp SVG into the DOM and cleans it up. If the previous
//    render's element still exists, use a monotonic counter to guarantee uniqueness.
import { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({ startOnLoad: false, theme: 'dark' });

let renderCounter = 0;

export default function MermaidBlock({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const container = ref.current;
    const id = `mermaid-${++renderCounter}`;
    let cancelled = false;

    mermaid.render(id, code).then(({ svg }) => {
      if (!cancelled && container) container.innerHTML = svg;
    }).catch(() => {
      if (!cancelled && container) {
        container.innerHTML = `<pre style="color:#94a3b8;font-size:12px;white-space:pre-wrap">${
          code.length > 500 ? code.slice(0, 500) + '\n...' : code
        }</pre>`;
      }
    });

    return () => { cancelled = true; };
  }, [code]);

  return <div ref={ref} style={{ display: 'flex', justifyContent: 'center', padding: '8px 0' }} />;
}
