import React, { useState } from 'react';

/**
 * Панель поиска для истории отчётов — независимый аналог FiltersPanel из features/tracks,
 * без каких-либо общих зависимостей с ним.
 */
export const ReportHistoryFilters = ({ filters, onChange, onSearch, onClear, loading, partners, categories, usageTypes }) => {
  const [collapsed, setCollapsed] = useState(false);

  const set = (key) => (e) => onChange({ ...filters, [key]: e.target.value });

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !loading) onSearch();
  };

  return (
    <div className={`filters-panel ${collapsed ? 'filters-panel--collapsed' : ''}`}>
      <div className="filters-header">
        <div onClick={() => setCollapsed(!collapsed)} style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
          <span className="filters-header__title">Фильтры</span>
          <span className={`filters-header__arrow ${collapsed ? 'filters-header__arrow--down' : 'filters-header__arrow--up'}`}>
            ▲
          </span>
        </div>
      </div>

      <div className={`filters-body ${collapsed ? 'filters-body--hidden' : ''}`}>
        <div className="filters-row">
          <div className="filter-field">
            <label className="filter-field__label">Период с</label>
            <input
              type="month"
              className={`filter-field__input ${loading ? 'filter-field__input--disabled' : ''}`}
              value={filters.date_from}
              onChange={set('date_from')}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
          </div>

          <div className="filter-field">
            <label className="filter-field__label">Период до</label>
            <input
              type="month"
              className={`filter-field__input ${loading ? 'filter-field__input--disabled' : ''}`}
              value={filters.date_to}
              onChange={set('date_to')}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
          </div>

          <div className="filter-field">
            <label className="filter-field__label">Партнёр</label>
            <select
              className={`filter-field__select ${loading ? 'filter-field__select--disabled' : ''}`}
              value={filters.partner_id}
              onChange={set('partner_id')}
              disabled={loading}
            >
              <option value="">Все партнёры</option>
              {partners.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
          </div>

          <div className="filter-field">
            <label className="filter-field__label">Категория прав</label>
            <select
              className={`filter-field__select ${loading ? 'filter-field__select--disabled' : ''}`}
              value={filters.right_category_id}
              onChange={set('right_category_id')}
              disabled={loading}
            >
              <option value="">Все категории</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.label || c.name}</option>
              ))}
            </select>
          </div>

          <div className="filter-field">
            <label className="filter-field__label">Тип использования</label>
            <select
              className={`filter-field__select ${loading ? 'filter-field__select--disabled' : ''}`}
              value={filters.right_usage_type_id}
              onChange={set('right_usage_type_id')}
              disabled={loading}
            >
              <option value="">Все типы</option>
              {usageTypes.map((u) => (
                <option key={u.id} value={u.id}>{u.label || u.code}</option>
              ))}
            </select>
          </div>

          <button
            type="button"
            className={`btn-search ${loading ? 'btn-search--loading' : ''}`}
            onClick={onSearch}
            disabled={loading}
          >
            {loading && <span className="loading-spinner loading-spinner--small" />}
            {loading ? 'Загрузка...' : 'Найти'}
          </button>

          <button
            type="button"
            className="btn-secondary"
            onClick={onClear}
            disabled={loading}
          >
            Очистить
          </button>
        </div>
      </div>
    </div>
  );
};

export default ReportHistoryFilters;
