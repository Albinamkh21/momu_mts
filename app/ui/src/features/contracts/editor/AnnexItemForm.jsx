import React, { useState } from 'react';
import { addAnnexItem, updateAnnexItem } from '../api/contractAnnex.api';

const buildEmptyForm = (item) => ({
  code: item?.code || '',
  track_title: item?.track_title || '',
  artist_name: item?.artist_name || '',
  related_rights_percent: item?.related_rights_percent ?? '',
  composer_name: item?.composer_name || '',
  composer_percent: item?.composer_percent ?? '',
  lyricist_name: item?.lyricist_name || '',
  lyricist_percent: item?.lyricist_percent ?? '',
});

/**
 * Инлайн-форма добавления/редактирования одной строки (произведения) приложения.
 * Используется внутри ContractAnnexItems — не является отдельной страницей.
 */
export const AnnexItemForm = ({ contractId, annexId, item, onDone, onCancel }) => {
  const [form, setForm] = useState(() => buildEmptyForm(item));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const isEdit = !!item;

  const set = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!form.track_title?.trim() || !form.artist_name?.trim()) {
      setError('Укажите название песни и исполнителя.');
      return;
    }
    setError('');
    setSaving(true);
    try {
      const payload = {
        code: form.code || null,
        track_title: form.track_title,
        artist_name: form.artist_name,
        related_rights_percent: Number(form.related_rights_percent) || 0,
        composer_name: form.composer_name,
        composer_percent: Number(form.composer_percent) || 0,
        lyricist_name: form.lyricist_name,
        lyricist_percent: Number(form.lyricist_percent) || 0,
      };
      const saved = isEdit
        ? await updateAnnexItem(contractId, annexId, item.id, payload)
        : await addAnnexItem(contractId, annexId, payload);
      onDone && onDone(saved);
    } catch (err) {
      setError(err.response?.data?.detail || 'Не удалось сохранить произведение.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="annex-item-form">
      {error && <div className="wizard-error">{error}</div>}

      <div className="form-group">
        <label className="form-label">Код/ISRC</label>
        <input className="form-control" value={form.code} onChange={set('code')} />
      </div>

      <div className="form-group">
        <label className="form-label">Название песни *</label>
        <input className="form-control" value={form.track_title} onChange={set('track_title')} />
      </div>

      <div className="form-group">
        <label className="form-label">Исполнитель *</label>
        <input className="form-control" value={form.artist_name} onChange={set('artist_name')} />
      </div>

      <div className="form-group">
        <label className="form-label">Смежные права, %</label>
        <input
          className="form-control"
          type="number"
          min="0"
          max="100"
          step="0.01"
          value={form.related_rights_percent}
          onChange={set('related_rights_percent')}
        />
      </div>

      <div className="form-group">
        <label className="form-label">Автор музыки</label>
        <input className="form-control" value={form.composer_name} onChange={set('composer_name')} />
      </div>

      <div className="form-group">
        <label className="form-label">% прав на музыку</label>
        <input
          className="form-control"
          type="number"
          min="0"
          max="100"
          step="0.01"
          value={form.composer_percent}
          onChange={set('composer_percent')}
        />
      </div>

      <div className="form-group">
        <label className="form-label">Автор текста</label>
        <input className="form-control" value={form.lyricist_name} onChange={set('lyricist_name')} />
      </div>

      <div className="form-group">
        <label className="form-label">% прав на текст</label>
        <input
          className="form-control"
          type="number"
          min="0"
          max="100"
          step="0.01"
          value={form.lyricist_percent}
          onChange={set('lyricist_percent')}
        />
      </div>

      <div className="form-group" style={{ justifyContent: 'flex-end' }}>
        <button type="button" className="btn" onClick={onCancel}>Отмена</button>
        <button type="button" className="btn-primary" onClick={handleSubmit} disabled={saving}>
          {saving ? 'Сохранение...' : 'Сохранить'}
        </button>
      </div>
    </div>
  );
};
