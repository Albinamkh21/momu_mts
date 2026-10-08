import React, { useMemo } from 'react';
import { DataGrid } from '../../../components/shared/DataGrid';
import { getTrackColumns } from './trackColumns';

export const TrackGrid = ({ fetchTracks, filters, onPersonClick, onTrackClick, onEditTrack, onDeleteTrack, searchTrigger, sortModel, onSortChange }) => {
  const columnDefs = useMemo(
    () => getTrackColumns({ onPersonClick, onTrackClick, onEditTrack }),
    [onPersonClick, onTrackClick, onEditTrack]
  );

  return (
    <DataGrid
      columnDefs={columnDefs}
      fetchRows={fetchTracks}
      filters={filters}
      searchTrigger={searchTrigger}
      sortModel={sortModel}
      onSortChange={onSortChange}
      deleteConfirm={{
        getMessage: (row) =>
          `Удалить трек "${row.title}"? Также будут удалены его права, участники и связи с релизом/лейблом (авторы и правообладатели удаляются, только если не используются другими треками).`,
        onConfirm: (row) => onDeleteTrack && onDeleteTrack(row.id),
      }}
    />
  );
};