import React, { useMemo } from 'react';
import { DataGrid } from '../../../components/shared/DataGrid';
import { getContractAnnexColumns } from './contractAnnexColumns';

export const ContractAnnexGrid = ({
  fetchContractAnnexes,
  filters,
  searchTrigger,
  onView,
  onEdit,
  onDelete,
}) => {
  const columnDefs = useMemo(() => getContractAnnexColumns({ onView, onEdit }), [onView, onEdit]);

  return (
    <DataGrid
      columnDefs={columnDefs}
      fetchRows={fetchContractAnnexes}
      filters={filters}
      searchTrigger={searchTrigger}
      deleteConfirm={{
        getMessage: (row) => `Удалить приложение "${row.annex_number}"? Все произведения из этого приложения будут удалены.`,
        onConfirm: (row) => onDelete && onDelete(row.id),
      }}
    />
  );
};
