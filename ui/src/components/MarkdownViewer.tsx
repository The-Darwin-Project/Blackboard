// BlackBoard/ui/src/components/MarkdownViewer.tsx
// @ai-rules:
// 1. [Pattern]: Floating resizable window with drag, resize, and maximize.
// 2. [Pattern]: Uses @uiw/react-markdown-preview with custom MermaidBlock for fenced mermaid blocks.
// 3. [Constraint]: Shared by ConversationFeed (report viewer) and TurnBubble (AttachmentIcon).
import { useState, useRef } from 'react';
import MarkdownPreview from '@uiw/react-markdown-preview';
import { getCodeString } from 'rehype-rewrite';
import MermaidBlock from './MermaidBlock';

export default function MarkdownViewer({
  filename, content, onClose,
}: {
  filename: string; content: string; onClose: () => void;
}) {
  const [maximized, setMaximized] = useState(false);
  const [size, setSize] = useState({ width: 600, height: 450 });
  const [pos, setPos] = useState({ x: 100, y: 60 });
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null);
  const resizeRef = useRef<{ startX: number; startY: number; origW: number; origH: number } | null>(null);

  const onDragStart = (e: React.MouseEvent) => {
    if (maximized) return;
    dragRef.current = { startX: e.clientX, startY: e.clientY, origX: pos.x, origY: pos.y };
    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      setPos({ x: dragRef.current.origX + (ev.clientX - dragRef.current.startX), y: dragRef.current.origY + (ev.clientY - dragRef.current.startY) });
    };
    const onUp = () => { dragRef.current = null; document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };

  const onResizeStart = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (maximized) return;
    resizeRef.current = { startX: e.clientX, startY: e.clientY, origW: size.width, origH: size.height };
    const onMove = (ev: MouseEvent) => {
      if (!resizeRef.current) return;
      setSize({ width: Math.max(300, resizeRef.current.origW + (ev.clientX - resizeRef.current.startX)), height: Math.max(200, resizeRef.current.origH + (ev.clientY - resizeRef.current.startY)) });
    };
    const onUp = () => { resizeRef.current = null; document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };

  const windowStyle: React.CSSProperties = maximized
    ? { position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', zIndex: 1000 }
    : { position: 'fixed', top: pos.y, left: pos.x, width: size.width, height: size.height, zIndex: 1000 };

  return (
    <>
      <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', zIndex: 999 }} onClick={onClose} />
      <div style={{ ...windowStyle, background: '#0f172a', border: '1px solid #334155', borderRadius: maximized ? 0 : 8, display: 'flex', flexDirection: 'column', boxShadow: '0 20px 60px rgba(0,0,0,0.5)' }}>
        <div onMouseDown={onDragStart} style={{ padding: '8px 12px', background: '#1e293b', borderBottom: '1px solid #334155', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: maximized ? 'default' : 'move', borderRadius: maximized ? 0 : '8px 8px 0 0', flexShrink: 0, userSelect: 'none' }}>
          <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 600 }}>{filename}</span>
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={() => setMaximized(!maximized)} style={{ background: '#334155', border: 'none', borderRadius: 4, color: '#94a3b8', width: 24, height: 24, cursor: 'pointer', fontSize: 12 }} title={maximized ? 'Restore' : 'Maximize'}>{maximized ? '◱' : '◳'}</button>
            <button onClick={onClose} style={{ background: '#dc2626', border: 'none', borderRadius: 4, color: '#fff', width: 24, height: 24, cursor: 'pointer', fontSize: 12, fontWeight: 700 }} title="Close">x</button>
          </div>
        </div>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <MarkdownPreview source={content} style={{ padding: 16, background: 'transparent', fontSize: 13, lineHeight: 1.6 }} wrapperElement={{ 'data-color-mode': 'dark' }} components={{
            code: ({ children, className, ...props }) => {
              const code = props.node?.children ? getCodeString(props.node.children) : (Array.isArray(children) ? String(children[0] ?? '') : String(children ?? ''));
              if (typeof code === 'string' && typeof className === 'string' && /^language-mermaid/.test(className.toLowerCase())) return <MermaidBlock code={code} />;
              return <code className={String(className ?? '')}>{children}</code>;
            },
          }} />
        </div>
        {!maximized && (
          <div onMouseDown={onResizeStart} style={{ position: 'absolute', bottom: 0, right: 0, width: 16, height: 16, cursor: 'nwse-resize', opacity: 0.5 }}>
            <svg width="16" height="16" viewBox="0 0 16 16"><path d="M14 14L8 14L14 8Z" fill="#64748b" /></svg>
          </div>
        )}
      </div>
    </>
  );
}
