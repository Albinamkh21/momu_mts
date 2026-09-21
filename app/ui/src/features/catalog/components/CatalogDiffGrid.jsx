import React, { useCallback, useMemo } from 'react';
import { DataGrid } from '../../../components/shared/DataGrid';
import { getCatalogDiffColumns } from './catalogDiffColumns';

// Табличный вывод изменившихся треков: две строки на трек подряд (row_type: 'old' затем 'new').
// Данные уже полностью загружены на клиент (rows), поэтому fetchRows просто отдаёт нужный срез.
export const CatalogDiffGrid = ({ rows, searchTrigger }) => {
  const columnDefs = useMemo(() => getCatalogDiffColumns(), []);

  const fetchRows = useCallback(
    async (_filters, limit, offset) => ({
      items: rows.slice(offset, offset + limit),
      total: rows.length,
    }),
    [rows]
  );

  const getRowClass = (params) => (params.data ? `diff-row-${params.data.row_type}` : '');

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
