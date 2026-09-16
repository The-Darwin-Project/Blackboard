// BlackBoard/ui/src/contexts/WebSocketContext.tsx
// @ai-rules:
// 1. [Pattern]: Single shared WS connection via React context. All consumers use hooks.
// 2. [Pattern]: Reconnect signal fires on onopen when retryRef > 0 (not initial connect).
// 3. [Gotcha]: subscribersRef and reconnectSubscribersRef are Sets -- never recreate, only mutate.
// 4. [Pattern]: connect is useCallback(..., []) with stable empty-deps identity. Auth state/callbacks
//    mirrored into refs (getAccessTokenRef, renewTokenRef, isAuthRenewingRef) to avoid dep churn.
// 5. [Pattern]: 4001 = real auth rejection. Cap at 3 consecutive before triggering logout.
//    consecutiveAuthRejectionsRef reset ONLY on onmessage or 1500ms stable timer, NEVER raw onopen.
// 6. [Pattern]: Non-4001 closes (1006 transport drops) retry indefinitely with exponential backoff
//    capped at 5s. Network disconnects NEVER log out the operator.
// 7. [Pattern]: At retry 6 (~30s), surfaces connectionDegraded + reconnect() for UI banner.
// 8. [Pattern]: 1006 trusted-proxy backstop: 10 consecutive immediate 1006 drops triggers renewToken().
// 9. [Pattern]: 30s heartbeat ping keeps HAProxy from dropping idle connections.
// 10. [Pattern]: isConnectingRef released on socket onopen/onclose, not synchronous finally.
// 11. [Gotcha]: isMountedRef is reset to `true` at the top of the mount effect (not just at
//     declaration) -- otherwise a remount after unmount (StrictMode double-invoke, or any real
//     remount) leaves it `false` forever and every socket callback early-returns permanently.
// 12. [Gotcha]: handleAuthRenewal races renewTokenRef.current() against AUTH_RENEWAL_TIMEOUT_MS --
//     this manual path isn't covered by AuthContext's own 20s safety timeout, so a hung
//     signinSilent() would otherwise leave isRenewingRef stuck `true` and permanently block
//     connect()'s entry guard (including the manual reconnect button).
/**
 * WebSocket context provider -- shares a single WS connection across
 * multiple consumers (ConversationFeed, AgentStreamCards, Dashboard).
 *
 * Usage:
 *   <WebSocketProvider>
 *     <ConversationFeed />
 *     <AgentStreamCard />
 *   </WebSocketProvider>
 *
 * Consumers:
 *   const { connected, reconnecting, connectionDegraded, send, reconnect } = useWSConnection();
 *   useWSMessage((msg) => { ... }); // subscribe to messages
 *   useWSReconnect(() => { ... });  // called once per reconnect (not initial connect)
 */
import { createContext, useContext, useEffect, useRef, useState, useCallback, useMemo, type ReactNode } from 'react';
import type { WSMessage } from '../hooks/useWebSocket';
import { getWSAuthFailureCallback } from '../api/client';
import { useAuth } from './AuthContext';

type MessageHandler = (msg: WSMessage) => void;
type ReconnectHandler = () => void;

interface WSConnectionState {
  connected: boolean;
  reconnecting: boolean;
  connectionDegraded: boolean;
  send: (data: object) => void;
  reconnect: () => void;
}

const WSConnectionContext = createContext<WSConnectionState>({
  connected: false,
  reconnecting: false,
  connectionDegraded: false,
  send: () => {},
  reconnect: () => {},
});

const WSSubscribersContext = createContext<{
  subscribe: (handler: MessageHandler) => () => void;
  subscribeReconnect: (handler: ReconnectHandler) => () => void;
}>({
  subscribe: () => () => {},
  subscribeReconnect: () => () => {},
});

