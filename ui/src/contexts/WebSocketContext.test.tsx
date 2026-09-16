import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, cleanup } from '@testing-library/react';
import { WebSocketProvider, useWSConnection } from './WebSocketContext';
import { useAuth } from './AuthContext';

vi.mock('../api/client', () => ({
  getWSAuthFailureCallback: () => mockLogout,
}));

vi.mock('./AuthContext', () => ({
  useAuth: vi.fn(),
}));

class MockWebSocket {
  url: string;
  onopen: any = null;
  onclose: any = null;
  onmessage: any = null;
  onerror: any = null;
  readyState = 0;
  
  constructor(url: string) {
    this.url = url;
    (window as any).mockWsInstances.push(this);
  }
  close() {
    this.readyState = 3;
  }
  send() {}
}

const mockLogout = vi.fn();
const mockRenewToken = vi.fn();

function Probe() {
  const { connectionDegraded, reconnect } = useWSConnection();
  return (
    <div>
      <div data-testid="degraded">{String(connectionDegraded)}</div>
      <button onClick={reconnect}>reconnect</button>
    </div>
  );
}

describe('WebSocketContext resilience', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    (window as any).mockWsInstances = [];
    (window as any).WebSocket = MockWebSocket;
    
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { access_token: 'valid-token' },
      
      renewToken: mockRenewToken,
      isRenewing: false,
      getAccessToken: () => 'valid-token',
    } as any);
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it('repeated 1006 closes do not trigger logout callback', () => {
    render(
      <WebSocketProvider>
        <Probe />
      </WebSocketProvider>
    );
    
    for (let i = 0; i < 15; i++) {
      const ws = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];
      act(() => {
        if (ws.onclose) ws.onclose({ code: 1006 });
        vi.advanceTimersByTime(10000); // Advance past backoff
      });
    }
    
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it('10 consecutive immediate 1006 drops triggers renewToken, not logout', () => {
    render(
      <WebSocketProvider>
        <Probe />
      </WebSocketProvider>
    );
    
    for (let i = 0; i < 10; i++) {
      const ws = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];
      act(() => {
        if (ws.onclose) ws.onclose({ code: 1006 });
        vi.advanceTimersByTime(10000);
      });
    }
    
    expect(mockRenewToken).toHaveBeenCalled();
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it('3 consecutive 4001 closes triggers logout callback', () => {
    render(
      <WebSocketProvider>
        <Probe />
      </WebSocketProvider>
    );
    
    for (let i = 0; i < 3; i++) {
      const ws = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];
      act(() => {
        if (ws.onclose) ws.onclose({ code: 4001 });
        vi.advanceTimersByTime(10000);
      });
    }
    
    expect(mockLogout).toHaveBeenCalled();
  });

  it('onopen right before 4001 does not reset rejection counter', () => {
    render(
      <WebSocketProvider>
        <Probe />
      </WebSocketProvider>
    );
    
    for (let i = 0; i < 3; i++) {
      const ws = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];
      act(() => {
        if (ws.onopen) ws.onopen();
        if (ws.onclose) ws.onclose({ code: 4001 });
        vi.advanceTimersByTime(10000);
      });
    }
    
    expect(mockLogout).toHaveBeenCalled();
  });

  it('onmessage resets 4001 rejection counter', () => {
    render(
      <WebSocketProvider>
        <Probe />
      </WebSocketProvider>
    );
    
    // Two 4001 closes
    for (let i = 0; i < 2; i++) {
      const ws = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];
      act(() => {
        if (ws.onclose) ws.onclose({ code: 4001 });
        vi.advanceTimersByTime(10000);
      });
    }
    
    // One successful connection with a message
    const ws3 = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];
    act(() => {
      if (ws3.onopen) ws3.onopen();
      if (ws3.onmessage) ws3.onmessage({ data: '{}' });
    });
    
    // Two more 4001 closes
    for (let i = 0; i < 2; i++) {
      const ws = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];
      act(() => {
        if (ws.onclose) ws.onclose({ code: 4001 });
        vi.advanceTimersByTime(10000);
      });
    }
    
    // Total 4 closes, but counter was reset, so no logout
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it('stable connection for 1500ms resets 4001 rejection counter', () => {
    render(
      <WebSocketProvider>
        <Probe />
      </WebSocketProvider>
    );
    
    // Two 4001 closes
    for (let i = 0; i < 2; i++) {
      const ws = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];
      act(() => {
        if (ws.onclose) ws.onclose({ code: 4001 });
        vi.advanceTimersByTime(10000);
      });
    }
    
    // One successful connection stable for 1500ms
    const ws3 = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];
    act(() => {
      if (ws3.onopen) ws3.onopen();
      vi.advanceTimersByTime(1500);
    });
    
    // Two more 4001 closes
    for (let i = 0; i < 2; i++) {
      const ws = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];
      act(() => {
        if (ws.onclose) ws.onclose({ code: 4001 });
        vi.advanceTimersByTime(10000);
      });
    }
    
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it('connectionDegraded becomes true at retry 6 and reconnect clears it', () => {
    render(
      <WebSocketProvider>
        <Probe />
      </WebSocketProvider>
    );
    
    // 6 failures
    for (let i = 0; i < 6; i++) {
      const ws = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];
      act(() => {
        if (ws.onclose) ws.onclose({ code: 1006 });
        vi.advanceTimersByTime(10000);
      });
    }
    
    expect(screen.getByTestId('degraded').textContent).toBe('true');
    
    act(() => {
      screen.getByText('reconnect').click();
    });
    
    // A new WS instance should be created
    const newWs = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];
    act(() => {
      if (newWs.onopen) newWs.onopen();
    });
    
    expect(screen.getByTestId('degraded').textContent).toBe('false');
  });

  it('connect referential stability across AuthContext re-renders', () => {
    const { rerender } = render(
      <WebSocketProvider>
        <Probe />
      </WebSocketProvider>
    );
    
    const initialWsCount = (window as any).mockWsInstances.length;
    
    // Re-render with changed isRenewing state
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { access_token: 'valid-token' },
      
      renewToken: mockRenewToken,
      isRenewing: true, // Changed
    } as any);
    
    rerender(
      <WebSocketProvider>
        <Probe />
      </WebSocketProvider>
    );
    
    // Should not have created a new WS instance due to re-render
    expect((window as any).mockWsInstances.length).toBe(initialWsCount);
  });
});
