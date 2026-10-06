import React, { useCallback, useMemo } from 'react';
import { DataGrid } from '../../../components/shared/DataGrid';
import { getCatalogDiffColumns, getCatalogDeletedColumns } from './catalogDiffColumns';

// Табличный вывод изменившихся/удаленных треков.
export const CatalogDiffGrid = ({ rows, searchTrigger, isDeleted }) => {
  
  const columnDefs = useMemo(() => {
    return isDeleted ? getCatalogDeletedColumns() : getCatalogDiffColumns();
  }, [isDeleted]);

  const fetchRows = useCallback(
    async (_filters, limit, offset) => ({
      items: rows.slice(offset, offset + limit),
      total: rows.length,
    }),
    [rows]
  );

  const getRowClass = (params) => {
    if (!params.data) return '';
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