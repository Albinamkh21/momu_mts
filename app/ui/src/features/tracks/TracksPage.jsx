import React, { useState } from 'react';
import { useTracks } from './hooks/useTracks';
import { TrackGrid } from './components/TrackGrid';
import { FiltersPanel } from './components/FiltersPanel';
import './tracks.css';

const emptyFilters = { title: '', isrc: '', label_own_code: '', label_id: '' };

export const TracksPage = ({ onTrackClick }) => {
  const { data, loading, labels, refetch } = useTracks();
  const [selectedPerson, setSelectedPerson] = useState(null);
  const [filters, setFilters] = useState(emptyFilters);

  const handleSearch = () => {
    if (!loading) refetch(filters);
  };

  return (
    <div className="tracks-page">
      <FiltersPanel
        filters={filters}
        onChange={setFilters}
        onSearch={handleSearch}
        loading={loading}
        labels={labels}
      />

      <div className="grid-wrapper">
        {loading && (
          <div className="loading-overlay">
            <div className="loading-spinner" />
            <span className="loading-text">Загружаем треки...</span>
          </div>
        )}
        <TrackGrid rowData={data} onPersonClick={setSelectedPerson} onTrackClick={onTrackClick} />
      </div>

      {selectedPerson && (
        <div className="person-sidebar">
          <h3>{selectedPerson.name}</h3>
          <p>Роль: {selectedPerson.role}</p>
          <hr />
          <button onClick={() => setSelectedPerson(null)}>Закрыть</button>
        </div>
      )}
    </div>
  );
};