import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import WorkspaceLayout from '../WorkspaceLayout';
import * as OpsStateContext from '../../../contexts/OpsStateContext';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock child components to isolate layout logic
vi.mock('../WorkspaceHeader', () => ({
  default: ({ onToggleSessions, onToggleInspector }: any) => (
    <header data-testid="workspace-header">
      <button data-testid="btn-toggle-sessions" onClick={onToggleSessions}>Toggle Sessions</button>
      <button data-testid="btn-toggle-inspector" onClick={onToggleInspector}>Toggle Inspector</button>
      <a href="/" data-testid="link-to-ops">Ops Center</a>
    </header>
  ),
}));

vi.mock('../WorkspaceSessionsHub', () => ({
  default: ({ isOpen }: { isOpen: boolean }) => (
    isOpen ? <aside data-testid="workspace-sessions-hub">Sessions Hub</aside> : null
  ),
}));

vi.mock('../WorkspaceCenterStage', () => ({
  default: ({ selectedEventId }: { selectedEventId: string | null }) => (
    <main data-testid="workspace-center-stage">Center Stage: {selectedEventId || 'none'}</main>
  ),
}));

vi.mock('../WorkspaceInspector', () => ({
  default: ({ isOpen }: { isOpen: boolean }) => (
    isOpen ? <aside data-testid="workspace-inspector">Inspector Drawer</aside> : null
  ),
}));

describe('WorkspaceLayout (T-2, T-3, T-4, T-14, T-15)', () => {
  let queryClient: QueryClient;
  const mockSelectEvent = vi.fn();
  const mockDeselectEvent = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    vi.spyOn(OpsStateContext, 'useOpsControl').mockReturnValue({
      selectedEventId: 'evt-initial',
      selectEvent: mockSelectEvent,
      deselectEvent: mockDeselectEvent,
      registeredAgents: [],
      ephemeralAgents: [],
      kargoStages: [],
      kargoEventResult: null,
      contentTiles: [],
      hotspotTileId: null,
      setHotspot: vi.fn(),
      openContentTile: vi.fn(),
      closeContentTile: vi.fn(),
      autoHotspot: false,
      toggleAutoHotspot: vi.fn(),
      connected: true,
      send: vi.fn(),
    } as any);

    // Default window innerWidth to 1200 (desktop)
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 1200,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const renderLayout = (initialRoute = '/workspace') => {
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialRoute]}>
          <Routes>
            <Route path="/workspace" element={<WorkspaceLayout />} />
            <Route path="/workspace/:eventId" element={<WorkspaceLayout />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  };

  it('T-2: mounts isolated shell without Layout.tsx or 12 Ops tabs', () => {
    renderLayout('/workspace');

    expect(screen.getByTestId('workspace-header')).toBeInTheDocument();
    expect(screen.getByTestId('workspace-sessions-hub')).toBeInTheDocument();
    expect(screen.getByTestId('workspace-center-stage')).toBeInTheDocument();

    // Verify 12 Ops tabs are NOT present
    expect(screen.queryByText('Streams')).not.toBeInTheDocument();
    expect(screen.queryByText('Topology')).not.toBeInTheDocument();
    expect(screen.queryByText('Guide')).not.toBeInTheDocument();
    expect(screen.queryByText('TimeKeeper')).not.toBeInTheDocument();
  });

  it('T-3: keyboard shortcut (Cmd+B / Ctrl+B) toggles left Sessions panel', () => {
    renderLayout('/workspace');

    expect(screen.getByTestId('workspace-sessions-hub')).toBeInTheDocument();

    // Fire Cmd+B
    fireEvent.keyDown(window, { key: 'b', metaKey: true });
    expect(screen.queryByTestId('workspace-sessions-hub')).not.toBeInTheDocument();

    // Fire Ctrl+B (Windows / Linux)
    fireEvent.keyDown(window, { key: 'b', ctrlKey: true });
    expect(screen.getByTestId('workspace-sessions-hub')).toBeInTheDocument();
  });

  it('T-4: keyboard shortcut (Cmd+J / Ctrl+J) toggles right Inspector panel', () => {
    renderLayout('/workspace');

    expect(screen.getByTestId('workspace-inspector')).toBeInTheDocument();

    // Fire Cmd+J
    fireEvent.keyDown(window, { key: 'j', metaKey: true });
    expect(screen.queryByTestId('workspace-inspector')).not.toBeInTheDocument();

    // Fire Ctrl+J
    fireEvent.keyDown(window, { key: 'j', ctrlKey: true });
    expect(screen.getByTestId('workspace-inspector')).toBeInTheDocument();
  });

  it('T-14: route param :eventId synchronizes with session selection on mount', () => {
    renderLayout('/workspace/evt-param-999');

    // On mounting with /workspace/:eventId, selectEvent should be called with "evt-param-999"
    expect(mockSelectEvent).toHaveBeenCalledWith('evt-param-999');
  });

  it('T-15: responsive resize auto-collapses sidebars on small screens (<1024px)', () => {
    renderLayout('/workspace');

    expect(screen.getByTestId('workspace-sessions-hub')).toBeInTheDocument();
    expect(screen.getByTestId('workspace-inspector')).toBeInTheDocument();

    // Resize window below 1024px
    window.innerWidth = 900;
    fireEvent(window, new Event('resize'));

    // Sidebars should now be collapsed
    expect(screen.queryByTestId('workspace-sessions-hub')).not.toBeInTheDocument();
    expect(screen.queryByTestId('workspace-inspector')).not.toBeInTheDocument();
  });

  it('Escape key triggers deselectEvent when focus is outside text inputs', () => {
    renderLayout('/workspace/evt-param-999');

    // Fire Escape key globally
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(mockDeselectEvent).toHaveBeenCalled();

    mockDeselectEvent.mockClear();

    // Fire Escape key when focused on an input element (should NOT deselect)
    const input = document.createElement('input');
    document.body.appendChild(input);
    input.focus();

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(mockDeselectEvent).not.toHaveBeenCalled();

    document.body.removeChild(input);
  });
});
