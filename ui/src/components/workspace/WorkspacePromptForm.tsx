// BlackBoard/ui/src/components/workspace/WorkspacePromptForm.tsx
/**
 * Prompt input form with submit button for cold-boot Workspace perspective.
 */
import type { FormEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface WorkspacePromptFormProps {
  prompt: string;
  isSubmitting: boolean;
  onChangePrompt: (value: string) => void;
  onSubmitPrompt: (value: string) => void;
}

export default function WorkspacePromptForm({
  prompt,
  isSubmitting,
  onChangePrompt,
  onSubmitPrompt,
}: WorkspacePromptFormProps) {
  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmitPrompt(prompt);
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-lg relative">
      <input
        type="text"
        value={prompt}
        onChange={(e) => onChangePrompt(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            onSubmitPrompt(prompt);
          }
        }}
        placeholder="Instruct the swarm or enter prompt..."
        disabled={isSubmitting}
        className="w-full px-4 py-3 pr-12 rounded-xl bg-bg-secondary border border-border focus:border-accent focus:outline-none text-sm text-text-primary placeholder-text-muted transition-colors shadow-inner"
      />
      <button
        type="submit"
        disabled={!prompt.trim() || isSubmitting}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-accent text-white hover:bg-accent/90 disabled:opacity-30 disabled:hover:bg-accent transition-all"
      >
        {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
      </button>
    </form>
  );
}
