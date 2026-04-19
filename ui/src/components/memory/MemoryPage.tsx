// BlackBoard/ui/src/components/memory/MemoryPage.tsx
// @ai-rules:
// 1. [Pattern]: Sub-nav with Memories | Lessons | Extract tabs. Extract deferred to Batch 6.
// 2. [Pattern]: URL hash or state-based sub-navigation within the Memory tab.
import { useState } from 'react';
import { Database, BookOpen, Download } from 'lucide-react';
import MemoriesView from './MemoriesView';
import LessonsView from './LessonsView';

type SubView = 'memories' | 'lessons';

const SUB_TABS: { id: SubView; label: string; icon: typeof Database }[] = [
  { id: 'memories', label: 'Memories', icon: Database },
  { id: 'lessons', label: 'Lessons', icon: BookOpen },
];

export default function MemoryPage() {
  const [active, setActive] = useState<SubView>('memories');

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="flex-shrink-0 px-4 pt-3 pb-2 flex items-center justify-between border-b border-border">
        <div className="flex items-center gap-1">
          {SUB_TABS.map(tab => {
            const Icon = tab.icon;
            return (
              <button key={tab.id} onClick={() => setActive(tab.id)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                  active === tab.id
                    ? 'bg-accent/20 text-accent'
                    : 'text-text-muted hover:text-text-secondary hover:bg-bg-tertiary'
                }`}>
                <Icon size={12} />
                {tab.label}
              </button>
            );
          })}
        </div>
        <a href="/lessons-learned-template.md" download
          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded text-xs font-medium text-text-muted hover:text-text-secondary hover:bg-bg-tertiary transition-colors"
          title="Download the Lessons Learned authoring template">
          <Download size={12} /> Template
        </a>
      </div>
      <div className="flex-1 overflow-hidden">
        {active === 'memories' && <MemoriesView />}
        {active === 'lessons' && <LessonsView />}
      </div>
    </div>
  );
}
