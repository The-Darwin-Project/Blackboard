// BlackBoard/ui/src/components/cortex/CortexPage.test.tsx
// @ai-rules:
// 1. [Pattern]: Regression coverage for the materialize->click dead-click bug (HIGH finding on
//    PR #216). CortexGraph is mocked (real Sigma/canvas rendering isn't testable in jsdom) --
//    the mock exposes a button that invokes the real `onClickNeuron` callback CortexPage passes
//    down, simulating DragHandler's mouseup->onClick wiring for a node id that only exists on
//    the live Sigma graph (i.e. one added by cortex-pulse-handler.ts's materializeNeuron, never
//    present in the REST-fetched `mergedNeurons`).
// 2. [Constraint]: NeuronInfoPanel is left unmocked so a passing test proves the resolved neuron
//    payload actually reaches the panel, not just that some internal state changed.
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { describe, it, expect, afterEach, vi } from 'vitest';
import CortexPage from './CortexPage';
import type { Neuron } from './types';

const mockOnClickNeuron: { current: ((id: string | null, pos?: { x: number; y: number }) => void) | null } = {
  current: null,
};

vi.mock('./CortexGraph', () => ({
  default: (props: { onClickNeuron?: (id: string | null, pos?: { x: number; y: number }) => void }) => {
    mockOnClickNeuron.current = props.onClickNeuron ?? null;
    return null;
  },
}));

vi.mock('./CortexLiveFeed', () => ({ default: () => null }));
vi.mock('./EventDrillDown', () => ({ default: () => null }));
vi.mock('../MarkdownViewer', () => ({ default: () => null }));

vi.mock('../../hooks/useQueue', () => ({
  useActiveEvents: () => ({ data: [] }),
}));

vi.mock('../../hooks/useCortexData', () => ({
  useCortexGraph: () => ({ data: { neurons: [] as Neuron[], total: 0 }, isLoading: false, error: null }),
  useKGServices: () => ({ data: [] }),
  useKGServiceDetail: () => ({ data: undefined }),
  usePulseStream: () => [],
  usePulseGlow: () => ({ isGlowing: () => false, glowTick: 0 }),
  useCortexThinking: () => [],
  useCortexShadow: () => [],
  useCortexWhispers: () => [],
  useCortexStatus: () => null,
  useHeartbeat: () => ({ heartbeatType: null, tick: 0 }),
}));

const getKnowledgeById = vi.fn();
vi.mock('../../api/client', () => ({
  getEventReport: vi.fn(),
  getKnowledgeById: (id: string) => getKnowledgeById(id),
  getLessonById: vi.fn(),
  getMemory: vi.fn(),
}));

afterEach(() => {
  cleanup();
  mockOnClickNeuron.current = null;
  vi.clearAllMocks();
});

describe('CortexPage handleClickNeuron (materialize->click regression)', () => {
  it('resolves and displays a live pulse-materialized node not present in mergedNeurons', async () => {
    getKnowledgeById.mockResolvedValue({
      id: 'fact-pulsed-1',
      payload: { topic: 'Pulsed Fact', fact: 'Materialized outside the cold-start sample', scope: 'global', source: 's', confidence: 0.9, valid_until: null, created_at: 0, updated_at: 0 },
    });

    render(<CortexPage />);
    await waitFor(() => expect(mockOnClickNeuron.current).not.toBeNull());

    // Simulates DragHandler's mouseup->onClick for a node id that only exists on the live Sigma
    // graph (materializeNeuron added it there directly) -- CortexPage's `neurons` state (and
    // therefore mergedNeurons) never contains it, since it never went through useCortexGraph.
    mockOnClickNeuron.current!('knowledge:fact-pulsed-1', { x: 10, y: 10 });

    expect(getKnowledgeById).toHaveBeenCalledWith('fact-pulsed-1');
    await waitFor(() => expect(screen.getAllByText('Pulsed Fact').length).toBeGreaterThan(0));
    expect(screen.getByText('Materialized outside the cold-start sample')).toBeTruthy();
  });

  it('does not resolve for ids outside the knowledge/lesson/memory ring types', async () => {
    render(<CortexPage />);
    await waitFor(() => expect(mockOnClickNeuron.current).not.toBeNull());

    mockOnClickNeuron.current!('tool:select_agent', { x: 10, y: 10 });

    expect(getKnowledgeById).not.toHaveBeenCalled();
    expect(screen.queryByText(/select_agent/)).toBeNull();
  });
});
