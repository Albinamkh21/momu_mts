import React, { useState } from 'react';

export const FiltersPanel = ({ filters, onChange, onSearch, loading, labels }) => {
  const [collapsed, setCollapsed] = useState(false);

  const set = (key) => (e) => onChange({ ...filters, [key]: e.target.value });

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !loading) onSearch();
  };

  return (
    <div className={`filters-panel ${collapsed ? 'filters-panel--collapsed' : ''}`}>
      <div className="filters-header" onClick={() => setCollapsed(!collapsed)}>
        <span className="filters-header__title">Фильтры</span>
        <span className={`filters-header__arrow ${collapsed ? 'filters-header__arrow--down' : 'filters-header__arrow--up'}`}>
          ▲
        </span>
      </div>

      <div className={`filters-body ${collapsed ? 'filters-body--hidden' : ''}`}>
        <div className="filters-row">
          <div className="filter-field">
            <label className="filter-field__label">Название трека</label>
            <input
              className={`filter-field__input ${loading ? 'filter-field__input--disabled' : ''}`}
              value={filters.title}
              onChange={set('title')}
              onKeyDown={handleKeyDown}
              disabled={loading}
              placeholder="Название..."
            />
          </div>

          <div className="filter-field">
            <label className="filter-field__label">ISRC</label>
            <input
              className={`filter-field__input ${loading ? 'filter-field__input--disabled' : ''}`}
              value={filters.isrc}
              onChange={set('isrc')}
              onKeyDown={handleKeyDown}
              disabled={loading}
              placeholder="ISRC..."
            />
          </div>

          <div className="filter-field">
            <label className="filter-field__label">Код лейбла</label>
            <input
              className={`filter-field__input ${loading ? 'filter-field__input--disabled' : ''}`}
              value={filters.label_own_code}
              onChange={set('label_own_code')}
              onKeyDown={handleKeyDown}
              disabled={loading}
              placeholder="Код..."
            />
          </div>
          <div className="filter-field">
            <label className="filter-field__label">Исполнитель (artist)</label>
            <input
              className={`filter-field__input ${loading ? 'filter-field__input--disabled' : ''}`}
              value={filters.artist_name || ''}
              onChange={set('artist_name')}
              onKeyDown={handleKeyDown}
              disabled={loading}
              placeholder="Имя исполнителя..."
            />
          </div>

          <div className="filter-field">
            <label className="filter-field__label">Авторы (composer / lyricist)</label>
            <input
              className={`filter-field__input ${loading ? 'filter-field__input--disabled' : ''}`}
              value={filters.author_name || ''}
              onChange={set('author_name')}
              onKeyDown={handleKeyDown}
              disabled={loading}
              placeholder="Имя автора..."
            />
          </div>

          <div className="filter-field">
            <label className="filter-field__label">Лейбл</label>
            <select
              className={`filter-field__select ${loading ? 'filter-field__select--disabled' : ''}`}
              value={filters.label_id}
              onChange={set('label_id')}
              disabled={loading}
            >
              <option value="">Все лейблы</option>
              {labels.map((l) => (
                <option key={l.id} value={l.id}>{l.name}</option>
              ))}
            </select>
          </div>

          <button
            className={`btn-search ${loading ? 'btn-search--loading' : ''}`}
            onClick={onSearch}
            disabled={loading}
          >
            {loading && <span className="loading-spinner loading-spinner--small" />}
            {loading ? 'Загрузка...' : 'Найти'}
          </button>
        </div>
      </div>
    </div>
  );
};
