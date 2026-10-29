import { useEffect, useRef, useState } from 'react';
import type { Violation } from '../lib/types';
import { getAccessToken } from '../lib/auth';
import { listViolations } from '../lib/api';

export type ConnectionStatus = 'connecting' | 'open' | 'closed' | 'error';

const RECONNECT_DELAY_MS = 3000;

export function useViolationStream(onAuthError: () => void) {
  const [violations, setViolations] = useState<Violation[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [loadingInitial, setLoadingInitial] = useState(true);

  const onAuthErrorRef = useRef(onAuthError);
  useEffect(() => {
    onAuthErrorRef.current = onAuthError;
  });

  useEffect(() => {
    let active = true;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;

    async function loadInitial() {
      try {
        const page = await listViolations();
        if (active) {
          setViolations(page.items);
        }
      } catch {
        // 401 обрабатывается глобально; здесь игнорируем прочие ошибки истории.
      } finally {
        if (active) {
          setLoadingInitial(false);
        }
      }
    }

    function connect() {
      if (!active) {
        return;
      }

      const token = getAccessToken();
      if (!token) {
        onAuthErrorRef.current();
        return;
      }

      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const url = `${protocol}://${window.location.host}/api/v1/ws/violations?token=${encodeURIComponent(
        token,
      )}`;

      setStatus('connecting');
      socket = new WebSocket(url);

      socket.onopen = () => {
        if (active) {
          setStatus('open');
        }
      };

      socket.onmessage = (event: MessageEvent) => {
        if (!active) {
          return;
        }
        try {
          const message = JSON.parse(event.data);
          if (message && message.type === 'violation' && message.data) {
            const incoming = message.data as Violation;
            setViolations((prev) => {
              if (prev.some((item) => item.id === incoming.id)) {
                return prev;
              }
              return [incoming, ...prev];
            });
          }
        } catch {
          // Игнорируем некорректные сообщения.
        }
      };

      socket.onerror = () => {
        if (active) {
          setStatus('error');
        }
      };

      socket.onclose = (event: CloseEvent) => {
        if (!active) {
          return;
        }
        if (event.code === 1008) {
          setStatus('closed');
          onAuthErrorRef.current();
          return;
        }
        setStatus('closed');
        reconnectTimer = window.setTimeout(connect, RECONNECT_DELAY_MS);
      };
    }

    loadInitial();
    connect();

    return () => {
      active = false;
      if (reconnectTimer !== undefined) {
        window.clearTimeout(reconnectTimer);
      }
      if (socket) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        socket.close();
      }
    };
  }, []);

  return { violations, setViolations, status, loadingInitial };
}