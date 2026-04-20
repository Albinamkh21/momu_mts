import React from 'react';

export const PersonsRenderer = (props) => {
  const items = props.value || [];
  return (
    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
      {items.map(p => (
        <span 
          key={`${p.id}-${p.role}`}
          style={{ color: '#1890ff', cursor: 'pointer', fontWeight: 500 }}
          onClick={() => props.onPersonClick(p)}
        >
          {p.name}{p.role ? ` (${p.role})` : ''}
        </span>
      ))}
    </div>
  );
};