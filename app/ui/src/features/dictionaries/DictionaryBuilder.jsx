import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  getDictionaryList,
  createDictionaryItem,
  updateDictionaryItem,
  deleteDictionaryItem,
} from './api/dictionaries.api';

const PAGE_SIZE = 50;
const SEARCH_DEBOUNCE_MS = 350;

/**
 * Generic CRUD builder for dictionary-like data (Dynamic CRUD / Generic Admin Engine).
 * Given an endpointKey + declarative columns/formFields/searchFields config, renders a full
 * search + list + create/edit/delete UI without any dictionary-specific code.
 *
 * @param {string} endpointKey - key matching the backend DICTIONARY_REGISTRY (e.g. "labels")
 * @param {string} title - page title
 * @param {{key: string, label: string, render?: (value, row) => React.ReactNode}[]} columns
 * @param {{key: string, label: string, type?: 'text'|'number'|'textarea', required?: boolean}[]} formFields
 * @param {{key: string, label: string, placeholder?: string}[]} searchFields - text search inputs, AND-combined
 */
export function DictionaryBuilder({ endpointKey, title, columns, formFields, searchFields = [] }) {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [filters, setFilters] = useState(() =>
    Object.fromEntries(searchFields.map((f) => [f.key, '']))
  );
  const [collapsed, setCollapsed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const requestIdRef = useRef(0);
  const isFirstFilterRun = useRef(true);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [formValues, setFormValues] = useState({});
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  const fetchList = useCallback(async (currentFilters, currentOffset) => {
    const requestId = ++requestIdRef.current;
    console.log(`[fetchList] requestId=${requestId}, currentFilters=`, currentFilters, `currentOffset=${currentOffset}`);
    setLoading(true);
    setError('');
    try {
      const data = await getDictionaryList(endpointKey, { filters: currentFilters, limit: PAGE_SIZE, offset: currentOffset });
      if (requestId !== requestIdRef.current) {
        console.log(`[fetchList] requestId=${requestId} is stale, ignoring result.`);
        return; // a newer request has since started, ignore this stale result
      }
      console.log(`[fetchList] requestId=${requestId} got result, items.length=${data.items.length}, total=${data.total}`);
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      console.error(`[fetchList] requestId=${requestId} error:`, err);
      setError(err.response?.data?.detail || 'Не удалось загрузить данные справочника');
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [endpointKey]);

  // Pagination fetches right away.
  useEffect(() => {
    fetchList(filters, offset);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset, fetchList]);

  // Typing into a search field fetches after a short debounce.
  useEffect(() => {
    if (isFirstFilterRun.current) {
      isFirstFilterRun.current = false;
      console.log(`[DictionaryBuilder effect] First filter run, skipping.`);
      return;
    }
    console.log(`[DictionaryBuilder effect] Filters changed, setting debounce timer. filters=`, filters);
    const handle = setTimeout(() => {
      console.log(`[DictionaryBuilder effect] Debounce fired, calling fetchList with filters=`, filters, `offset=${offset}`);
      fetchList(filters, offset);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const handleFilterChange = (key) => (e) => {
    const { value } = e.target;
    console.log(`[handleFilterChange] key=${key}, value=${value}`);
    setOffset(0);
    setFilters((prev) => {
      const updated = { ...prev, [key]: value };
      console.log(`[handleFilterChange] filters updated to`, updated);
      return updated;
    });
  };

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
      await fetchList(filters, offset);
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
      await fetchList(filters, offset);
    } catch (err) {
      setError(err.response?.data?.detail || 'Не удалось удалить запись');
    }
  };

  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return (
    <div className="dictionary-page">
      <h1 className="dictionary-page-title">{title}</h1>

      <div className="filters-panel">
        <div className="filters-header">
          <div className="filters-header__toggle" onClick={() => setCollapsed(!collapsed)}>
            <span className="filters-header__title">Поиск</span>
            {loading && <span className="filters-header__status">обновление…</span>}
            <span className={`filters-header__arrow ${collapsed ? 'filters-header__arrow--down' : 'filters-header__arrow--up'}`}>
              ▲
            </span>
          </div>
          <button type="button" className="btn btn-primary" onClick={openCreateModal}>
            + Добавить
          </button>
        </div>

        {searchFields.length > 0 && (
          <div className={`filters-body ${collapsed ? 'filters-body--hidden' : ''}`}>
            <div className="filters-row">
              {searchFields.map((field) => (
                <div className="filter-field" key={field.key}>
                  <label className="filter-field__label">{field.label}</label>
                  <input
                    className="filter-field__input"
                    value={filters[field.key] ?? ''}
                    onChange={handleFilterChange(field.key)}
                    placeholder={field.placeholder || `${field.label}...`}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {error && <div className="alert-message error">{error}</div>}

      <div className="dictionary-table-card">
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
            {loading && items.length === 0 && (
              <tr>
                <td colSpan={columns.length + 1}>Загрузка...</td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={columns.length + 1}>Нет данных</td>
              </tr>
            )}
            {items.map((item) => (
              <tr key={item.id}>
                {columns.map((col) => (
                  <td key={col.key}>{col.render ? col.render(item[col.key], item) : String(item[col.key] ?? '')}</td>
                ))}
                <td className="dictionary-row-actions">
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

        <div className="dictionary-pagination">
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
      </div>

      {isModalOpen && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-panel modal-panel--wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h4>{editingItem ? 'Редактировать запись' : 'Новая запись'}</h4>
              <button className="modal-close" onClick={closeModal}>✕</button>
            </div>

            <form onSubmit={handleSubmit} className="modal-body">
              {formFields.map((field) => (
                <div className="dict-form-row" key={field.key}>
                  <label className="dict-form-label">
                    {field.label}
                    {field.required && <span className="dict-form-required"> *</span>}
                  </label>
                  <div className="dict-form-control">
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
                  </div>
                </div>
              ))}

              {formError && <p className="dict-form-error">{formError}</p>}

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

