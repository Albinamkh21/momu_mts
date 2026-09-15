import React, { useState } from 'react';

/**
 * Config-driven filter bar. `fields` is an array of
 * `{ key, label, type: 'text' | 'select' | 'date', placeholder, options }`.
 * Reports the whole filters object back via `onChange`.
 */
export const FilterPanel = ({ fields, filters, onChange, onSearch, loading, title = 'Фильтры', addButton }) => {
  const [collapsed, setCollapsed] = useState(false);

  const set = (key) => (e) => onChange({ ...filters, [key]: e.target.value });

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !loading) onSearch();
  };

  const handleClearFilters = () => {
    const cleanFilters = {};
    fields.forEach((field) => {
      cleanFilters[field.key] = '';
    });
    onChange(cleanFilters);
    setTimeout(() => onSearch(), 0);
  };

  return (
    <div className={`filters-panel ${collapsed ? 'filters-panel--collapsed' : ''}`}>
      <div className="filters-header">
        <div
          onClick={() => setCollapsed(!collapsed)}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}
        >
          <span className="filters-header__title">{title}</span>
          <span className={`filters-header__arrow ${collapsed ? 'filters-header__arrow--down' : 'filters-header__arrow--up'}`}>
            ▲
          </span>
        </div>
        {addButton && (
          <button className="btn-primary" onClick={(e) => { e.stopPropagation(); addButton.onClick(); }}>
            {addButton.label}
          </button>
        )}
      </div>

      <div className={`filters-body ${collapsed ? 'filters-body--hidden' : ''}`}>
        <div className="filters-row">
          {fields.map((field) => (
            <div className="filter-field" key={field.key}>
              <label className="filter-field__label">{field.label}</label>
              {field.type === 'select' ? (
                <select
                  className={`filter-field__select ${loading ? 'filter-field__select--disabled' : ''}`}
                  value={filters[field.key] ?? ''}
                  onChange={set(field.key)}
                  disabled={loading}
                >
                  <option value="">{field.placeholder || 'Все'}</option>
                  {(field.options || []).map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              ) : (
                <input
                  type={field.type === 'date' ? 'date' : 'text'}
                  className={`filter-field__input ${loading ? 'filter-field__input--disabled' : ''}`}
                  value={filters[field.key] ?? ''}
                  onChange={set(field.key)}
                  onKeyDown={handleKeyDown}
                  disabled={loading}
                  placeholder={field.placeholder}
                />
              )}
            </div>
          ))}

          <button
            className={`btn-search ${loading ? 'btn-search--loading' : ''}`}
            onClick={onSearch}
            disabled={loading}
          >
            {loading && <span className="loading-spinner loading-spinner--small" />}
            {loading ? 'Загрузка...' : 'Найти'}
          </button>

          <button
            className={`btn-search ${loading ? 'btn-search--loading' : ''}`}
            onClick={handleClearFilters}
            disabled={loading}
            title="Очистить все фильтры"
            style={{ background: '#999' }}
          >
            ✕ Очистить
          </button>
        </div>
      </div>
    </div>
  );
};
