import React, { useMemo } from 'react';
import { DataGrid } from '../../../components/shared/DataGrid';
import { getRightHolderColumns } from './rightHolderColumns';

export const RightHolderGrid = ({ fetchRightHolders, filters, onView, onEdit, onDelete, searchTrigger }) => {
  const columnDefs = useMemo(() => getRightHolderColumns({ onView, onEdit }), [onView, onEdit]);

  return (
    <DataGrid
      columnDefs={columnDefs}
      fetchRows={fetchRightHolders}
      filters={filters}
      searchTrigger={searchTrigger}
      deleteConfirm={{
        getMessage: (row) => `Удалить правообладателя "${row.name}"? Связанные договоры и права должны быть удалены или переназначены заранее.`,
        onConfirm: (row) => onDelete && onDelete(row.id),
      }}
    />
  );
};
