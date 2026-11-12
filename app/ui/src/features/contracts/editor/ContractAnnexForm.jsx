import React, { useEffect, useState } from 'react';
import {
  createContractAnnex,
  getContractAnnexDetail,
  updateContractAnnex,
} from '../api/contractAnnex.api';
import { ANNEX_STATUS_OPTIONS } from '../components/contractAnnexFilterFields';

const EMPTY_FORM = {
  annex_number: '',
  doc_date: '',
  status: 'DRAFT',
};

const emptyItemRow = () => ({
  _key: Math.random().toString(36).slice(2),
  code: '',
  track_title: '',
  artist_name: '',
  related_rights_percent: '',
  composer_name: '',
  composer_percent: '',
  lyricist_name: '',
  lyricist_percent: '',
});

/**
 * Форма шапки приложения (ContractAnnex): номер, дата, статус.
 * В режиме создания дополнительно собирает начальный список произведений —
 * бэкенд требует хотя бы одну строку при создании приложения (`items` не
 * может быть пустым). Дальнейшее редактирование строк (добавление/правка/
 * удаление) выполняется уже через ContractAnnexItems после создания.
 *
 * mode: 'create' | 'view' | 'edit'
 */
export const ContractAnnexForm = ({
  contractId,
  annexId,
  mode = 'edit',
  onDone,
  onCancel,
  onSwitchToEdit,
}) => {
  const [form, setForm] = useState(EMPTY_FORM);
  const [items, setItems] = useState([emptyItemRow()]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const readOnly = mode === 'view';
  const isCreate = mode === 'create';

  const handleSwitchToEdit = (e) => {
    e?.preventDefault();
    if (onSwitchToEdit) onSwitchToEdit();
  };

  useEffect(() => {
    if (!annexId) {
      setForm(EMPTY_FORM);
      setItems([emptyItemRow()]);
      return;
    }
    setLoading(true);
    getContractAnnexDetail(contractId, annexId)
      .then((data) => {
        setForm({
          annex_number: data.annex_number || '',
          doc_date: data.doc_date || '',
          status: data.status || 'DRAFT',
        });
      })
      .catch(() => setError('Не удалось загрузить данные приложения.'))
      .finally(() => setLoading(false));
  }, [contractId, annexId]);

  const set = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const addItemRow = () => setItems((prev) => [...prev, emptyItemRow()]);
  const removeItemRow = (idx) => setItems((prev) => prev.filter((_, i) => i !== idx));
  const setItemField = (idx, field, value) =>
    setItems((prev) => prev.map((row, i) => (i === idx ? { ...row, [field]: value } : row)));

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!form.annex_number?.trim()) {
      setError('Укажите номер приложения.');
      return;
    }
    if (!form.doc_date) {
      setError('Укажите дату документа.');
      return;
    }
    if (isCreate && items.length === 0) {
      setError('Добавьте хотя бы одно произведение.');
      return;
    }

    setError('');
    setSaving(true);
    try {
      if (isCreate) {
        const payload = {
          annex_number: form.annex_number,
          doc_date: form.doc_date,
          status: form.status,
          items: items.map((row, idx) => ({
            line_number: idx + 1,
            code: row.code || null,
            track_title: row.track_title,
            artist_name: row.artist_name,
            related_rights_percent: Number(row.related_rights_percent) || 0,
            composer_name: row.composer_name,
            composer_percent: Number(row.composer_percent) || 0,
            lyricist_name: row.lyricist_name,
            lyricist_percent: Number(row.lyricist_percent) || 0,
          })),
        };
        const created = await createContractAnnex(contractId, payload);
        onDone && onDone(created);
      } else {
        const updated = await updateContractAnnex(contractId, annexId, { ...form });
        onDone && onDone(updated);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Не удалось сохранить приложение.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="loading-text">Загрузка...</div>;

  return (
    <div className="contract-annex-form">
      {error && <div className="wizard-error">{error}</div>}

      <div className="form-group">
        <label className="form-label">Номер приложения *</label>
        <input
          className="form-control"
          value={form.annex_number || ''}
          onChange={set('annex_number')}
          disabled={readOnly}
        />
      </div>

      <div className="form-group">
        <label className="form-label">Дата документа *</label>
        <input
          type="date"
          className="form-control"
          value={form.doc_date || ''}
          onChange={set('doc_date')}
          disabled={readOnly}
        />
      </div>

      <div className="form-group">
        <label className="form-label">Статус</label>
        <select className="form-control" value={form.status || ''} onChange={set('status')} disabled={readOnly}>
          {ANNEX_STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {isCreate && (
        <div className="annex-items-editor">
          <label className="form-label">Произведения *</label>
          <table className="rights-table">
            <thead>
              <tr>
                <th>Код/ISRC</th>
                <th>Название</th>
                <th>Исполнитель</th>
                <th>Смежные %</th>
                <th>Композитор</th>
                <th>% муз.</th>
                <th>Автор текста</th>
                <th>% текста</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((row, idx) => (
                <tr key={row._key}>
                  <td><input className="form-input" style={{ width: '90px' }} value={row.code} onChange={(e) => setItemField(idx, 'code', e.target.value)} /></td>
                  <td><input className="form-input" value={row.track_title} onChange={(e) => setItemField(idx, 'track_title', e.target.value)} /></td>
                  <td><input className="form-input" value={row.artist_name} onChange={(e) => setItemField(idx, 'artist_name', e.target.value)} /></td>
                  <td><input className="form-input" type="number" min="0" max="100" step="0.01" style={{ width: '70px' }} value={row.related_rights_percent} onChange={(e) => setItemField(idx, 'related_rights_percent', e.target.value)} /></td>
                  <td><input className="form-input" value={row.composer_name} onChange={(e) => setItemField(idx, 'composer_name', e.target.value)} /></td>
                  <td><input className="form-input" type="number" min="0" max="100" step="0.01" style={{ width: '70px' }} value={row.composer_percent} onChange={(e) => setItemField(idx, 'composer_percent', e.target.value)} /></td>
                  <td><input className="form-input" value={row.lyricist_name} onChange={(e) => setItemField(idx, 'lyricist_name', e.target.value)} /></td>
                  <td><input className="form-input" type="number" min="0" max="100" step="0.01" style={{ width: '70px' }} value={row.lyricist_percent} onChange={(e) => setItemField(idx, 'lyricist_percent', e.target.value)} /></td>
                  <td>
                    <button type="button" className="btn-sm btn-danger" onClick={() => removeItemRow(idx)} disabled={items.length <= 1}>✕</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button type="button" className="btn-add" onClick={addItemRow}>+ Добавить произведение</button>
        </div>
      )}

      <div className="form-group" style={{ justifyContent: 'flex-end' }}>
        {readOnly ? (
          <>
            <button type="button" className="btn" onClick={onCancel}>Закрыть</button>
            <button type="button" className="btn-primary" onClick={handleSwitchToEdit}>✎ Редактировать</button>
          </>
        ) : (
          <>
            <button type="button" className="btn" onClick={onCancel}>Отмена</button>
            <button type="button" className="btn-primary" onClick={handleSubmit} disabled={saving}>
              {saving ? 'Сохранение...' : 'Сохранить'}
            </button>
          </>
        )}
      </div>
    </div>
  );
};
