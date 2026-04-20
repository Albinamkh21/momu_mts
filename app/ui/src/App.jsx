import React, { useState } from 'react';
import { MainLayout } from './components/Layout/MainLayout';
import { TracksPage } from './features/tracks/TracksPage';
import { TrackDetailPage } from './features/tracks/TrackDetailPage';
import { PersonDetailPage } from './features/tracks/PersonDetailPage';

function App() {
  const [page, setPage] = useState({ type: 'list' });

  const goToTrack = (id) => setPage({ type: 'track', id });
  const goToPerson = (id) => setPage({ type: 'person', id, prev: page });
  const goBack = () => {
    if (page.prev) {
      setPage(page.prev);
    } else {
      setPage({ type: 'list' });
    }
  };

  return (
    <MainLayout>
      {page.type === 'track' && (
        <TrackDetailPage
          trackId={page.id}
          onBack={goBack}
          onPersonClick={goToPerson}
        />
      )}
      {page.type === 'person' && (
        <PersonDetailPage
          personId={page.id}
          onBack={goBack}
          onTrackClick={goToTrack}
        />
      )}
      {page.type === 'list' && (
        <TracksPage onTrackClick={goToTrack} />
      )}
    </MainLayout>
  );
}

export default App;