import React, { useCallback, useEffect, useState } from 'react';
import {
  getDictionaryList,
  createDictionaryItem,
  updateDictionaryItem,
  deleteDictionaryItem,
} from './api/dictionaries.api';

const PAGE_SIZE = 50;

/**
 * Generic CRUD builder for dictionary-like data (Dynamic CRUD / Generic Admin Engine).
 * Given an endpointKey + declarative columns/formFields config, renders a full
 * list + create/edit/delete UI without any dictionary-specific code.
 *
 * @param {string} endpointKey - key matching the backend DICTIONARY_REGISTRY (e.g. "labels")
 * @param {string} title - page title
 * @param {{key: string, label: string, render?: (value, row) => React.ReactNode}[]} columns
 * @param {{key: string, label: string, type?: 'text'|'number'|'textarea', required?: boolean}[]} formFields
 */
export function DictionaryBuilder({ endpointKey, title, columns, formFields }) {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [formValues, setFormValues] = useState({});
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  const fetchList = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getDictionaryList(endpointKey, { search, limit: PAGE_SIZE, offset });
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err.response?.data?.detail || 'Не удалось загрузить данные справочника');
    } finally {
      setLoading(false);
    }
  }, [endpointKey, search, offset]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const openCreateModal = () => {
    setEditingItem(null);
    setFormValues({});
    setFormError('');
    setIsModalOpen(true);
  };

  const openEditModal = (item) => {
    setEditingItem(item);
    setFormValues({ ...item });
    setFormError('');
    setIsModalOpen(true);
  };

  const closeModal = () => {
    if (saving) return;
    setIsModalOpen(false);
  };

  const handleFieldChange = (key, value) => {
    setFormValues((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setFormError('');
    try {
      if (editingItem) {
        await updateDictionaryItem(endpointKey, editingItem.id, formValues);
      } else {
        await createDictionaryItem(endpointKey, formValues);
      }
      setIsModalOpen(false);
      await fetchList();
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Ошибка при сохранении записи');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (item) => {
    if (!window.confirm('Удалить эту запись?')) return;
    try {
      await deleteDictionaryItem(endpointKey, item.id);
      await fetchList();
    } catch (err) {
      setError(err.response?.data?.detail || 'Не удалось удалить запись');
    }
  };

  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return (
    <div className="page-container">
      <h1 className="page-title">{title}</h1>

      <div className="action-section" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input
          type="text"
          className="form-control"
          placeholder="Поиск..."
          value={search}
          onChange={(e) => {
            setOffset(0);
            setSearch(e.target.value);
          }}
          style={{ maxWidth: 320 }}
        />
        <button type="button" className="btn btn-primary" onClick={openCreateModal}>
          + Добавить
        </button>
      </div>

      {error && <div className="alert-message error">{error}</div>}

      <table className="contributors-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key}>{col.label}</th>
            ))}
            <th></th>
          </tr>
        </thead>
        <tbody>
          {loading && (
            <tr>
              <td colSpan={columns.length + 1}>Загрузка...</td>
            </tr>
          )}
          {!loading && items.length === 0 && (
            <tr>
              <td colSpan={columns.length + 1}>Нет данных</td>
            </tr>
          )}
          {!loading &&
            items.map((item) => (
              <tr key={item.id}>
                {columns.map((col) => (
                  <td key={col.key}>{col.render ? col.render(item[col.key], item) : String(item[col.key] ?? '')}</td>
                ))}
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button type="button" className="btn-secondary" onClick={() => openEditModal(item)}>
                    ✏️
                  </button>{' '}
                  <button type="button" className="btn-danger" onClick={() => handleDelete(item)}>
                    🗑️
                  </button>
                </td>
              </tr>
            ))}
        </tbody>
      </table>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 12 }}>
        <button
          type="button"
          className="btn-secondary"
          disabled={!canPrev}
          onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
        >
          ← Назад
        </button>
        <span>
          {total === 0 ? 0 : offset + 1}–{Math.min(offset + PAGE_SIZE, total)} из {total}
        </span>
        <button
          type="button"
          className="btn-secondary"
          disabled={!canNext}
          onClick={() => setOffset((o) => o + PAGE_SIZE)}
        >
          Вперёд →
        </button>
      </div>

      {isModalOpen && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h4>{editingItem ? 'Редактировать запись' : 'Новая запись'}</h4>
              <button className="modal-close" onClick={closeModal}>✕</button>
            </div>

            <form onSubmit={handleSubmit} className="modal-body">
              {formFields.map((field) => (
                <label className="form-label" key={field.key} style={{ display: 'block', marginBottom: 10 }}>
                  {field.label}
                  {field.required && <span style={{ color: 'red' }}> *</span>}
                  {field.type === 'textarea' ? (
                    <textarea
                      className="form-input"
                      value={formValues[field.key] ?? ''}
                      onChange={(e) => handleFieldChange(field.key, e.target.value)}
                      required={field.required}
                    />
                  ) : (
                    <input
                      className="form-input"
                      type={field.type === 'number' ? 'number' : 'text'}
                      value={formValues[field.key] ?? ''}
                      onChange={(e) =>
                        handleFieldChange(
                          field.key,
                          field.type === 'number' ? e.target.valueAsNumber : e.target.value
                        )
                      }
                      required={field.required}
                    />
                  )}
                </label>
              ))}

              {formError && <p style={{ color: 'red', margin: '0.5rem 0' }}>{formError}</p>}

              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={closeModal} disabled={saving}>
                  Отмена
                </button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? 'Сохранение...' : 'Сохранить'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
