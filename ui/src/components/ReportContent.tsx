// BlackBoard/ui/src/components/ReportContent.tsx
// @ai-rules:
// 1. [Pattern]: Uses shared MermaidBlock for fenced mermaid code blocks.
// 2. [Pattern]: data-report-content attribute for @media print CSS targeting.
/**
 * Full markdown report viewer.
 * Renders persisted report markdown with Mermaid diagram support.
 */
import MarkdownPreview from '@uiw/react-markdown-preview';
import { getCodeString } from 'rehype-rewrite';
import MermaidBlock from './MermaidBlock';

interface ReportContentProps {
  markdown: string;
}

export default function ReportContent({ markdown }: ReportContentProps) {
  return (
    <div data-report-content style={{ flex: 1, overflow: 'auto', padding: 16 }}>
      <MarkdownPreview
        source={markdown}
        style={{ background: 'transparent', fontSize: 14, lineHeight: 1.7 }}
        wrapperElement={{ 'data-color-mode': 'dark' }}
        components={{
          code: ({ children, className, ...props }) => {
            const code = props.node?.children
              ? getCodeString(props.node.children)
              : (Array.isArray(children) ? String(children[0] ?? '') : String(children ?? ''));
            if (typeof code === 'string' && typeof className === 'string'
                && /^language-mermaid/.test(className.toLowerCase())) {
              return <MermaidBlock code={code} />;
            }
            return <code className={String(className ?? '')}>{children}</code>;
          },
        }}
      />
    </div>
  );
}
