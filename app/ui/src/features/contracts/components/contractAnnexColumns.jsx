import React from 'react';
import { ANNEX_STATUS_OPTIONS } from './contractAnnexFilterFields';

const STATUS_LABELS = Object.fromEntries(ANNEX_STATUS_OPTIONS.map((o) => [o.value, o.label]));

export const getContractAnnexColumns = ({ onView, onEdit }) => [
  { field: 'id', headerName: 'ID', width: 90, sortable: true },
  {
    field: 'annex_number',
    headerName: 'Номер приложения',
    flex: 1.5,
    sortable: true,
    cellRenderer: (params) => {
      if (!params.data) return <span style={{ color: '#aaa' }}>Загрузка...</span>;
      return (
        <span className="grid-link" onClick={() => onView && onView(params.data.id)}>
          {params.value}
        </span>
      );
    },
  },
  { field: 'doc_date', headerName: 'Дата документа', width: 150, sortable: true },
  {
    field: 'status',
    headerName: 'Статус',
    width: 150,
    sortable: true,
    valueFormatter: (p) => STATUS_LABELS[p.value] || p.value,
  },
  { field: 'items_count', headerName: 'Произведений', width: 140, sortable: false },
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
            onClick={() => onEdit && onEdit(params.data.id)}
            title="Редактировать приложение"
          >
            ✎
          </button>
          <button
            type="button"
            className="btn-sm btn-danger"
            onClick={() => params.context.requestDelete(params.data)}
            title="Удалить приложение"
            style={{ marginLeft: '0.25rem' }}
          >
            🗑
          </button>
        </>
      );
    },
  },
];
