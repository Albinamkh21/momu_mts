import React, { useState } from 'react';
import { httpClient } from '../../../../../api/httpClient';

/**
 * Modal for creating a new RightHolder record.
 * On success calls onCreated({ id, name, effective_date, termination_date }).
 */
export function RightHolderCreateModal({ onCreated, onClose }) {
  const [name, setName] = useState('');
  const [effectiveDate, setEffectiveDate] = useState('');
  const [terminationDate, setTerminationDate] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Введите название правообладателя');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const { data } = await httpClient.post('/right-holders', {
        name: trimmedName,
        effective_date: effectiveDate || null,
        termination_date: terminationDate || null,
      });
      onCreated(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка при создании правообладателя');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h4>Новый правообладатель</h4>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          <label className="form-label">
            Название <span style={{ color: 'red' }}>*</span>
            <input
              className="form-input"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Название правообладателя"
              autoFocus
            />
          </label>
          <label className="form-label">
            Дата начала
            <input
              className="form-input"
              type="date"
              value={effectiveDate}
              onChange={(e) => setEffectiveDate(e.target.value)}
            />
          </label>
          <label className="form-label">
            Дата окончания
            <input
              className="form-input"
              type="date"
              value={terminationDate}
              onChange={(e) => setTerminationDate(e.target.value)}
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
