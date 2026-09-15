import React from 'react';
import { PersonsRenderer } from './renderers/PersonsRenderer';

export const getTrackColumns = ({ onPersonClick, onTrackClick, onEditTrack }) => [
  { field: 'id', headerName: 'ID', width: 90, sortable: true },
  { field: 'isrc', headerName: 'ISRC', width: 140, sortable: true },
  {
    field: 'title',
    headerName: 'Название',
    flex: 2,
    sortable: true,
    cellRenderer: (params) => {
      if (!params.data) return <span style={{ color: '#aaa' }}>Загрузка...</span>;
      return (
        <span className="grid-link" onClick={() => onTrackClick && onTrackClick(params.data.id)}>
          {params.value}
        </span>
      );
    },
  },
  { field: 'label_own_code', headerName: 'Код лейбла', width: 120, sortable: true },
  {
    field: 'persons',
    headerName: 'Авторы / Исполнители',
    flex: 3,
    sortable: false,
    cellRenderer: PersonsRenderer,
    cellRendererParams: { onPersonClick },
  },
  {
    field: 'labels',
    headerName: 'Лейблы',
    sortable: false,
    valueFormatter: (p) => p.value?.map((l) => l.name).join(', '),
  },
  {
    headerName: '',
    width: 100,
    sortable: false,
    filter: false,
    cellRenderer: (params) => {
      if (!params.data) return null;
      return (
        <>
          <button
            type="button"
            className="btn-sm"
            onClick={() => onEditTrack && onEditTrack(params.data.id)}
            title="Редактировать трек"
          >
            ✎
          </button>
          <button
            type="button"
            className="btn-sm btn-danger"
            onClick={() => params.context.requestDelete(params.data)}
            title="Удалить трек"
            style={{ marginLeft: '0.25rem' }}
          >
            🗑
          </button>
        </>
      );
    },
  },
];
