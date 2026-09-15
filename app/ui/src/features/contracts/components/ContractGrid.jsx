import React, { useMemo } from 'react';
import { DataGrid } from '../../../components/shared/DataGrid';
import { getContractColumns } from './contractColumns';

export const ContractGrid = ({ 
  fetchContracts, 
  filters, 
  onView, 
  onEdit, 
  onDelete, 
  onViewRightHolder,
  searchTrigger,
}) => {
  const columnDefs = useMemo(
    () => getContractColumns({ onView, onEdit, onViewRightHolder }),
    [onView, onEdit, onViewRightHolder]
  );

  return (
    <DataGrid
      columnDefs={columnDefs}
      fetchRows={fetchContracts}
      filters={filters}
      searchTrigger={searchTrigger}
      deleteConfirm={{
        getMessage: (row) => `Удалить договор "${row.contract_number}"?`,
        onConfirm: (row) => onDelete && onDelete(row.id),
      }}
    />
  );
};
