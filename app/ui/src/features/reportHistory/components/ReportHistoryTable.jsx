import React from 'react';

const COLUMNS = [
  { key: 'partner_name', label: 'Партнёр' },
  { key: 'right_category_name', label: 'Категория прав' },
  { key: 'right_usage_type_name', label: 'Тип использования' },
  { key: 'report_month', label: 'Месяц' },
  { key: 'report_year', label: 'Год' },
  { key: 'play_count', label: 'Прослушивания' },
  { key: 'payout_amount', label: 'Сумма выплаты' },
  { key: 'price_per_play', label: 'Цена за прослушивание' },
  { key: 'created_at', label: 'Создан' },
];

const formatDate = (value) => {
  if (!value) return '';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString('ru-RU');
};

/**
 * Таблица истории отчётов: сортировка кликом по заголовку + выбор строк чекбоксами.
 * Полностью независима от таблицы треков (features/tracks) — своя реализация без ag-grid.
 */
export const ReportHistoryTable = ({ items, loading, sortBy, sortDir, onSortChange, selectedIds, onToggleSelect, onToggleSelectAll }) => {
  const allSelected = items.length > 0 && items.every((it) => selectedIds.has(it.id));

  const renderSortArrow = (key) => {
    if (sortBy !== key) return null;
    return <span className="sort-arrow">{sortDir === 'asc' ? ' ▲' : ' ▼'}</span>;
  };

  return (
    <table className="contributors-table report-history-table">
      <thead>
        <tr>
          <th style={{ width: 32 }}>
            <input
              type="checkbox"
              checked={allSelected}
              onChange={(e) => onToggleSelectAll(e.target.checked)}
              disabled={items.length === 0}
            />
          </th>
          <th style={{ cursor: 'pointer' }} onClick={() => onSortChange('id')}>
            ID{renderSortArrow('id')}
          </th>
          {COLUMNS.map((col) => (
            <th key={col.key} style={{ cursor: 'pointer' }} onClick={() => onSortChange(col.key)}>
              {col.label}{renderSortArrow(col.key)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {loading && items.length === 0 && (
          <tr>
            <td colSpan={COLUMNS.length + 2}>Загрузка...</td>
          </tr>
        )}
        {!loading && items.length === 0 && (
          <tr>
            <td colSpan={COLUMNS.length + 2}>Нет данных</td>
          </tr>
        )}
        {items.map((item) => (
          <tr key={item.id} className={selectedIds.has(item.id) ? 'report-history-row--selected' : ''}>
            <td>
              <input
                type="checkbox"
                checked={selectedIds.has(item.id)}
                onChange={() => onToggleSelect(item.id)}
              />
            </td>
            <td>{item.id}</td>
            <td>{item.partner_name}</td>
            <td>{item.right_category_name}</td>
            <td>{item.right_usage_type_name}</td>
            <td>{item.report_month}</td>
            <td>{item.report_year}</td>
            <td>{item.play_count ?? ''}</td>
            <td>{item.payout_amount ?? ''}</td>
            <td>{item.price_per_play ?? ''}</td>
            <td>{formatDate(item.created_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};

export default ReportHistoryTable;
