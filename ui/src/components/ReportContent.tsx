// BlackBoard/ui/src/components/ReportContent.tsx
// @ai-rules:
// 1. [Pattern]: Composes ReportHeader, CollapsibleSection, ReportTurnCard from parsed markdown.
// 2. [Pattern]: data-report-content attribute for @media print CSS targeting.
// 3. [Gotcha]: Report metadata (domain, severity, source) comes from ReportFull fields, NOT parsed from markdown.
// 4. [Pattern]: Mermaid rendered via MarkdownPreview inside CollapsibleSection (Architecture Diagram).
// 5. [Constraint]: Raw markdown is NOT passed here -- ReportToolbar receives it separately from ReportsPage.
import { useMemo } from 'react';
import MarkdownPreview from '@uiw/react-markdown-preview';
import { getCodeString } from 'rehype-rewrite';
import MermaidBlock from './MermaidBlock';
import type { ReportFull } from '../api/types';
import { parseReportMarkdown } from '../utils/parseReport';
import ReportHeader from './ReportHeader';
import ReportTurnCard from './ReportTurnCard';
import CollapsibleSection from './CollapsibleSection';

function SectionMarkdown({ source }: { source: string }) {
  return (
    <MarkdownPreview
      source={source}
      style={{ background: 'transparent', fontSize: 13, lineHeight: 1.6, color: '#e2e8f0' }}
      wrapperElement={{ 'data-color-mode': 'dark' }}
      components={{
        code: ({ children, className, ...props }) => {
          const code = props.node?.children
            ? getCodeString(props.node.children)
            : String(children ?? '');
          if (typeof code === 'string' && typeof className === 'string'
              && /^language-mermaid/.test(className.toLowerCase())) {
            return <MermaidBlock code={code} />;
          }
          return <code className={String(className ?? '')}>{children}</code>;
        },
      }}
    />
  );
}

export default function ReportContent({ report }: { report: ReportFull }) {
  const parsed = useMemo(() => parseReportMarkdown(report.markdown), [report.markdown]);

  return (
    <div data-report-content style={{ flex: 1, overflow: 'auto', padding: 16 }}>
      <ReportHeader report={report} />

      {parsed.sections.map((section) => (
        <CollapsibleSection
          key={section.title}
          title={section.title}
          defaultOpen={section.title === 'Architecture Diagram'}
        >
          <SectionMarkdown source={section.content} />
        </CollapsibleSection>
      ))}

      {parsed.turns.length > 0 && (
        <div style={{ marginTop: 16, marginBottom: 8 }}>
          <div style={{
            fontSize: 14,
            fontWeight: 700,
            color: '#e2e8f0',
            marginBottom: 12,
            paddingBottom: 8,
            borderBottom: '1px solid #1e293b',
          }}>
            Conversation ({parsed.turns.length} turns)
          </div>
          {parsed.turns.map((turn) => (
            <ReportTurnCard key={turn.number} turn={turn} />
          ))}
        </div>
      )}

      {parsed.journal.length > 0 && (
        <CollapsibleSection
          title="Service Ops Journal"
          badge={
            <span style={{ fontSize: 11, color: '#64748b' }}>
              {parsed.journal.length} entries
            </span>
          }
        >
          <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.7 }}>
            {parsed.journal.map((entry, i) => (
              <div key={i} style={{
                padding: '6px 0',
                borderBottom: i < parsed.journal.length - 1 ? '1px solid #1e293b' : 'none',
              }}>
                {entry}
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}
    </div>
  );
}
