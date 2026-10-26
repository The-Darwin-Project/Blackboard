// BlackBoard/ui/src/components/Header.tsx
/**
 * Header for Operations Center layout.
 * Includes logo, operational navigation tabs, and perspective switcher to Agent Workspace.
 */
import { useNavigate } from 'react-router-dom';
import { Zap } from 'lucide-react';

interface HeaderProps {
  tabs: Array<{ id: string; label: string }>;
  activeTab: string;
  onSelectTab: (id: string) => void;
}

export default function Header({ tabs, activeTab, onSelectTab }: HeaderProps) {
  const navigate = useNavigate();

  return (
    <header className="flex-shrink-0 bg-bg-secondary border-b border-border px-4 py-1.5 flex items-center gap-4">
      <div className="flex items-center gap-2.5 cursor-pointer" onClick={() => navigate('/')}>
        <img src="/darwin.svg" alt="Darwin" className="w-7 h-7 rounded-lg shadow-sm" />
        <span className="text-sm font-semibold text-text-primary hidden lg:block tracking-tight">Darwin</span>
      </div>

      <nav className="flex items-center gap-0.5 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onSelectTab(tab.id)}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-colors whitespace-nowrap ${
              activeTab === tab.id
                ? 'bg-accent/20 text-accent'
                : 'text-text-muted hover:text-text-secondary hover:bg-bg-tertiary'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="ml-auto flex items-center gap-2">
        <button
          onClick={() => navigate('/workspace')}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-accent/15 border border-accent/30 hover:bg-accent/25 text-accent text-xs font-medium transition-colors"
          title="Switch to Agent Workspace (Pair Programming Mode)"
        >
          <Zap size={13} className="text-accent" />
          <span>Agent Workspace</span>
        </button>
      </div>
    </header>
  );
}
