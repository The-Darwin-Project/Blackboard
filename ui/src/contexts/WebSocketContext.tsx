// BlackBoard/ui/src/contexts/WebSocketContext.tsx
// @ai-rules:
// 1. [Pattern]: Single shared WS connection via React context. All consumers use hooks.
// 2. [Pattern]: Reconnect signal fires on onopen when retryRef > 0 (not initial connect).
// 3. [Gotcha]: subscribersRef and reconnectSubscribersRef are Sets -- never recreate, only mutate.
// 4. [Pattern]: onclose code 4001 = auth rejection -- triggers logout via getWSAuthFailureCallback(), skips reconnect.
// 5. [Pattern]: 30s heartbeat ping keeps HAProxy from dropping idle connections. Heartbeat cleared on unmount.
// 6. [Pattern]: Visibility change listener reconnects immediately when tab regains focus.
// 7. [Constraint]: Max backoff is 5s (not 30s) for fast recovery.
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
 *   const { connected, reconnecting, send } = useWSConnection();
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
  send: (data: object) => void;
}

const WSConnectionContext = createContext<WSConnectionState>({
  connected: false,
  reconnecting: false,
  send: () => {},
});

const WSSubscribersContext = createContext<{
  subscribe: (handler: MessageHandler) => () => void;
  subscribeReconnect: (handler: ReconnectHandler) => () => void;
}>({
  subscribe: () => () => {},
  subscribeReconnect: () => () => {},
});

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const retryRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const subscribersRef = useRef<Set<MessageHandler>>(new Set());
  const reconnectSubscribersRef = useRef<Set<ReconnectHandler>>(new Set());
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastMessageTimeRef = useRef<number>(Date.now());
  const { getAccessToken } = useAuth();
  const getAccessTokenRef = useRef(getAccessToken);
  getAccessTokenRef.current = getAccessToken;

  const connect = useCallback(() => {
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
        retryRef.current = 0;
        lastMessageTimeRef.current = Date.now();

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
        lastMessageTimeRef.current = Date.now();
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
        setConnected(false);
        wsRef.current = null;
        if (event.code === 4001) {
          console.warn('[WS] Auth rejected (4001) -- triggering logout');
          getWSAuthFailureCallback()?.();
          return;
        }
        const delay = Math.min(1000 * Math.pow(2, retryRef.current), 5000);
        retryRef.current++;
        setReconnecting(true);
        console.log(`[WS] Reconnecting in ${delay}ms (attempt ${retryRef.current})`);
        reconnectTimerRef.current = setTimeout(connect, delay);
      };

      ws.onerror = (err) => {
        console.error('[WS] Error:', err);
      };
    } catch (e) {
      console.error('[WS] Connect failed:', e);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  // Reconnect immediately when tab regains focus
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === 'visible' && !wsRef.current) {
        console.log('[WS] Tab visible -- reconnecting');
        retryRef.current = 0;
        if (reconnectTimerRef.current) {
          clearTimeout(reconnectTimerRef.current);
          reconnectTimerRef.current = null;
        }
        connect();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, [connect]);

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
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

  const connectionValue = useMemo(() => ({ connected, reconnecting, send }), [connected, reconnecting, send]);
  const subscriberValue = useMemo(() => ({ subscribe, subscribeReconnect }), [subscribe, subscribeReconnect]);

  return (
    <WSConnectionContext.Provider value={connectionValue}>
      <WSSubscribersContext.Provider value={subscriberValue}>
        {children}
      </WSSubscribersContext.Provider>
    </WSConnectionContext.Provider>
  );
}

/** Get WS connection state (connected, reconnecting, send). */
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
