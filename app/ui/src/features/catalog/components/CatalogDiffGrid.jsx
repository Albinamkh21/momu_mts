import React, { useCallback, useMemo } from 'react';
import { DataGrid } from '../../../components/shared/DataGrid';
import { getCatalogDiffColumns, getCatalogDeletedColumns, getCatalogNewColumns } from './catalogDiffColumns';

// Табличный вывод изменившихся/удаленных/новых треков.
export const CatalogDiffGrid = ({ rows, searchTrigger, isDeleted, isNew }) => {
  
  const columnDefs = useMemo(() => {
    if (isDeleted) return getCatalogDeletedColumns();
    if (isNew) return getCatalogNewColumns();
    return getCatalogDiffColumns();
  }, [isDeleted, isNew]);

  const fetchRows = useCallback(
    async (_filters, limit, offset) => ({
      items: rows.slice(offset, offset + limit),
      total: rows.length,
    }),
    [rows]
  );

  const getRowClass = (params) => {
    if (!params.data) return '';
    if (isNew) return 'diff-row-new';
    // Для стандартных строк берем row_type ('old' / 'new'), для удаленных — подсвечиваем как 'old'
    const rowType = params.data.row_type || (params.data.diff_type === 'DELETED' ? 'old' : '');
    return rowType ? `diff-row-${rowType}` : '';
  };

  return (
    <DataGrid
      columnDefs={columnDefs}
      fetchRows={fetchRows}
      filters={{}}
      searchTrigger={searchTrigger}
      getRowClass={getRowClass}
    />
  );
};