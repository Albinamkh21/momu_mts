import React, { useState, useEffect } from 'react';
import {
  getRightHolderDetail,
  createRightHolder,
  updateRightHolder,
  getLabels,
} from '../api/rightHolders.api';
import { RIGHT_HOLDER_TYPE_OPTIONS } from '../components/rightHolderFilterFields';

const EMPTY_FORM = {
  type: 'INDIVIDUAL',
  alias: '',
  label_id: '',
  email: '',
  phone: '',
  address: '',
  full_name: '',
  company_name: '',
  iin_bin: '',
  id_document_type: '',
  id_document_number: '',
  id_document_issued_by: '',
  id_document_issue_date: '',
  director_name: '',
  acting_basis: '',
  iban: '',
  bank_name: '',
  bik: '',
};

// mode: 'create' | 'view' | 'edit'
export const RightHolderForm = ({ rightHolderId, mode = 'edit', onDone, onCancel, onSwitchToEdit }) => {
  const [form, setForm] = useState(EMPTY_FORM);
  const [labels, setLabels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const readOnly = mode === 'view';

  const handleSwitchToEdit = (e) => {
    e?.preventDefault();
    if (onSwitchToEdit) {
      onSwitchToEdit();
    }
  };

  useEffect(() => {
    getLabels().then(setLabels).catch(() => setLabels([]));
  }, []);

  useEffect(() => {
    if (!rightHolderId) {
      setForm(EMPTY_FORM);
      return;
    }
    setLoading(true);
    getRightHolderDetail(rightHolderId)
      .then((data) => {
        setForm({
          ...EMPTY_FORM,
          ...data,
          label_id: data.label_id ?? '',
          id_document_issue_date: data.id_document_issue_date ?? '',
        });
      })
      .catch(() => setError('Не удалось загрузить данные правообладателя.'))
      .finally(() => setLoading(false));
  }, [rightHolderId]);

  const set = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    e.stopPropagation(); // не даём submit-у всплыть к родительской форме (например, форме договора)
    setError('');
    setSaving(true);
    try {
      // name всегда выводится автоматически: ФИО для физлица/ИП, название компании для юрлица
      const name = form.type === 'COMPANY' ? form.company_name : form.full_name;
      const payload = { ...form, name };
      Object.keys(payload).forEach((key) => {
        if (payload[key] === '') payload[key] = null;
      });
      if (payload.label_id) payload.label_id = Number(payload.label_id);

      const saved = rightHolderId
        ? await updateRightHolder(rightHolderId, payload)
        : await createRightHolder(payload);
      onDone && onDone(saved);
    } catch (err) {
      setError(err.response?.data?.detail || 'Не удалось сохранить правообладателя.');
    } finally {
      setSaving(false);
    }
  };

  const isCompany = form.type === 'COMPANY';
  const isPersonLike = form.type === 'INDIVIDUAL' || form.type === 'IP';

  if (loading) return <div className="loading-text">Загрузка...</div>;

  return (
    <form className="right-holder-form" onSubmit={handleSubmit}>
      {error && <div className="wizard-error">{error}</div>}

      <div className="form-group">
        <label className="form-label">Тип</label>
        <select className="form-control" value={form.type} onChange={set('type')} disabled={readOnly}>
          {RIGHT_HOLDER_TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      <div className="form-group">
        <label className="form-label">Псевдоним</label>
        <input className="form-control" value={form.alias || ''} onChange={set('alias')} disabled={readOnly} />
      </div>

      <div className="form-group">
        <label className="form-label">Лейбл</label>
        <select className="form-control" value={form.label_id ?? ''} onChange={set('label_id')} disabled={readOnly}>
          <option value="">Без лейбла</option>
          {labels.map((l) => (
            <option key={l.id} value={l.id}>{l.name}</option>
          ))}
        </select>
      </div>

      {isPersonLike && (
        <div className="form-group">
          <label className="form-label">ФИО *</label>
          <input className="form-control" value={form.full_name || ''} onChange={set('full_name')} required disabled={readOnly} />
        </div>
      )}

      {isCompany && (
        <div className="form-group">
          <label className="form-label">Название компании *</label>
          <input className="form-control" value={form.company_name || ''} onChange={set('company_name')} required disabled={readOnly} />
        </div>
      )}

      {(isPersonLike || isCompany) && (
        <div className="form-group">
          <label className="form-label">ИИН/БИН{(isCompany || form.type === 'IP') ? ' *' : ''}</label>
          <input
            className="form-control"
            value={form.iin_bin || ''}
            onChange={set('iin_bin')}
            required={isCompany || form.type === 'IP'}
            disabled={readOnly}
          />
        </div>
      )}

      <div className="form-group">
        <label className="form-label">Email</label>
        <input type="email" className="form-control" value={form.email || ''} onChange={set('email')} disabled={readOnly} />
      </div>

      <div className="form-group">
        <label className="form-label">Телефон</label>
        <input className="form-control" value={form.phone || ''} onChange={set('phone')} disabled={readOnly} />
      </div>

      <div className="form-group">
        <label className="form-label">Адрес</label>
        <input className="form-control" value={form.address || ''} onChange={set('address')} disabled={readOnly} />
      </div>

      {isPersonLike && (
        <>
          <div className="form-group">
            <label className="form-label">Тип документа</label>
            <input className="form-control" value={form.id_document_type || ''} onChange={set('id_document_type')} disabled={readOnly} placeholder="Паспорт, удостоверение..." />
          </div>
          <div className="form-group">
            <label className="form-label">Номер документа</label>
            <input className="form-control" value={form.id_document_number || ''} onChange={set('id_document_number')} disabled={readOnly} />
          </div>
          <div className="form-group">
            <label className="form-label">Кем выдан</label>
            <input className="form-control" value={form.id_document_issued_by || ''} onChange={set('id_document_issued_by')} disabled={readOnly} />
          </div>
          <div className="form-group">
            <label className="form-label">Дата выдачи</label>
            <input type="date" className="form-control" value={form.id_document_issue_date || ''} onChange={set('id_document_issue_date')} disabled={readOnly} />
          </div>
        </>
      )}

      {isCompany && (
        <>
          <div className="form-group">
            <label className="form-label">Директор</label>
            <input className="form-control" value={form.director_name || ''} onChange={set('director_name')} disabled={readOnly} />
          </div>
          <div className="form-group">
            <label className="form-label">Действует на основании</label>
            <input className="form-control" value={form.acting_basis || ''} onChange={set('acting_basis')} disabled={readOnly} />
          </div>
        </>
      )}

      <div className="form-group">
        <label className="form-label">IBAN</label>
        <input className="form-control" value={form.iban || ''} onChange={set('iban')} disabled={readOnly} />
      </div>
      <div className="form-group">
        <label className="form-label">Банк</label>
        <input className="form-control" value={form.bank_name || ''} onChange={set('bank_name')} disabled={readOnly} />
      </div>
      <div className="form-group">
        <label className="form-label">БИК</label>
        <input className="form-control" value={form.bik || ''} onChange={set('bik')} disabled={readOnly} />
      </div>

      <div className="form-group" style={{ justifyContent: 'flex-end' }}>
        {readOnly ? (
          <>
            <button type="button" className="btn" onClick={onCancel}>Закрыть</button>
            <button type="button" className="btn-primary" onClick={handleSwitchToEdit}>✎ Редактировать</button>
          </>
        ) : (
          <>
            <button type="button" className="btn" onClick={onCancel}>Отмена</button>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? 'Сохранение...' : 'Сохранить'}
            </button>
          </>
        )}
      </div>
    </form>
  );
};
