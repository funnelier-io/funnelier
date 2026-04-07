"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export interface WSEvent {
  type: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

interface UseWebSocketOptions {
  onEvent?: (event: WSEvent) => void;
  autoReconnect?: boolean;
  reconnectInterval?: number;
}

/**
 * React hook for WebSocket connection to the Funnelier backend.
 * Automatically reconnects on disconnect and provides connection status.
 */
export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { onEvent, autoReconnect = true, reconnectInterval = 5000 } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null);
  const [events, setEvents] = useState<WSEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (typeof window === "undefined") return;

    // Determine WebSocket URL
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setIsConnected(true);
        console.log("[WS] Connected to", wsUrl);
      };

      ws.onmessage = (ev) => {
        if (!mountedRef.current) return;
        try {
          const event: WSEvent = JSON.parse(ev.data);
          setLastEvent(event);
          setEvents((prev) => [...prev.slice(-49), event]); // keep last 50
          onEvent?.(event);
        } catch {
          // Ignore non-JSON messages
        }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setIsConnected(false);
        wsRef.current = null;

        if (autoReconnect) {
          reconnectTimerRef.current = setTimeout(() => {
            if (mountedRef.current) connect();
          }, reconnectInterval);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // WebSocket creation failed
    }
  }, [autoReconnect, reconnectInterval, onEvent]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return {
    isConnected,
    lastEvent,
    events,
    clearEvents,
  };
}

