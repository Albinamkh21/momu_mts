import React, { useState } from 'react';
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
  const { loading, labels, fetchTracksData } = useTracks();
  const [selectedPerson, setSelectedPerson] = useState(null);
  const [filters, setFilters] = useState(getInitialFilters);
  const [searchTrigger, setSearchTrigger] = useState(0);

  const handleSearch = () => {
    if (!loading) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
      // Просто увеличиваем счетчик, чтобы TrackGrid понял, что нужно обновить данные
      setSearchTrigger(prev => prev + 1);
    }
  };

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
        {/* Анимация загрузки сохранена */}
        {loading && (
          <div className="loading-overlay">
            <div className="loading-spinner" />
            <span className="loading-text">Загружаем треки...</span>
          </div>
        )}
        
        {/* Грид теперь работает в режиме Infinite */}
        <TrackGrid 
          fetchTracks={fetchTracksData} 
          filters={filters}
          searchTrigger={searchTrigger}
          onPersonClick={setSelectedPerson} 
          onTrackClick={onTrackClick} 
        />
      </div>

      {/* Сайдбар Person сохранен полностью */}
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