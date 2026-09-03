import React, { useCallback, useEffect, useState } from 'react';
import { ReportHistoryFilters } from './components/ReportHistoryFilters';
import { ReportHistoryTable } from './components/ReportHistoryTable';
import {
  getReportHistory,
  deleteReportHistory,
  getPartners,
  getRightCategories,
  getRightUsageTypes,
} from './api/reportHistory.api';
import './reportHistory.css';

const PAGE_SIZE = 50;

const EMPTY_FILTERS = {
  partner_id: '',
  right_category_id: '',
  right_usage_type_id: '',
  date_from: '',
  date_to: '',
};

// Разбирает значения <input type="month"> ("YYYY-MM") в year_from/month_from и year_to/month_to для API.
const buildApiParams = (filters) => {
  const params = {};
  if (filters.partner_id !== '') params.partner_id = filters.partner_id;
  if (filters.right_category_id !== '') params.right_category_id = filters.right_category_id;
  if (filters.right_usage_type_id !== '') params.right_usage_type_id = filters.right_usage_type_id;
  if (filters.date_from) {
    const [year, month] = filters.date_from.split('-');
    params.year_from = parseInt(year, 10);
    params.month_from = parseInt(month, 10);
  }
  if (filters.date_to) {
    const [year, month] = filters.date_to.split('-');
    params.year_to = parseInt(year, 10);
    params.month_to = parseInt(month, 10);
  }
  return params;
};

/**
 * Вкладка "История отчётов" — полностью независимая страница (свой api/components),
 * не зависит от CreateReportPage/ReportPage. Может быть вынесена в отдельный пункт меню.
 */
export function ReportHistoryPage() {
  const [partners, setPartners] = useState([]);
  const [categories, setCategories] = useState([]);
  const [usageTypes, setUsageTypes] = useState([]);

  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [sortBy, setSortBy] = useState('created_at');
  const [sortDir, setSortDir] = useState('desc');
  const [offset, setOffset] = useState(0);

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [selectedIds, setSelectedIds] = useState(new Set());
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [p, c, u] = await Promise.all([getPartners(), getRightCategories(), getRightUsageTypes()]);
        setPartners(p || []);
        setCategories(c || []);
        setUsageTypes(u || []);
      } catch (err) {
        console.error(err);
      }
    })();
  }, []);

  const fetchData = useCallback(async (currentFilters, currentSortBy, currentSortDir, currentOffset) => {
    setLoading(true);
    setError('');
    try {
      const params = {
        sort_by: currentSortBy,
        sort_dir: currentSortDir,
        limit: PAGE_SIZE,
        offset: currentOffset,
        ...buildApiParams(currentFilters),
      };

      const response = await getReportHistory(params);
      const totalHeader = response.headers['x-total-count'];
      setItems(response.data || []);
      setTotal(totalHeader ? parseInt(totalHeader, 10) : 0);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Не удалось загрузить историю отчётов');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData(filters, sortBy, sortDir, offset);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset, sortBy, sortDir]);

  const handleSearch = () => {
    setOffset(0);
    fetchData(filters, sortBy, sortDir, 0);
  };

  const handleClear = () => {
    setFilters(EMPTY_FILTERS);
    setOffset(0);
    fetchData(EMPTY_FILTERS, sortBy, sortDir, 0);
  };

  const handleSortChange = (key) => {
    if (sortBy === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(key);
      setSortDir('asc');
    }
    setOffset(0);
  };

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = (checked) => {
    setSelectedIds(checked ? new Set(items.map((it) => it.id)) : new Set());
  };

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    if (!window.confirm(`Удалить выбранные отчёты (${selectedIds.size})?`)) return;

    setDeleting(true);
    setError('');
    try {
      await deleteReportHistory(Array.from(selectedIds));
      setSelectedIds(new Set());
      await fetchData(filters, sortBy, sortDir, offset);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Не удалось удалить отчёты');
    } finally {
      setDeleting(false);
    }
  };

  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return (
    <div className="report-history-page">
      <h2 className="page-title">История отчётов</h2>

      <ReportHistoryFilters
        filters={filters}
        onChange={setFilters}
        onSearch={handleSearch}
        onClear={handleClear}
        loading={loading}
        partners={partners}
        categories={categories}
        usageTypes={usageTypes}
      />

      {error && <div className="alert-message error">{error}</div>}

      <div className="dictionary-table-card" style={{ marginTop: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span>{total === 0 ? 0 : offset + 1}–{Math.min(offset + PAGE_SIZE, total)} из {total}</span>
          <button
            type="button"
            className="btn-danger"
            disabled={selectedIds.size === 0 || deleting}
            onClick={handleDeleteSelected}
          >
            {deleting ? 'Удаление...' : `🗑 Удалить выбранные (${selectedIds.size})`}
          </button>
        </div>

        <ReportHistoryTable
          items={items}
          loading={loading}
          sortBy={sortBy}
          sortDir={sortDir}
          onSortChange={handleSortChange}
          selectedIds={selectedIds}
          onToggleSelect={toggleSelect}
          onToggleSelectAll={toggleSelectAll}
        />

        <div className="dictionary-pagination">
          <button type="button" className="btn-secondary" disabled={!canPrev} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
            ← Назад
          </button>
          <span>{total === 0 ? 0 : offset + 1}–{Math.min(offset + PAGE_SIZE, total)} из {total}</span>
          <button type="button" className="btn-secondary" disabled={!canNext} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
            Вперёд →
          </button>
        </div>
      </div>
    </div>
  );
}

export default ReportHistoryPage;
