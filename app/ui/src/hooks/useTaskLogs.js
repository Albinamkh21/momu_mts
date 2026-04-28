import { useState, useEffect, useRef } from 'react';

export const useTaskLogs = (taskId) => {
  const [logs, setLogs] = useState([]);
  const socketRef = useRef(null);

  useEffect(() => {
    if (!taskId) return;

    // Используем текущий хост и порт (тот же, что у страницы – 5173 в dev, либо домен в проде)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/task/${taskId}`;

    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      console.log('WebSocket connected for task', taskId);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLogs((prev) => [...prev, data]);
      } catch (err) {
        console.error('Failed to parse WebSocket message', err);
      }
    };

    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    socket.onclose = () => {
      console.log('WebSocket closed for task', taskId);
    };

    return () => {
      if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
        socketRef.current.close();
      }
    };
  }, [taskId]);

  return { logs, setLogs };
};