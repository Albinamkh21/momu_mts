import React, { useState } from 'react';
import { httpClient } from '../../../../../api/httpClient';

/**
 * Modal / side-panel for creating a new Person record.
 * On success calls onCreated({ id, full_name }).
 */
export function PersonCreateModal({ onCreated, onClose }) {
  const [fullName, setFullName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    const name = fullName.trim();
    if (!name) {
      setError('Введите имя');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const { data } = await httpClient.post('/persons', { full_name: name });
      onCreated(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка при создании автора');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h4>Новый автор / исполнитель</h4>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          <label className="form-label">
            Полное имя <span style={{ color: 'red' }}>*</span>
            <input
              className="form-input"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Иванов Иван Иванович"
              autoFocus
            />
          </label>

          {error && <p style={{ color: 'red', margin: '0.5rem 0' }}>{error}</p>}

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={saving}>
              Отмена
            </button>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? 'Сохранение...' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
