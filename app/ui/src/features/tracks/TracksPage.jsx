import React, { useState } from 'react';
import { useTracks } from './hooks/useTracks';
import { TrackGrid } from './components/TrackGrid';
import { CrudPageLayout } from '../../components/shared/CrudPageLayout';
import { getTrackFilterFields } from './components/trackFilterFields';
import { TrackWizardPage } from './editor/TrackWizardPage';
import { deleteTrack } from './api/tracks.api';
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

export const TracksPage = ({ onTrackClick, isComingFromDetail = false }) => {
  const { loading, labels, fetchTracksData } = useTracks();
  const [selectedPerson, setSelectedPerson] = useState(null);
  // Se vindo do menu (isComingFromDetail=false), inicia com filtros vazios
  // Se voltando de um detalhe (isComingFromDetail=true), carrega filtros salvos
  const [filters, setFilters] = useState(() => 
    isComingFromDetail ? getInitialFilters() : { title: '', isrc: '', label_own_code: '', label_id: '', artist_name: '', author_name: '' }
  );
  const [searchTrigger, setSearchTrigger] = useState(0);
  // null = closed, { trackId: null } = creating a new track, { trackId } = editing
  const [editorState, setEditorState] = useState(null);
  const [deleteError, setDeleteError] = useState('');

  const handleSearch = () => {
    if (!loading) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
      // Просто увеличиваем счетчик, чтобы TrackGrid понял, что нужно обновить данные
      setSearchTrigger(prev => prev + 1);
    }
  };

  const handleFiltersChange = (newFilters) => {
    setFilters(newFilters);
  };

  const openNewTrackEditor = () => setEditorState({ trackId: null });
  const openEditTrackEditor = (trackId) => setEditorState({ trackId });
  const closeEditor = () => setEditorState(null);

  const handleEditorDone = () => {
    closeEditor();
    // Обновляем грид, чтобы отобразить созданный/изменённый трек
    setSearchTrigger(prev => prev + 1);
  };

  const handleDeleteTrack = async (trackId) => {
    setDeleteError('');
    try {
      await deleteTrack(trackId);
      setSearchTrigger((prev) => prev + 1);
    } catch (err) {
      setDeleteError(err.response?.data?.detail || 'Не удалось удалить трек.');
    }
  };

  return (
    <CrudPageLayout
      className="tracks-page"
      filterFields={getTrackFilterFields(labels)}
      filters={filters}
      onFiltersChange={handleFiltersChange}
      onSearch={handleSearch}
      loading={loading}
      addButton={{ label: 'Новый трек', onClick: openNewTrackEditor }}
      editorSlot={editorState && (
        <div className="track-editor-inline">
          <TrackWizardPage
            trackId={editorState.trackId}
            onDone={handleEditorDone}
            onCancel={closeEditor}
          />
        </div>
      )}
      error={deleteError}
      sidebar={selectedPerson && (
        <div className="person-sidebar">
          <h3>{selectedPerson.name}</h3>
          <p>Роль: {selectedPerson.role}</p>
          <hr />
          <button onClick={() => setSelectedPerson(null)}>Закрыть</button>
        </div>
      )}
    >
      <TrackGrid
        fetchTracks={fetchTracksData}
        filters={filters}
        searchTrigger={searchTrigger}
        onPersonClick={setSelectedPerson}
        onTrackClick={onTrackClick}
        onEditTrack={openEditTrackEditor}
        onDeleteTrack={handleDeleteTrack}
      />
    </CrudPageLayout>
  );
};