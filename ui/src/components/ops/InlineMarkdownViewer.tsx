// BlackBoard/ui/src/components/ops/InlineMarkdownViewer.tsx
// @ai-rules:
// 1. [Pattern]: Lightweight inline markdown renderer for grid content tiles. No drag/resize/maximize.
// 2. [Pattern]: Shares the MarkdownPreview + MermaidBlock rendering core with MarkdownViewer.tsx.
// 3. [Constraint]: Renders inline (no position:fixed). Used inside GridTile content-viewer mode.
import MarkdownPreview from '@uiw/react-markdown-preview';
import { getCodeString } from 'rehype-rewrite';
import MermaidBlock from '../MermaidBlock';

interface InlineMarkdownViewerProps {
  content: string;
}

export default function InlineMarkdownViewer({ content }: InlineMarkdownViewerProps) {
  return (
    <div className="h-full overflow-auto">
      <MarkdownPreview
        source={content}
        style={{ padding: 12, background: 'transparent', fontSize: 15, lineHeight: 1.6 }}
        wrapperElement={{ 'data-color-mode': 'dark' }}
        components={{
          code: ({ children, className, ...props }) => {
            const code = props.node?.children
              ? getCodeString(props.node.children)
              : (Array.isArray(children) ? String(children[0] ?? '') : String(children ?? ''));
            if (typeof code === 'string' && typeof className === 'string' && /^language-mermaid/.test(className.toLowerCase())) {
              return <MermaidBlock code={code} />;
            }
            return <code className={String(className ?? '')}>{children}</code>;
          },
        }}
      />
    </div>
  );
}
