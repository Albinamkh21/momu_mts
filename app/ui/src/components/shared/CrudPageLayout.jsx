import React from 'react';
import { FilterPanel } from './FilterPanel';
import './shared.css';

/**
 * Common CRUD list page shell shared across modules: filter bar, optional inline
 * editor slot, grid area with loading overlay/error banner, and an optional side panel.
 */
export const CrudPageLayout = ({
  className = '',
  filterFields,
  filters,
  onFiltersChange,
  onSearch,
  loading,
  filterTitle,
  addButton,
  editorSlot,
  error,
  sidebar,
  children,
}) => (
  <div className={`crud-page ${className}`}>
    <FilterPanel
      fields={filterFields}
      filters={filters}
      onChange={onFiltersChange}
      onSearch={onSearch}
      loading={loading}
      title={filterTitle}
      addButton={addButton}
    />

    {editorSlot}

    <div className="grid-wrapper">
      {loading && (
        <div className="loading-overlay">
          <div className="loading-spinner" />
          <span className="loading-text">Загружаем данные...</span>
        </div>
      )}

      {error && <div className="wizard-error">{error}</div>}

      {children}
    </div>

    {sidebar}
  </div>
);
