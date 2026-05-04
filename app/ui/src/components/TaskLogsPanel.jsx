import React from 'react';

export default function TaskLogsPanel({ activeTaskId, logs = [], onClose, height = 200 }) {
  if (!activeTaskId) return null;

  const containerStyle = {
    background: '#1e1e1e',
    color: '#00ff00',
    padding: '15px',
    marginTop: '20px',
    borderRadius: '5px',
    fontFamily: 'monospace'
  };

  const headerStyle = {
    borderBottom: '1px solid #444',
    marginBottom: '10px',
    paddingBottom: '5px',
    color: '#aaa',
    display: 'flex',
    justifyContent: 'space-between'
  };

  const logListStyle = {
    height: `${height}px`,
    overflowY: 'auto'
  };

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <span>Логи операции (ID: {activeTaskId})</span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'red', cursor: 'pointer' }}>Закрыть</button>
      </div>
      <div style={logListStyle}>
        {logs.map((log, i) => (
          <div key={i} style={{ marginBottom: '4px' }}>
            <span style={{ color: '#888' }}>[{new Date(log.timestamp).toLocaleTimeString()}]</span> {log.message}
          </div>
        ))}
      </div>
    </div>
  );
}
