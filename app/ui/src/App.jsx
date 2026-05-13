// src/App.jsx
import React, { useState } from 'react';
import { MainLayout } from './components/Layout/MainLayout';
import { TracksPage } from './features/tracks/TracksPage';
import { TrackDetailPage } from './features/tracks/TrackDetailPage';
import { PersonDetailPage } from './features/tracks/PersonDetailPage';
import { CatalogPage } from './features/catalog/CatalogPage';
import { ReportPage } from './features/report/ReportPage';
import { CreateReportPage } from './features/report/CreateReportPage';
import './assets/style/minimal.css';

function App() {
  const [page, setPage] = useState({ type: 'list' });

  const goToTrack = (id) => setPage({ type: 'track', id });
  const goToPerson = (id) => setPage({ type: 'person', id, prev: page });
  const goToCatalog = () => setPage({ type: 'catalog', prev: page });
  const goToReport = () => setPage({ type: 'report', prev: page });
  const goToCreateReport = () => setPage({ type: 'createReport', prev: page });
  const goToTracks = () => setPage({ type: 'list', prev: page });

  const goBack = () => {
    if (page.prev) {
      setPage(page.prev);
    } else {
      setPage({ type: 'list' });
    }
  };

  return (
    <MainLayout currentPage={page.type} onMenuClick={(mod) => mod === 'catalog' ? goToCatalog() : (mod === 'report' ? goToReport() : (mod === 'createReport' ? goToCreateReport() : goToTracks()))}>
      
      {page.type === 'track' && (
        <TrackDetailPage trackId={page.id} onBack={goBack} onPersonClick={goToPerson} />
      )}
      
      {page.type === 'person' && (
        <PersonDetailPage personId={page.id} onBack={goBack} onTrackClick={goToTrack} />
      )}
      
      {page.type === 'catalog' && (
        <CatalogPage />
      )}

      {page.type === 'report' && (
        <ReportPage />
      )}

      {page.type === 'createReport' && (
        <CreateReportPage />
      )}
      
      {page.type === 'list' && (
        <TracksPage onTrackClick={goToTrack} />
      )}

    </MainLayout>
  );
}

export default App;