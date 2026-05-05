import React, { useMemo, useCallback, useEffect, useRef } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { PersonsRenderer } from './renderers/PersonsRenderer';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

export const TrackGrid = ({ fetchTracks, filters, onPersonClick, onTrackClick, searchTrigger }) => {
  const gridApiRef = useRef(null);
  
  // Ref для хранения фильтров, которые будут отправлены на сервер при запросе
  // Мы синхронизируем его с пропсами, но не используем как зависимость для запроса
  const lastFiltersRef = useRef(filters);
  useEffect(() => {
    lastFiltersRef.current = filters;
  }, [filters]);

  const columnDefs = useMemo(() => [
    { field: 'id', headerName: 'ID', width: 90 },
    { field: 'isrc', headerName: 'ISRC', width: 140 },
    { 
      field: 'title', 
      headerName: 'Название', 
      flex: 2, 
      cellRenderer: (params) => {
        if (!params.data) return <span style={{ color: '#aaa' }}>Загрузка...</span>;
        return (
          <span
            className="track-title-link"
            onClick={() => onTrackClick && onTrackClick(params.data.id)}
          >
            {params.value}
          </span>
        );
      },
    },
    { field: 'label_own_code', headerName: 'Код лейбла', width: 120 },
    { 
      field: 'persons', 
      headerName: 'Авторы / Исполнители', 
      flex: 3,
      cellRenderer: PersonsRenderer,
      cellRendererParams: { onPersonClick }
    },
    { 
      field: 'labels', 
      headerName: 'Лейблы', 
      valueFormatter: p => p.value?.map(l => l.name).join(', ') 
    }
  ], [onPersonClick, onTrackClick]);

  // Функция настройки источника данных
  const setupDatasource = useCallback((gridApi) => {
    const dataSource = {
      getRows: async (rowParams) => {
        const limit = rowParams.endRow - rowParams.startRow;
        const offset = rowParams.startRow;

        // Вызываем загрузку, передавая текущие значения из Ref
        const result = await fetchTracks(lastFiltersRef.current, limit, offset);
        rowParams.successCallback(result.items, result.total);
      }
    };
    // Используем актуальный метод API
    gridApi.setGridOption('datasource', dataSource);
  }, [fetchTracks]); // Исключаем filters, чтобы ввод текста не вызывал пересоздание

  const onGridReady = (params) => {
    gridApiRef.current = params.api;
    setupDatasource(params.api);
  };

  // Этот эффект запускается ПРИ МОНТИРОВАНИИ и ПРИ НАЖАТИИ кнопки "Найти"
  useEffect(() => {
    if (gridApiRef.current) {
      gridApiRef.current.paginationGoToFirstPage();
      setupDatasource(gridApiRef.current);
    }
  }, [searchTrigger, setupDatasource]);

  return (
    <div className="ag-theme-alpine" style={{ height: '100%', width: '100%' }}>
      <AgGridReact
        columnDefs={columnDefs}
        rowModelType="infinite"
        pagination={true}
        paginationPageSize={100}
        cacheBlockSize={100}
        onGridReady={onGridReady}
        maxConcurrentDatasourceRequests={1}
      />
    </div>
  );
};