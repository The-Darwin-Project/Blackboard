// BlackBoard/ui/src/components/workspace/starterChips.ts
// @ai-rules:
// 1. [Constraint]: Kept out of WorkspaceStarterChips.tsx so that file only exports a component (react-refresh).
// 2. [Pattern]: A chip's prompt text only pre-fills the prompt form; it never auto-submits.
import { GitPullRequest, Wrench, AlertTriangle, Sparkles, type LucideIcon } from 'lucide-react';

export interface StarterChip {
  label: string;
  icon: LucideIcon;
  prompt: string;
}

export const STARTER_CHIPS: StarterChip[] = [
  { label: 'Review PR', icon: GitPullRequest, prompt: 'Review PR' },
  { label: 'Debug Pipeline', icon: Wrench, prompt: 'Debug Pipeline' },
  { label: 'Incident Scan', icon: AlertTriangle, prompt: 'Inspect service latency and logs' },
  { label: 'Swarm Strategy', icon: Sparkles, prompt: 'Plan swarm architecture improvements' },
];