const AUTH_REJECTION_CAP = 3;
const IMMEDIATE_1006_BACKSTOP = 10;
const STABLE_CONNECTION_MS = 1500;
const MAX_BACKOFF_MS = 5000;
const DEGRADED_RETRY_THRESHOLD = 6;
const AUTH_RENEWAL_TIMEOUT_MS = 20_000;

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [connectionDegraded, setConnectionDegraded] = useState(false);
  const retryRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const subscribersRef = useRef<Set<MessageHandler>>(new Set());
  const reconnectSubscribersRef = useRef<Set<ReconnectHandler>>(new Set());
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastMessageTimeRef = useRef<number>(Date.now());

  // Reentrancy guards
  const isConnectingRef = useRef(false);
  const isRenewingRef = useRef(false);

  // Auth rejection tracking (4001)
  const consecutiveAuthRejectionsRef = useRef(0);
  const pendingAuthCheckRef = useRef(false);
  const stableTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Trusted-proxy 1006 backstop
  const consecutive1006DropsRef = useRef(0);
  const isMountedRef = useRef(true);

  // Mirror auth state/callbacks into refs for stable connect identity
  const { getAccessToken, renewToken, isRenewing: isAuthRenewing } = useAuth();
  const getAccessTokenRef = useRef(getAccessToken);
  getAccessTokenRef.current = getAccessToken;
  const renewTokenRef = useRef(renewToken);
  renewTokenRef.current = renewToken;
  const isAuthRenewingRef = useRef(isAuthRenewing);
  isAuthRenewingRef.current = isAuthRenewing;

  // connectRef lets effects call the latest connect without adding it as a dep
  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    // Entry guards: prevent parallel connects and defer during auth renewal
    if (isConnectingRef.current) return;
    if (isRenewingRef.current) return;
    if (isAuthRenewingRef.current) {
      console.log('[WS] Deferring connect -- auth renewal in progress');
      if (!reconnectTimerRef.current) {
        reconnectTimerRef.current = setTimeout(() => connectRef.current(), 1000);
      }
      return;
    }

    isConnectingRef.current = true;
    pendingAuthCheckRef.current = true;

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    let url = `${protocol}//${location.host}/ws`;
    const token = getAccessTokenRef.current();
    if (token) {
      url += `?token=${encodeURIComponent(token)}`;
    }

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current || wsRef.current !== ws) return;
        isConnectingRef.current = false;

        // Clear any pending reconnect timer (prevents double-connect)
        if (reconnectTimerRef.current) {
          clearTimeout(reconnectTimerRef.current);
          reconnectTimerRef.current = null;
        }

        // Fire reconnect signal BEFORE resetting retryRef so consumers
        // can distinguish reconnect from initial connect.
        if (retryRef.current > 0) {
          console.log('[WS] Reconnected -- notifying subscribers');
          reconnectSubscribersRef.current.forEach((handler) => {
            try { handler(); } catch (e) { console.error('[WS] Reconnect handler error:', e); }
          });
        }

        setConnected(true);
        setReconnecting(false);
        setConnectionDegraded(false);
        retryRef.current = 0;
        lastMessageTimeRef.current = Date.now();

        // DO NOT reset consecutiveAuthRejectionsRef here (A-13).
        // An accepted-then-immediately-closed(4001) fires onopen before onclose.
        // Instead, start a 1500ms stable timer to confirm the connection is real.
        pendingAuthCheckRef.current = true;
        if (stableTimerRef.current) clearTimeout(stableTimerRef.current);
        stableTimerRef.current = setTimeout(() => {
          pendingAuthCheckRef.current = false;
          consecutiveAuthRejectionsRef.current = 0;
          consecutive1006DropsRef.current = 0;
        }, STABLE_CONNECTION_MS);

        // Start heartbeat -- detects HAProxy idle drops
        if (heartbeatRef.current) clearInterval(heartbeatRef.current);
        heartbeatRef.current = setInterval(() => {
          if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            console.log('[WS] Heartbeat: not OPEN -- triggering reconnect');
            if (heartbeatRef.current) clearInterval(heartbeatRef.current);
            heartbeatRef.current = null;
            if (wsRef.current) wsRef.current.close();
            return;
          }
          wsRef.current.send(JSON.stringify({ type: 'ping' }));
        }, 30_000);

        console.log('[WS] Connected');
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current || wsRef.current !== ws) return;
        lastMessageTimeRef.current = Date.now();
        // Confirmed healthy traffic -- reset ALL rejection counters
        pendingAuthCheckRef.current = false;
        consecutiveAuthRejectionsRef.current = 0;
        consecutive1006DropsRef.current = 0;
        if (stableTimerRef.current) {
          clearTimeout(stableTimerRef.current);
          stableTimerRef.current = null;
        }
        try {
          const msg = JSON.parse(event.data) as WSMessage;
          subscribersRef.current.forEach((handler) => {
            try {
              handler(msg);
            } catch (e) {
              console.error('[WS] Handler error:', e);
            }
          });
        } catch (e) {
          console.error('[WS] Parse error:', e);
        }
      };

      ws.onclose = (event) => {
        if (!isMountedRef.current || wsRef.current !== ws) return;
        setConnected(false);
        wsRef.current = null;
        isConnectingRef.current = false;

        // Clear stable timer on close
        if (stableTimerRef.current) {
          clearTimeout(stableTimerRef.current);
          stableTimerRef.current = null;
        }
        pendingAuthCheckRef.current = false;

        // Clear heartbeat on close
        if (heartbeatRef.current) {
          clearInterval(heartbeatRef.current);
          heartbeatRef.current = null;
        }

        if (event.code === 4001) {
          // Real auth rejection (server accepted then closed with 4001)
          consecutiveAuthRejectionsRef.current++;
          console.warn(`[WS] Auth rejected (4001) -- consecutive: ${consecutiveAuthRejectionsRef.current}/${AUTH_REJECTION_CAP}`);
          if (consecutiveAuthRejectionsRef.current >= AUTH_REJECTION_CAP) {
            console.warn('[WS] Auth rejection cap reached -- triggering logout');
            getWSAuthFailureCallback()?.();
            return;
          }
          // Retry after backoff (may succeed after token refresh)
          const delay = Math.min(1000 * Math.pow(2, consecutiveAuthRejectionsRef.current), MAX_BACKOFF_MS);
          setReconnecting(true);
          reconnectTimerRef.current = setTimeout(() => connectRef.current(), delay);
          return;
        }

        // Non-4001 closure (transport drop, network blip, etc.)
        // NEVER trigger logout for transport failures.
        retryRef.current++;

        if (event.code === 1006) {
          consecutive1006DropsRef.current++;
          // Trusted-proxy backstop: 10 consecutive immediate 1006 drops
          if (consecutive1006DropsRef.current >= IMMEDIATE_1006_BACKSTOP) {
            console.warn('[WS] 1006 backstop reached -- triggering auth verification via renewToken');
            consecutive1006DropsRef.current = 0;
            handleAuthRenewal();
            return;
          }
        }

        // Surface degraded state at retry 6 (~30s of backoff)
        if (retryRef.current >= DEGRADED_RETRY_THRESHOLD) {
          setConnectionDegraded(true);
        }

        const delay = Math.min(1000 * Math.pow(2, retryRef.current), MAX_BACKOFF_MS);
        setReconnecting(true);
        console.log(`[WS] Reconnecting in ${delay}ms (attempt ${retryRef.current})`);
        reconnectTimerRef.current = setTimeout(() => connectRef.current(), delay);
      };

      ws.onerror = (err) => {
        if (!isMountedRef.current || wsRef.current !== ws) return;
        console.error('[WS] Error:', err);
      };
    } catch (e) {
      isConnectingRef.current = false;
      console.error('[WS] Connect failed:', e);
    }
  }, []);

  connectRef.current = connect;

  const handleAuthRenewal = useCallback(async () => {
    if (isRenewingRef.current) return;
    isRenewingRef.current = true;
    try {
      // Unlike the OIDC-event-driven renewal path (AuthContext's own 20s safety
      // timeout), this manual path has no backstop of its own -- race against a
      // timeout so a hung signinSilent() can't leave isRenewingRef stuck `true`
      // forever, which would permanently block connect()'s entry guard.
      const result = await Promise.race([
        renewTokenRef.current(),
        new Promise<null>((resolve) => setTimeout(() => resolve(null), AUTH_RENEWAL_TIMEOUT_MS)),
      ]);
      // Reset isRenewingRef BEFORE calling connect so connect entry guard is not tripped
      isRenewingRef.current = false;
      if (result) {
        // Token refreshed -- clear backoff timer and reconnect with new token
        if (reconnectTimerRef.current) {
          clearTimeout(reconnectTimerRef.current);
          reconnectTimerRef.current = null;
        }
        connectRef.current();
      } else {
        // Renewal failed -- surface degraded, don't logout
        setConnectionDegraded(true);
        setReconnecting(true);
        if (!reconnectTimerRef.current) {
          const delay = Math.min(1000 * Math.pow(2, retryRef.current), MAX_BACKOFF_MS);
          reconnectTimerRef.current = setTimeout(() => connectRef.current(), delay);
        }
      }
    } finally {
      isRenewingRef.current = false;
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    connect();
    return () => {
      isMountedRef.current = false;
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (stableTimerRef.current) {
        clearTimeout(stableTimerRef.current);
        stableTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onmessage = null;
        wsRef.current.onerror = null;
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  // Reconnect immediately when tab regains focus
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === 'visible' && !wsRef.current) {
        console.log('[WS] Tab visible -- reconnecting');
        retryRef.current = 0;
        consecutive1006DropsRef.current = 0;
        setConnectionDegraded(false);
        if (reconnectTimerRef.current) {
          clearTimeout(reconnectTimerRef.current);
          reconnectTimerRef.current = null;
        }
        connectRef.current();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const reconnect = useCallback(() => {
    // Manual reconnect from UI -- reset counters and connect immediately
    retryRef.current = 0;
    consecutive1006DropsRef.current = 0;
    consecutiveAuthRejectionsRef.current = 0;
    setConnectionDegraded(false);
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    isConnectingRef.current = false;
    connectRef.current();
  }, []);

  const subscribe = useCallback((handler: MessageHandler) => {
    subscribersRef.current.add(handler);
    return () => {
      subscribersRef.current.delete(handler);
    };
  }, []);

  const subscribeReconnect = useCallback((handler: ReconnectHandler) => {
    reconnectSubscribersRef.current.add(handler);
    return () => {
      reconnectSubscribersRef.current.delete(handler);
    };
  }, []);

  const connectionValue = useMemo(
    () => ({ connected, reconnecting, connectionDegraded, send, reconnect }),
    [connected, reconnecting, connectionDegraded, send, reconnect],
  );
  const subscriberValue = useMemo(() => ({ subscribe, subscribeReconnect }), [subscribe, subscribeReconnect]);

  return (
    <WSConnectionContext.Provider value={connectionValue}>
      <WSSubscribersContext.Provider value={subscriberValue}>
        {children}
      </WSSubscribersContext.Provider>
    </WSConnectionContext.Provider>
  );
}

/** Get WS connection state (connected, reconnecting, connectionDegraded, send, reconnect). */
export function useWSConnection() {
  return useContext(WSConnectionContext);
}

/** Subscribe to WS messages. Handler is called for every message. */
export function useWSMessage(handler: MessageHandler) {
  const { subscribe } = useContext(WSSubscribersContext);
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    const stableHandler: MessageHandler = (msg) => handlerRef.current(msg);
    return subscribe(stableHandler);
  }, [subscribe]);
}

/** Subscribe to WS reconnect events. Called once per reconnect (not initial connect). */
export function useWSReconnect(handler: ReconnectHandler) {
  const { subscribeReconnect } = useContext(WSSubscribersContext);
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    const stableHandler: ReconnectHandler = () => handlerRef.current();
    return subscribeReconnect(stableHandler);
  }, [subscribeReconnect]);
}
