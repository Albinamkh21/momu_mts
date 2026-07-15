import React, { useEffect, useState } from 'react';
import { getReleasesRef, getLabelsRef } from '../api/drafts.api';

/**
 * Step 2 – Release: pick an existing release or fill in a new one.
 */
export function TrackStepRelease({ data, onChange }) {
  const [releases, setReleases] = useState([]);
  const [labels, setLabels] = useState([]);
  const [mode, setMode] = useState(
    data.new_release ? 'new' : data.release_id ? 'existing' : 'none'
  );

  useEffect(() => {
    getReleasesRef().then(setReleases).catch(() => setReleases([]));
    getLabelsRef().then(setLabels).catch(() => setLabels([]));
  }, []);

  const switchMode = (m) => {
    setMode(m);
    if (m === 'none') onChange({});
    if (m === 'existing') onChange({ new_release: undefined });
    if (m === 'new') onChange({ release_id: undefined, new_release: { title: '', upc: '', release_date: '', label_id: null } });
  };

  const setNew = (field, value) =>
    onChange({ ...data, new_release: { ...(data.new_release || {}), [field]: value } });

  return (
    <div className="wizard-step">
      <h3>Шаг 2 — Релиз</h3>

      <div className="radio-group">
        <label>
          <input type="radio" checked={mode === 'none'} onChange={() => switchMode('none')} />
          {' '}Без релиза
        </label>
        <label>
          <input type="radio" checked={mode === 'existing'} onChange={() => switchMode('existing')} />
          {' '}Выбрать существующий
        </label>
        <label>
          <input type="radio" checked={mode === 'new'} onChange={() => switchMode('new')} />
          {' '}Создать новый релиз
        </label>
      </div>

      {mode === 'existing' && (
        <label className="form-label">
          Релиз
          <select
            className="form-input"
            value={data.release_id || ''}
            onChange={(e) =>
              onChange({ release_id: e.target.value ? Number(e.target.value) : null })
            }
          >
            <option value="">— выберите релиз —</option>
            {releases.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title}{r.upc ? ` (${r.upc})` : ''}
              </option>
            ))}
          </select>
        </label>
      )}

      {mode === 'new' && (
        <div className="new-release-form">
          <label className="form-label">
            Название альбома <span style={{ color: 'red' }}>*</span>
            <input
              className="form-input"
              type="text"
              value={data.new_release?.title || ''}
              onChange={(e) => setNew('title', e.target.value)}
              placeholder="Название альбома"
            />
          </label>

          <label className="form-label">
            UPC
            <input
              className="form-input"
              type="text"
              value={data.new_release?.upc || ''}
              onChange={(e) => setNew('upc', e.target.value)}
              placeholder="000000000000"
              maxLength={20}
            />
          </label>

          <label className="form-label">
            Дата релиза
            <input
              className="form-input"
              type="date"
              value={data.new_release?.release_date || ''}
              onChange={(e) => setNew('release_date', e.target.value)}
            />
          </label>

          <label className="form-label">
            Лейбл
            <select
              className="form-input"
              value={data.new_release?.label_id || ''}
              onChange={(e) =>
                setNew('label_id', e.target.value ? Number(e.target.value) : null)
              }
            >
              <option value="">— без лейбла —</option>
              {labels.map((l) => (
                <option key={l.id} value={l.id}>{l.name}</option>
              ))}
            </select>
          </label>
        </div>
      )}
    </div>
  );
}
