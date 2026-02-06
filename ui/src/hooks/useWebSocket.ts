// BlackBoard/ui/src/hooks/useWebSocket.ts
/**
 * WebSocket hook for real-time Brain communication.
 * Connects to ws://host/ws, handles reconnect, dispatches messages.
 */
import { useEffect, useRef, useState, useCallback } from 'react';

export interface WSMessage {
  type: string;
  event_id?: string;
  [key: string]: unknown;
}

type MessageHandler = (msg: WSMessage) => void;

export function useWebSocket(onMessage: MessageHandler) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const retryRef = useRef(0);
  const maxRetries = 10;
  const handlersRef = useRef(onMessage);
  handlersRef.current = onMessage;

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
          handlersRef.current(msg);
        } catch (e) {
          console.error('[WS] Parse error:', e);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        // Reconnect with exponential backoff
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

  return { connected, reconnecting, send };
}
