import React, { useEffect, useState } from 'react';
import { getLabelsRef } from '../api/drafts.api';

/**
 * Step 1 – Track basics: title, ISRC, duration, explicit flag,
 * resource reference, and label (saved in TrackLabel).
 */
export function TrackStepBasic({ data, onChange }) {
  const [labels, setLabels] = useState([]);

  useEffect(() => {
    getLabelsRef().then(setLabels).catch(() => setLabels([]));
  }, []);

  const set = (field, value) => onChange({ ...data, [field]: value });

  return (
    <div className="wizard-step">
      <h3>Шаг 1 — Основная информация</h3>

      <label className="form-label">
        Название трека <span style={{ color: 'red' }}>*</span>
        <input
          className="form-input"
          type="text"
          value={data.title || ''}
          onChange={(e) => set('title', e.target.value)}
          placeholder="Введите название трека"
        />
      </label>

      <label className="form-label">
        ISRC
        <input
          className="form-input"
          type="text"
          value={data.isrc || ''}
          onChange={(e) => set('isrc', e.target.value)}
          placeholder="XX-XXX-00-00000"
          maxLength={20}
        />
      </label>

      <label className="form-label">
        Длительность
        <input
          className="form-input"
          type="text"
          value={data.duration || ''}
          onChange={(e) => set('duration', e.target.value)}
          placeholder="00:03:45"
          maxLength={20}
        />
      </label>

      <label className="form-label checkbox-label">
        <input
          type="checkbox"
          checked={!!data.explicit}
          onChange={(e) => set('explicit', e.target.checked)}
        />
        Explicit (содержит нецензурную лексику)
      </label>

      <label className="form-label">
        Resource Reference
        <input
          className="form-input"
          type="text"
          value={data.resource_reference || ''}
          onChange={(e) => set('resource_reference', e.target.value)}
          placeholder="A1-00000000-0"
        />
      </label>

      <label className="form-label">
        Лейбл
        <select
          className="form-input"
          value={data.label_id || ''}
          onChange={(e) => set('label_id', e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">— без лейбла —</option>
          {labels.map((l) => (
            <option key={l.id} value={l.id}>{l.name}</option>
          ))}
        </select>
      </label>

      <label className="form-label">
        Код лейбла
        <input
          className="form-input"
          type="text"
          value={data.label_own_code || ''}
          onChange={(e) => set('label_own_code', e.target.value)}
          placeholder="Введите код лейбла"
        />
      </label>
    </div>
  );
}
