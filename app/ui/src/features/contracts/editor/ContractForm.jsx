import React, { useState, useEffect } from 'react';
import { getContractDetail, createContract, updateContract } from '../api/contracts.api';
import { CONTRACT_STATUS_OPTIONS } from '../components/contractFilterFields';
import { RightHolderSelector } from './RightHolderSelector';

const DEFAULT_DIRECTION_TYPE = 'DIRECT_ARTIST';

const EMPTY_FORM = {
  rights_holder_id: null,
  contract_number: '',
  signed_date: '',
  valid_from: '',
  valid_to: '',
  status: 'DRAFT',
  direction_type: DEFAULT_DIRECTION_TYPE,
};

// mode: 'create' | 'view' | 'edit'
export const ContractForm = ({ 
  contractId, 
  mode = 'edit', 
  onDone, 
  onCancel, 
  onSwitchToEdit 
}) => {
  const [form, setForm] = useState(EMPTY_FORM);
  const [selectedRightHolderName, setSelectedRightHolderName] = useState('');
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

  // Load contract detail
  useEffect(() => {
    if (!contractId) {
      setForm(EMPTY_FORM);
      setSelectedRightHolderName('');
      return;
    }
    setLoading(true);
    getContractDetail(contractId)
      .then((data) => {
        const rightHolderId = data.rights_holder_id || data.right_holder_id;
        setForm({
          rights_holder_id: rightHolderId,
          contract_number: data.contract_number || '',
          signed_date: data.signed_date || '',
          valid_from: data.valid_from || '',
          valid_to: data.valid_to || '',
          status: data.status || 'DRAFT',
          direction_type: data.direction_type || DEFAULT_DIRECTION_TYPE,
        });
        setSelectedRightHolderName(data.right_holder_name || '');
      })
      .catch(() => setError('Не удалось загрузить данные договора.'))
      .finally(() => setLoading(false));
  }, [contractId]);

  const set = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const handleRightHolderSelect = (rightHolder) => {
    setForm((prev) => ({ ...prev, rights_holder_id: rightHolder?.id || null }));
    setSelectedRightHolderName(rightHolder?.name || '');
  };

  const handleRightHolderCreated = (createdRightHolder) => {
    if (createdRightHolder?.id) {
      setForm((prev) => ({ ...prev, rights_holder_id: createdRightHolder.id }));
      setSelectedRightHolderName(createdRightHolder.name || '');
    }
  };

  // Вызывается по клику кнопки "Сохранить", а не через submit формы: форма
  // договора не может быть <form>, т.к. RightHolderSelector рендерит внутри неё
  // свою собственную <form> (RightHolderForm) — вложенные <form> невалидны и
  // приводили к тому, что "Сохранить" в форме ПО реально отправлял форму договора.
  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!form.rights_holder_id) {
      setError('Выберите правообладателя.');
      return;
    }
    if (!form.contract_number?.trim()) {
      setError('Укажите номер договора.');
      return;
    }
    setError('');
    setSaving(true);
    try {
      const payload = { ...form };
      // Дата подписи заполняется автоматически текущей датой при создании
      if (!contractId) {
        payload.signed_date = new Date().toISOString().slice(0, 10);
      }

      // Convert empty strings to null
      Object.keys(payload).forEach((key) => {
        if (payload[key] === '') payload[key] = null;
      });

      if (contractId) {
        await updateContract(contractId, payload);
      } else {
        await createContract(payload);
      }
      onDone && onDone();
    } catch (err) {
      setError(err.response?.data?.detail || 'Не удалось сохранить договор.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="loading-text">Загрузка...</div>;

  return (
    <div className="contract-form">
      {error && <div className="wizard-error">{error}</div>}

      <div className="form-group">
        <label className="form-label">Номер договора *</label>
        <input
          className="form-control"
          value={form.contract_number || ''}
          onChange={set('contract_number')}
          disabled={readOnly}
        />
      </div>

      <div className="form-group">
        <label className="form-label">Статус</label>
        <select className="form-control" value={form.status || ''} onChange={set('status')} disabled={readOnly}>
          {CONTRACT_STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      <div className="form-group">
        <label className="form-label">Действительна с</label>
        <input
          type="date"
          className="form-control"
          value={form.valid_from || ''}
          onChange={set('valid_from')}
          disabled={readOnly}
        />
      </div>

      <div className="form-group">
        <label className="form-label">Действительна по</label>
        <input
          type="date"
          className="form-control"
          value={form.valid_to || ''}
          onChange={set('valid_to')}
          disabled={readOnly}
        />
      </div>

      <RightHolderSelector
        selectedRightHolderId={form.rights_holder_id}
        selectedRightHolderName={selectedRightHolderName}
        onSelect={handleRightHolderSelect}
        onRightHolderCreated={handleRightHolderCreated}
        readOnly={readOnly}
      />

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
