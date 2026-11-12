import React from 'react';

export const getAnnexItemColumns = ({ onEdit }) => [
  { field: 'line_number', headerName: '№', width: 70, sortable: true },
  { field: 'code', headerName: 'Код/ISRC', width: 120, sortable: true },
  { field: 'track_title', headerName: 'Название', flex: 1.5, sortable: true },
  { field: 'artist_name', headerName: 'Исполнитель', flex: 1, sortable: true },
  {
    field: 'related_rights_percent',
    headerName: 'Смежные %',
    width: 120,
    sortable: true,
    valueFormatter: (p) => (p.value != null ? `${p.value}%` : '—'),
  },
  { field: 'composer_name', headerName: 'Композитор', flex: 1, sortable: true },
  {
    field: 'composer_percent',
    headerName: '% муз.',
    width: 100,
    sortable: true,
    valueFormatter: (p) => (p.value != null ? `${p.value}%` : '—'),
  },
  { field: 'lyricist_name', headerName: 'Автор текста', flex: 1, sortable: true },
  {
    field: 'lyricist_percent',
    headerName: '% текста',
    width: 100,
    sortable: true,
    valueFormatter: (p) => (p.value != null ? `${p.value}%` : '—'),
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
            onClick={() => onEdit && onEdit(params.data)}
            title="Редактировать произведение"
          >
            ✎
          </button>
          <button
            type="button"
            className="btn-sm btn-danger"
            onClick={() => params.context.requestDelete(params.data)}
            title="Удалить произведение"
            style={{ marginLeft: '0.25rem' }}
          >
            🗑
          </button>
        </>
      );
    },
  },
];
