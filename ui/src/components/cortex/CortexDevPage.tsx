// BlackBoard/ui/src/components/cortex/CortexDevPage.tsx
// @ai-rules:
// 1. [Constraint]: Dev-only page. Renders EventDrillDown with mock data, no backend needed.
// 2. [Pattern]: Accessible at /cortex-dev route. Not included in production nav.
// 3. [Gotcha]: QueryClientProvider is needed for useQuery inside EventDrillDown (returns empty).
import { useState, type FC } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import EventDrillDown from './EventDrillDown';

import {
  MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES,
  MOCK_THINKING, MOCK_SHADOW, MOCK_WHISPERS, MOCK_CORTEX_STATUS,
} from './mockCortexData';

const devQueryClient = new QueryClient({
  defaultOptions: { queries: { enabled: false } },
});

const CortexDevPage: FC = () => {
  const [heartbeatType, setHeartbeatType] = useState<'spike' | 'wave' | null>(null);
  const [heartbeatTick, setHeartbeatTick] = useState(0);

  const triggerHeartbeat = (type: 'spike' | 'wave') => {
    setHeartbeatType(type);
    setHeartbeatTick(t => t + 1);
    setTimeout(() => setHeartbeatType(null), 3000);
  };

  return (
    <QueryClientProvider client={devQueryClient}>
      <div className="h-screen bg-bg-primary flex flex-col overflow-hidden">
        {/* Controls */}
        <div className="flex-shrink-0 px-4 py-2 bg-bg-secondary border-b border-border flex items-center gap-3">
          <span className="text-xs text-text-muted font-mono">CORTEX DEV MODE</span>
          <button
            onClick={() => triggerHeartbeat('spike')}
            className="px-2 py-1 text-[10px] bg-emerald-500/20 text-emerald-400 rounded hover:bg-emerald-500/30"
          >
            Spike
          </button>
          <button
            onClick={() => triggerHeartbeat('wave')}
            className="px-2 py-1 text-[10px] bg-emerald-500/20 text-emerald-400 rounded hover:bg-emerald-500/30"
          >
            Wave
          </button>
        </div>

        {/* Two-panel layout like the real Cortex page */}
        <div className="flex flex-1 overflow-hidden min-h-0">
          {/* Left: placeholder */}
          <div className="flex-1 flex items-center justify-center text-text-muted text-sm">
            Graph area (mock)
          </div>

          {/* Right: EventDrillDown sidebar */}
          <div className="flex-shrink-0 w-[480px] flex flex-col border-l border-border overflow-hidden">
            <div className="flex-1 min-h-0 overflow-y-auto border-b border-border">
              <EventDrillDown
                eventId={MOCK_EVENT_ID}
                allNeurons={MOCK_NEURONS}
                liveBatches={MOCK_PULSE_BATCHES}
                thinkingEntries={MOCK_THINKING}
                shadowEntries={MOCK_SHADOW}
                whisperEntries={MOCK_WHISPERS}
                cortexStatus={MOCK_CORTEX_STATUS}
                heartbeatType={heartbeatType}
                heartbeatTick={heartbeatTick}
                glowingIds={new Set(['tool:defer_event', 'lesson:mock-001'])}
                onClose={() => {}}
              />
            </div>

            {/* Standalone live feed removed — EventDrillDown has its own JARVIS Stream section */}
          </div>
        </div>
      </div>
    </QueryClientProvider>
  );
};

export default CortexDevPage;
