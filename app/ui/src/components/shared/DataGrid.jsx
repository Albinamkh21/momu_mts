import React, { useMemo, useCallback, useEffect, useRef, useState } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ConfirmModal } from '../ConfirmModal';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

/**
 * Generic infinite-scroll AG Grid used by every CRUD list page.
 * `fetchRows(filters, limit, offset, sortModel)` must resolve to `{ items, total }`.
 * `sortModel` / `onSortChange` make server-side sorting a controlled prop: the parent
 * owns the current sort state and is notified whenever the user clicks a column header.
 * `deleteConfirm` is optional: `{ getMessage(row), onConfirm(row) }`. When provided,
 * column cellRenderers can trigger the shared confirmation dialog via `params.context.requestDelete(row)`.
 */
export const DataGrid = ({
  columnDefs,
  fetchRows,
  filters,
  searchTrigger,
  sortModel,
  onSortChange,
  pageSize = 100,
  deleteConfirm,
  getRowClass,
}) => {
  const gridApiRef = useRef(null);
  const [rowToDelete, setRowToDelete] = useState(null);

  // Синхронизируем ref с пропсами, но не используем filters/sortModel как зависимость запроса
  const lastFiltersRef = useRef(filters);
  useEffect(() => {
    lastFiltersRef.current = filters;
  }, [filters]);

  const lastSortModelRef = useRef(sortModel || null);
  useEffect(() => {
    lastSortModelRef.current = sortModel || null;
  }, [sortModel]);

  const setupDatasource = useCallback((gridApi) => {
    const dataSource = {
      getRows: async (rowParams) => {
        const limit = rowParams.endRow - rowParams.startRow;
        const offset = rowParams.startRow;
        const result = await fetchRows(lastFiltersRef.current, limit, offset, lastSortModelRef.current);
        rowParams.successCallback(result.items, result.total);
      },
    };
    gridApi.setGridOption('datasource', dataSource);
  }, [fetchRows]);

  const onGridReady = (params) => {
    gridApiRef.current = params.api;
    setupDatasource(params.api);
  };

  const onSortChanged = (event) => {
    // getState().sort возвращает { sortModel: [...] }, а не сам массив — используем
    // getColumnState(), который даёт плоский список колонок с их sort/sortIndex.
    const newSortModel = event.api
      .getColumnState()
      .filter((col) => col.sort != null)
      .sort((a, b) => (a.sortIndex ?? 0) - (b.sortIndex ?? 0))
      .map((col) => ({ colId: col.colId, sort: col.sort }));

    const normalizedSortModel = newSortModel.length > 0 ? newSortModel : null;
    lastSortModelRef.current = normalizedSortModel;
    onSortChange && onSortChange(normalizedSortModel);

    if (gridApiRef.current) {
      gridApiRef.current.paginationGoToFirstPage();
      setupDatasource(gridApiRef.current);
    }
  };

  // Запускается при монтировании и при изменении searchTrigger ("Найти")
  useEffect(() => {
    if (gridApiRef.current) {
      gridApiRef.current.paginationGoToFirstPage();
      setupDatasource(gridApiRef.current);
    }
  }, [searchTrigger, setupDatasource]);

  const context = useMemo(() => ({ requestDelete: setRowToDelete }), []);

  return (
    <div className="ag-theme-alpine" style={{ height: '100%', width: '100%' }}>
      <AgGridReact
        columnDefs={columnDefs}
        rowModelType="infinite"
        pagination={true}
        paginationPageSize={pageSize}
        cacheBlockSize={pageSize}
        onGridReady={onGridReady}
        onSortChanged={onSortChanged}
        maxConcurrentDatasourceRequests={1}
        context={context}
        getRowClass={getRowClass}
      />

      {deleteConfirm && (
        <ConfirmModal
          open={!!rowToDelete}
          title="Подтверждение удаления"
          message={rowToDelete ? deleteConfirm.getMessage(rowToDelete) : ''}
          confirmLabel="Удалить"
          danger
          onConfirm={() => {
            deleteConfirm.onConfirm(rowToDelete);
            setRowToDelete(null);
          }}
          onCancel={() => setRowToDelete(null)}
        />
      )}
    </div>
  );
};
