// BlackBoard/ui/src/components/workspace/WorkspaceStarterChips.tsx
/**
 * Starter prompt action chips for cold-boot Workspace perspective.
 */
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

interface WorkspaceStarterChipsProps {
  onSelectPrompt: (prompt: string) => void;
  disabled?: boolean;
}

export default function WorkspaceStarterChips({ onSelectPrompt, disabled }: WorkspaceStarterChipsProps) {
  return (
    <div className="grid grid-cols-2 gap-2.5 w-full max-w-lg mb-6">
      {STARTER_CHIPS.map((chip) => {
        const Icon = chip.icon;
        return (
          <button
            key={chip.label}
            onClick={() => onSelectPrompt(chip.prompt)}
            disabled={disabled}
            className="flex items-center gap-2.5 p-3 rounded-lg bg-bg-secondary border border-border hover:border-accent/40 hover:bg-bg-tertiary text-left transition-all disabled:opacity-50"
          >
            <Icon size={16} className="text-accent flex-shrink-0" />
            <div className="min-w-0">
              <div className="text-xs font-semibold text-text-primary">{chip.label}</div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
