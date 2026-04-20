import React, { useMemo } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { PersonsRenderer } from './renderers/PersonsRenderer';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

export const TrackGrid = ({ rowData, onPersonClick, onTrackClick }) => {
  const columnDefs = useMemo(() => [
    { field: 'id', headerName: 'ID', width: 90 },
    { field: 'isrc', headerName: 'ISRC', width: 140 },
    { 
      field: 'title', 
      headerName: 'Название', 
      flex: 2, 
      filter: true,
      cellRenderer: (params) => (
        <span
          className="track-title-link"
          onClick={() => onTrackClick && onTrackClick(params.data.id)}
        >
          {params.value}
        </span>
      ),
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

  return (
    <div className="ag-theme-alpine" style={{ height: '100%', width: '100%' }}>
      <AgGridReact rowData={rowData} columnDefs={columnDefs} pagination={true} />
    </div>
  );
};