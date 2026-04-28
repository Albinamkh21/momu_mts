import React, { useState, useEffect } from 'react';
import { useTracks } from './hooks/useTracks';
import { TrackGrid } from './components/TrackGrid';
import { FiltersPanel } from './components/FiltersPanel';
import './tracks.css';

const STORAGE_KEY = 'tracks_filters';

const getInitialFilters = () => {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    try {
      return JSON.parse(saved);
    } catch {
      return { title: '', isrc: '', label_own_code: '', label_id: '', artist_name: '', author_name: '' };
    }
  }
  return { title: '', isrc: '', label_own_code: '', label_id: '', artist_name: '', author_name: '' };
};

export const TracksPage = ({ onTrackClick }) => {
  const { data, loading, labels, refetch } = useTracks();
  const [selectedPerson, setSelectedPerson] = useState(null);
  const [filters, setFilters] = useState(getInitialFilters);

  // При монтировании загружаем с сохранёнными фильтрами
  useEffect(() => {
    refetch(filters);
  }, []); // пустой массив – только один раз при монтировании

  const handleSearch = () => {
    if (!loading) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
      refetch(filters);
    }
  };

  // При изменении фильтров (без поиска) можно тоже сохранять, но по логике сохраняем только после нажатия "Найти"
  // Однако для согласованности можно обновлять localStorage при каждом изменении:
  const handleFiltersChange = (newFilters) => {
    setFilters(newFilters);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newFilters));
  };

  return (
    <div className="tracks-page">
      <FiltersPanel
        filters={filters}
        onChange={handleFiltersChange}
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