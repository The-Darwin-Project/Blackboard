// BlackBoard/ui/src/components/workspace/ExtendedThinkingAccordion.tsx
// @ai-rules:
// 1. [Pattern]: Renders nothing when there are no thoughts and no stream; collapsed by default.
// 2. [Constraint]: Thought text is rendered via MarkdownPreview only; never inject it as raw HTML.
/**
 * Collapsible extended thinking/reasoning accordion for agent turns.
 * Displays step counts, streaming indicator, and formatted Markdown reasoning.
 */
import { useState } from 'react';
import { ChevronRight, BrainCircuit } from 'lucide-react';
import MarkdownPreview from '@uiw/react-markdown-preview';

interface ExtendedThinkingAccordionProps {
  thoughts?: string;
  timestamp?: number;
  isStreaming?: boolean;
  defaultExpanded?: boolean;
}

export default function ExtendedThinkingAccordion({
  thoughts = '',
  timestamp,
  isStreaming = false,
  defaultExpanded = false,
}: ExtendedThinkingAccordionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  if (!thoughts && !isStreaming) return null;

  // Extract step count heuristic (numbered items or bullet lines)
  const stepMatches = thoughts.match(/(?:^|\n)\s*(?:\d+\.|\*|-)\s+/g);
  const stepCount = stepMatches ? stepMatches.length : 0;
  const timeLabel = (typeof timestamp === 'number' && Number.isFinite(timestamp))
    ? new Date(timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : null;

  return (
    <div className="border-l-2 border-slate-600/70 pl-3 my-2 text-xs">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-text-muted hover:text-text-secondary transition-colors cursor-pointer group select-none text-left w-full py-0.5"
      >
        <ChevronRight
          size={13}
          className={`text-slate-500 transition-transform duration-200 ${isExpanded ? 'rotate-90' : 'rotate-0'}`}
        />
        <BrainCircuit size={13} className="text-purple-400/80 flex-shrink-0" />
        <span className="font-medium text-purple-300/90">
          {isStreaming ? 'Thinking in progress...' : stepCount > 1 ? `Thinking process (${stepCount} steps)` : 'Thinking process'}
        </span>

        {isStreaming && (
          <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse" />
        )}

        {timeLabel && <span className="text-[10px] text-text-muted font-mono ml-auto">{timeLabel}</span>}
      </button>

      {isExpanded && thoughts && (
        <div className="mt-2 p-2.5 rounded-lg bg-bg-secondary/90 border border-border/80 text-text-secondary overflow-x-auto shadow-inner">
          <MarkdownPreview
            source={thoughts}
            style={{ fontSize: 12, background: 'transparent', color: '#94a3b8' }}
            wrapperElement={{ 'data-color-mode': 'dark' }}
          />
        </div>
      )}
    </div>
  );
}
