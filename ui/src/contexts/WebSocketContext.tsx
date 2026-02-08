// BlackBoard/ui/src/contexts/WebSocketContext.tsx
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
 */
import { createContext, useContext, useEffect, useRef, useState, useCallback, type ReactNode } from 'react';
import type { WSMessage } from '../hooks/useWebSocket';

type MessageHandler = (msg: WSMessage) => void;

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
}>({
  subscribe: () => () => {},
});

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const retryRef = useRef(0);
  const maxRetries = 10;
  const subscribersRef = useRef<Set<MessageHandler>>(new Set());

  const connect = useCallback(() => {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${location.host}/ws`;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setReconnecting(false);
        retryRef.current = 0;
        console.log('[WS] Connected');
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as WSMessage;
          // Fan out to all subscribers
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

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (retryRef.current < maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, retryRef.current), 30000);
          retryRef.current++;
          setReconnecting(true);
          console.log(`[WS] Reconnecting in ${delay}ms (attempt ${retryRef.current})`);
          setTimeout(connect, delay);
        }
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
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
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

  return (
    <WSConnectionContext.Provider value={{ connected, reconnecting, send }}>
      <WSSubscribersContext.Provider value={{ subscribe }}>
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
