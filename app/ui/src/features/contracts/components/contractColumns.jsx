import React from 'react';
import { CONTRACT_STATUS_OPTIONS } from './contractFilterFields';

const STATUS_LABELS = Object.fromEntries(CONTRACT_STATUS_OPTIONS.map((o) => [o.value, o.label]));

export const getContractColumns = ({ onView, onEdit, onViewRightHolder }) => [
  { field: 'id', headerName: 'ID', width: 90, sortable: true },
  {
    field: 'contract_number',
    headerName: 'Номер договора',
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
  {
    field: 'right_holder_name',
    headerName: 'Правообладатель',
    flex: 1.5,
    sortable: false,
    cellRenderer: (params) => {
      if (!params.data) return <span style={{ color: '#aaa' }}>Загрузка...</span>;
      return (
        <span
          className="grid-link"
          onClick={() => onViewRightHolder && onViewRightHolder(params.data.rights_holder_id)}
        >
          {params.data.right_holder_name || `ID: ${params.data.rights_holder_id}`}
        </span>
      );
    },
  },
  {
    field: 'status',
    headerName: 'Статус',
    width: 130,
    sortable: true,
    valueFormatter: (p) => STATUS_LABELS[p.value] || p.value,
  },
  { field: 'valid_from', headerName: 'Действительна с', width: 130, sortable: true },
  { field: 'valid_to', headerName: 'Действительна по', width: 130, sortable: true },
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
            title="Редактировать договор"
          >
            ✎
          </button>
          <button
            type="button"
            className="btn-sm btn-danger"
            onClick={() => params.context.requestDelete(params.data)}
            title="Удалить договор"
            style={{ marginLeft: '0.25rem' }}
          >
            🗑
          </button>
        </>
      );
    },
  },
];
