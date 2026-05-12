// BlackBoard/ui/src/components/cortex/CortexHeartbeat.tsx
// @ai-rules:
// 1. [Pattern]: Three visual states -- idle (flat line), spike (EKG), wave (sine). Driven by heartbeatType prop.
// 2. [Constraint]: Use key={tick} to force re-mount and re-trigger CSS animation on each heartbeat.
// 3. [Gotcha]: SVG viewBox is fixed at 200x48; preserveAspectRatio="none" stretches to container width.
// 4. [Pattern]: Animations are CSS-only via inline <style>. No JS requestAnimationFrame.
import type { FC } from 'react';

interface CortexHeartbeatProps {
  heartbeatType: 'spike' | 'wave' | null;
  isWatching: boolean;
  tick: number;
}

const SPIKE_POINTS = '0,24 60,24 75,24 82,6 90,42 97,24 110,24 200,24';
const WAVE_PATH = 'M0,24 C10,14 20,34 30,24 C40,14 50,34 60,24 C70,14 80,34 90,24 C100,14 110,34 120,24 C130,14 140,34 150,24 C160,14 170,34 180,24 C190,14 200,34 210,24 C220,14 230,34 240,24 C250,14 260,34 270,24 C280,14 290,34 300,24';

const KEYFRAMES_STYLE = `
  @keyframes ekg-draw {
    from { stroke-dashoffset: 400; }
    to   { stroke-dashoffset: 0; }
  }
  @keyframes sine-scroll {
    from { transform: translateX(0); opacity: 0.7; }
    60%  { opacity: 0.5; }
    to   { transform: translateX(-150px); opacity: 0; }
  }
`;

let keyframesInjected = false;
function ensureKeyframes() {
  if (keyframesInjected) return;
  const style = document.createElement('style');
  style.textContent = KEYFRAMES_STYLE;
  document.head.appendChild(style);
  keyframesInjected = true;
}

const CortexHeartbeat: FC<CortexHeartbeatProps> = ({ heartbeatType, isWatching, tick }) => {
  if (!isWatching) return null;
  ensureKeyframes();

  return (
    <div className="w-full h-12 bg-slate-900/50 border-b border-border/30 overflow-hidden relative">
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox="0 0 200 48"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        {/* Idle flat line -- always visible as baseline */}
        <polyline
          points="0,24 200,24"
          fill="none"
          stroke="rgb(52, 211, 153)"
          strokeWidth="1"
          opacity={heartbeatType ? 0.1 : 0.2}
        />

        {heartbeatType === 'spike' && (
          <polyline
            key={`spike-${tick}`}
            points={SPIKE_POINTS}
            fill="none"
            stroke="rgb(52, 211, 153)"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="400"
            strokeDashoffset="400"
            style={{ animation: 'ekg-draw 0.8s ease-out forwards' }}
          />
        )}

        {heartbeatType === 'wave' && (
          <path
            key={`wave-${tick}`}
            d={WAVE_PATH}
            fill="none"
            stroke="rgb(52, 211, 153)"
            strokeWidth="1.5"
            strokeLinecap="round"
            style={{ animation: 'sine-scroll 2s ease-out forwards' }}
          />
        )}
      </svg>
    </div>
  );
};

export default CortexHeartbeat;
