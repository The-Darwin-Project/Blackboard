// BlackBoard/ui/src/components/GuidePage.tsx
// @ai-rules:
// 1. [Pattern]: Static content page consuming useConfig hook for contactEmail + feedbackFormUrl.
// 2. [Constraint]: No PII collection. Content is purely informational -- AI transparency compliance.
// 3. [Pattern]: 9 sections matching the AI Transparency & Compliance plan.
import { useConfig } from '../hooks/useConfig';

const EXAMPLE_PROMPTS = [
  { prompt: '"Check MR !297 status"', behavior: 'Developer investigates, reports state' },
  { prompt: '"Retest and merge if passes"', behavior: 'Developer retests, Brain monitors, auto-merges' },
  { prompt: '"Scale down get-builds to 1 replica"', behavior: 'SysAdmin modifies Helm values via GitOps' },
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 24 }}>
      <h2 style={{ fontSize: 16, fontWeight: 600, color: '#e2e8f0', marginBottom: 8, borderBottom: '1px solid #334155', paddingBottom: 6 }}>{title}</h2>
      <div style={{ color: '#cbd5e1', fontSize: 14, lineHeight: 1.7 }}>{children}</div>
    </section>
  );
}

export default function GuidePage() {
  const { data: config, isLoading } = useConfig();

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: '24px 16px', overflow: 'auto', height: '100%' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0', marginBottom: 24 }}>Darwin Brain User Guide</h1>

      <Section title="1. Overview">
        <p>Darwin Brain is an autonomous cloud operations system that coordinates AI agents to investigate, plan, and execute infrastructure and code changes. It reduces operational toil, accelerates incident response, and automates merge request lifecycle management.</p>
      </Section>

      <Section title="2. Features">
        <ul style={{ paddingLeft: 20, margin: 0 }}>
          <li><strong>Agent Roster:</strong> Architect (strategy), SysAdmin (execution), Developer (code), QE (verification), Aligner (observation)</li>
          <li><strong>Slack Integration:</strong> Bidirectional event mirroring with approval buttons</li>
          <li><strong>Deep Memory:</strong> Closed events are archived to vector storage for pattern recognition</li>
          <li><strong>Progressive Skills:</strong> Agents load phase-specific capabilities as conversations evolve</li>
        </ul>
      </Section>

      <Section title="3. Limitations">
        <ul style={{ paddingLeft: 20, margin: 0 }}>
          <li>AI responses may contain inaccuracies. The Brain relies on LLM reasoning which can misclassify events, miss context, or produce incorrect recommendations.</li>
          <li>Pipeline and MR status checks depend on API access and may lag real-time state.</li>
          <li>The system cannot perform actions outside its declared tools -- no direct cluster mutations, no arbitrary code execution.</li>
        </ul>
      </Section>

      <Section title="4. Example Prompts">
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #334155' }}>
              <th style={{ textAlign: 'left', padding: '6px 8px', color: '#94a3b8' }}>Prompt</th>
              <th style={{ textAlign: 'left', padding: '6px 8px', color: '#94a3b8' }}>Expected Behavior</th>
            </tr>
          </thead>
          <tbody>
            {EXAMPLE_PROMPTS.map((ex, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #1e293b' }}>
                <td style={{ padding: '6px 8px', fontFamily: 'monospace', color: '#93c5fd' }}>{ex.prompt}</td>
                <td style={{ padding: '6px 8px' }}>{ex.behavior}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="5. Personal Information Notice">
        <p style={{ background: '#7f1d1d20', border: '1px solid #dc262644', borderRadius: 8, padding: 12 }}>
          <strong>Do not enter personal information</strong> (passwords, tokens, PII) into the chat interface. Event conversations are stored in Redis and may be archived to vector storage for operational learning.
        </p>
      </Section>

      <Section title="6. Session Retention">
        <p>Conversation history is retained per event in Redis. Each event has its own conversation. Closed events are archived to deep memory (vector database) for pattern recognition. There is no per-user session -- all interactions are event-scoped.</p>
      </Section>

      <Section title="7. Accuracy Disclaimer">
        <p style={{ background: '#92400e20', border: '1px solid #f59e0b44', borderRadius: 8, padding: 12 }}>
          All AI-generated responses should be reviewed for accuracy and relevance before acting on them. Darwin Brain assists with operational tasks but <strong>does not replace human judgment</strong> for critical decisions.
        </p>
      </Section>

      <Section title="8. Feedback">
        <p>Submit feedback on AI response quality using the <strong>thumbs up/down buttons</strong> on each response in the conversation view.</p>
        {isLoading ? (
          <span style={{ color: '#64748b' }}>Loading...</span>
        ) : config?.feedbackFormUrl ? (
          <p>For detailed feedback or issues, use the <a href={config.feedbackFormUrl} target="_blank" rel="noopener noreferrer" style={{ color: '#3b82f6', textDecoration: 'underline' }}>feedback form</a>.</p>
        ) : null}
      </Section>

      <Section title="9. Contact">
        {isLoading ? (
          <span style={{ color: '#64748b' }}>Loading...</span>
        ) : (
          <p>Questions? Contact <a href={`mailto:${config?.contactEmail || ''}`} style={{ color: '#3b82f6', textDecoration: 'underline' }}>{config?.contactEmail || 'the Darwin team'}</a>.</p>
        )}
      </Section>
    </div>
  );
}
