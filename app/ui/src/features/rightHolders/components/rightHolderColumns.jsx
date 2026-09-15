import React from 'react';
import { RIGHT_HOLDER_TYPE_OPTIONS } from './rightHolderFilterFields';

const TYPE_LABELS = Object.fromEntries(RIGHT_HOLDER_TYPE_OPTIONS.map((o) => [o.value, o.label]));

export const getRightHolderColumns = ({ onView, onEdit }) => [
  { field: 'id', headerName: 'ID', width: 90, sortable: true },
  {
    field: 'name',
    headerName: 'Имя / Название',
    flex: 2,
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
  { field: 'type', headerName: 'Тип', width: 130, sortable: true, valueFormatter: (p) => TYPE_LABELS[p.value] || p.value },
  { field: 'alias', headerName: 'Псевдоним', flex: 1, sortable: true },
  { field: 'iin_bin', headerName: 'ИИН/БИН', width: 150, sortable: true },
  { field: 'email', headerName: 'Email', flex: 1, sortable: true },
  { field: 'phone', headerName: 'Телефон', width: 150, sortable: true },
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
            title="Редактировать правообладателя"
          >
            ✎
          </button>
          <button
            type="button"
            className="btn-sm btn-danger"
            onClick={() => params.context.requestDelete(params.data)}
            title="Удалить правообладателя"
            style={{ marginLeft: '0.25rem' }}
          >
            🗑
          </button>
        </>
      );
    },
  },
];
