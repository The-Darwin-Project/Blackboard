// BlackBoard/ui/src/components/CiContextCard.tsx
// @ai-rules:
// 1. [Pattern]: 4-tier progressive disclosure for CI event context.
// 2. [Constraint]: All CiContext fields are optional — guard every access.
// 3. [Pattern]: console_tail rendered via stripJenkinsNoise(stripAnsi(text)). LLM triage correlated by job_name.
// 4. [Gotcha]: jenkins_url may be falsy — hide links when absent.
// 5. [Pattern]: Tiers 3/4 (Missing Jobs, LLM Triage) use the shared CollapsibleSection component for their expand/collapse chrome -- do not hand-roll another chevron+useState toggle here.
import { useState } from 'react';
import type { CiContext } from '../api/types';
import { stripAnsi, stripJenkinsNoise } from '../utils/stripAnsi';
import { safeOpen } from '../utils/safeOpen';
import CollapsibleSection from './CollapsibleSection';

function ConsoleTailBlock({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const cleaned = stripJenkinsNoise(stripAnsi(text));
  const lines = cleaned.split('\n');
  const preview = lines.slice(-8).join('\n');

  return (
    <div className="mt-1">
      <pre
        className="text-[11px] font-mono whitespace-pre-wrap break-all rounded p-2"
        style={{ background: '#0c0c0c', color: '#d4d4d4', maxHeight: expanded ? 'none' : 120, overflow: 'hidden' }}
      >
        {expanded ? cleaned : preview}
      </pre>
      {lines.length > 8 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[10px] text-blue-400 hover:underline mt-0.5"
        >
          {expanded ? 'Collapse' : `Show all ${lines.length} lines`}
        </button>
      )}
    </div>
  );
}

function FailedJobRow({ job, triage, jenkinsUrl }: {
  job: NonNullable<CiContext['failed_jobs']>[number];
  triage?: NonNullable<CiContext['llm_triage']>[number];
  jenkinsUrl?: string;
}) {
  const link = job.jenkins_link || (jenkinsUrl && job.job_name
    ? `${jenkinsUrl.replace(/\/$/, '')}/job/${encodeURIComponent(job.job_name)}/${job.build_number ?? ''}`
    : null);

  return (
    <div className="border border-border rounded p-2 space-y-1" style={{ background: '#1a0505' }}>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[12px] font-semibold text-red-400">{job.job_name ?? 'unknown job'}</span>
        {job.build_number != null && (
          <span className="text-[11px] text-text-muted font-mono">#{job.build_number}</span>
        )}
        {job.result && (
          <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-red-500/15 text-red-400">{job.result}</span>
        )}
        {link && (
          <button onClick={() => safeOpen(link)}
            className="text-[10px] text-blue-400 hover:underline ml-auto bg-transparent border-none cursor-pointer p-0">Jenkins &rarr;</button>
        )}
      </div>
      {triage?.recommended_action && (
        <div className="text-[11px] text-amber-300 bg-amber-500/10 rounded px-2 py-1">
          <span className="font-medium">Recommended: </span>{triage.recommended_action}
          {triage.classification && (
            <span className="text-text-muted ml-2">({triage.classification}{triage.confidence != null ? ` ${Math.round(triage.confidence * 100)}%` : ''})</span>
          )}
        </div>
      )}
      {job.console_tail && <ConsoleTailBlock text={job.console_tail} />}
    </div>
  );
}

interface CiContextCardProps {
  context: CiContext;
}

export default function CiContextCard({ context }: CiContextCardProps) {
  const failedCount = context.failed_jobs?.length ?? 0;
  const missingCount = context.missing_jobs?.length ?? 0;
  const triageMap = new Map(
    (context.llm_triage ?? []).filter(t => t.job_name).map(t => [t.job_name!, t]),
  );

  return (
    <div className="space-y-2">
      {/* Tier 1: summary badges */}
      <div className="flex items-center gap-2 flex-wrap text-[12px]">
        {context.cnv_version && (
          <span className="px-2 py-0.5 rounded bg-blue-500/15 text-blue-300 font-mono">{context.cnv_version}</span>
        )}
        {failedCount > 0
          ? <span className="px-2 py-0.5 rounded bg-red-500/15 text-red-400 font-medium">{failedCount} failed</span>
          : context.failed_jobs != null
            ? <span className="px-2 py-0.5 rounded bg-green-500/15 text-green-400 font-medium">All passing</span>
            : null
        }
        {missingCount > 0 && (
          <span className="px-2 py-0.5 rounded bg-yellow-500/15 text-yellow-400 font-medium">{missingCount} missing</span>
        )}
        {context.jenkins_url && (
          <button onClick={() => safeOpen(context.jenkins_url)}
            className="text-[11px] text-blue-400 hover:underline ml-auto bg-transparent border-none cursor-pointer p-0">Jenkins Dashboard &rarr;</button>
        )}
      </div>

      {/* Tier 2: failed jobs (default open) */}
      {failedCount > 0 && (
        <div className="space-y-1.5">
          {context.failed_jobs!.map((job, i) => (
            <FailedJobRow key={job.job_name ?? i} job={job} triage={job.job_name ? triageMap.get(job.job_name) : undefined} jenkinsUrl={context.jenkins_url} />
          ))}
        </div>
      )}

      {/* Tier 3: missing jobs (collapsed) */}
      {missingCount > 0 && (
        <CollapsibleSection title={`Missing Jobs (${missingCount})`}>
          <div className="space-y-1 text-[11px]">
            {context.missing_jobs!.map((job, i) => (
              <div key={job.job_name ?? i} className="flex items-center gap-2 text-text-muted">
                <span className="text-yellow-400">{job.job_name ?? 'unknown'}</span>
                {job.last_build_number != null && <span className="font-mono">last: #{job.last_build_number}</span>}
                {job.last_result && <span className="text-text-muted">({job.last_result})</span>}
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Tier 4: LLM triage detail (collapsed) */}
      {(context.llm_triage?.length ?? 0) > 0 && (
        <CollapsibleSection title={`LLM Triage (${context.llm_triage!.length})`}>
          <div className="space-y-1 text-[11px]">
            {context.llm_triage!.map((t, i) => (
              <div key={t.job_name ?? i} className="flex items-center gap-2 flex-wrap">
                <span className="text-text-secondary font-medium">{t.job_name ?? 'unknown'}</span>
                {t.classification && <span className="px-1.5 py-0.5 rounded bg-bg-tertiary text-text-muted">{t.classification}</span>}
                {t.confidence != null && <span className="text-text-muted">{Math.round(t.confidence * 100)}%</span>}
                {t.recommended_action && <span className="text-amber-300 truncate max-w-[200px]" title={t.recommended_action}>{t.recommended_action}</span>}
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}
    </div>
  );
}
