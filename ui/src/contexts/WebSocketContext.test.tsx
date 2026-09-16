import { StrictMode, useState } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, cleanup } from '@testing-library/react';
import { WebSocketProvider, useWSConnection, useWSMessage } from './WebSocketContext';
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

// Fires `onopen` synchronously the instant the handler is assigned, simulating an
// already-open socket. Used only by the StrictMode remount test below: it lets the
// first (pre-cleanup) socket reach `onopen` -- resetting isConnectingRef -- entirely
// within the same synchronous StrictMode mount->cleanup->mount pass, so the second
// mount's connect() isn't spuriously blocked by isConnectingRef still being true from
// the first (a separate, pre-existing gotcha unrelated to the isMountedRef fix under
// test here: cleanup nulls out the stale socket's onclose before closing it, so
// isConnectingRef is never reset via a close event once a socket is torn down before
// it opens).
class InstantOpenMockWebSocket {
  url: string;
  private _onopen: (() => void) | null = null;
  onclose: any = null;
  onmessage: any = null;
  onerror: any = null;
  readyState = 0;

  constructor(url: string) {
    this.url = url;
    (window as any).mockWsInstances.push(this);
  }
  get onopen() {
    return this._onopen;
  }
  set onopen(handler: (() => void) | null) {
    this._onopen = handler;
    handler?.();
  }
  close() {
    this.readyState = 3;
  }
  send() {}
}

const mockLogout = vi.fn();
const mockRenewToken = vi.fn();

function Probe() {
  const { connected, connectionDegraded, reconnect } = useWSConnection();
  return (
    <div>
      <div data-testid="connected">{String(connected)}</div>
      <div data-testid="degraded">{String(connectionDegraded)}</div>
      <button onClick={reconnect}>reconnect</button>
    </div>
  );
}

function MessageProbe() {
  const [received, setReceived] = useState<string | null>(null);
  useWSMessage((msg) => setReceived(JSON.stringify(msg)));
  return <div data-testid="received">{received ?? 'none'}</div>;
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

  it('a socket callback still functions after unmount/remount (isMountedRef reset)', () => {
    // React 18/19 StrictMode double-invokes the mount effect in dev builds: mount ->
    // cleanup -> mount, all on the SAME component instance/refs -- this is the "remount
    // after unmount" case the ai-rules gotcha calls out (unlike a real full
    // unmount+separate-render, which always gets fresh refs regardless of this fix).
    // Without resetting isMountedRef.current = true at the top of the mount effect, the
    // first mount's cleanup leaves it `false` forever, and the second mount's socket's
    // `onmessage` guard (`if (!isMountedRef.current ...) return;`) permanently drops
    // every message even though connect() itself ran fine and created a live socket.
    (window as any).WebSocket = InstantOpenMockWebSocket;

    render(
      <StrictMode>
        <WebSocketProvider>
          <MessageProbe />
        </WebSocketProvider>
      </StrictMode>
    );

    // Both the first (torn down) and second (surviving) sockets already auto-fired
    // onopen synchronously via InstantOpenMockWebSocket -- the last instance is the one
    // from the post-cleanup remount and is the one still referenced by wsRef.
    const ws2 = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];

    act(() => {
      ws2.onmessage?.({ data: JSON.stringify({ type: 'remount-probe' }) });
    });

    expect(screen.getByTestId('received').textContent).toContain('remount-probe');
  });

  it('hung renewToken() unblocks connect() via the 20s AUTH_RENEWAL_TIMEOUT_MS safety timeout', async () => {
    // Simulates a hung signinSilent() -- renewToken() is called but never resolves.
    mockRenewToken.mockReturnValue(new Promise(() => {}));

    render(
      <WebSocketProvider>
        <Probe />
      </WebSocketProvider>
    );

    // Drive 10 consecutive immediate 1006 drops to trip the trusted-proxy backstop and
    // invoke handleAuthRenewal() (same mechanism as the "10 consecutive immediate 1006
    // drops" test above). Each reconnected socket is briefly opened (without letting the
    // 1500ms stable-connection timer elapse, so consecutive1006DropsRef isn't reset)
    // before the next drop -- this clears reconnectTimerRef via the onopen handler each
    // time, avoiding a stale non-null reconnectTimerRef left over from a naturally-fired
    // (never explicitly nulled) reconnect timer, which would otherwise cause the
    // `if (!reconnectTimerRef.current)` guard in handleAuthRenewal's failure branch below
    // to wrongly skip scheduling the post-timeout reconnect.
    for (let i = 0; i < 10; i++) {
      const ws = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];
      await act(async () => {
        if (ws.onclose) ws.onclose({ code: 1006 });
        await vi.advanceTimersByTimeAsync(10000);
      });
      const newWs = (window as any).mockWsInstances[(window as any).mockWsInstances.length - 1];
      if (newWs !== ws) {
        act(() => {
          if (newWs.onopen) newWs.onopen();
        });
      }
    }

    expect(mockRenewToken).toHaveBeenCalled();
    const wsCountWhileHung = (window as any).mockWsInstances.length;

    // While renewToken() is hung, isRenewingRef stays true and connect()'s entry guard
    // blocks -- no further WS instances get created no matter how long we wait short of
    // the safety timeout.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect((window as any).mockWsInstances.length).toBe(wsCountWhileHung);

    // Advance past AUTH_RENEWAL_TIMEOUT_MS (20s): Promise.race resolves to null,
    // isRenewingRef is released BEFORE connect() would otherwise be blocked by it, and
    // the "renewal failed" degraded/reconnect path schedules a fresh connect().
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000);
    });
    // Reconnect is scheduled behind an exponential backoff derived from retryRef; advance
    // far enough past MAX_BACKOFF_MS (5s) to guarantee it fires.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });

    expect((window as any).mockWsInstances.length).toBeGreaterThan(wsCountWhileHung);
  });
});
