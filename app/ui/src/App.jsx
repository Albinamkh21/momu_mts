// src/App.jsx
import React, { useState, useEffect } from 'react';
import { MainLayout } from './components/Layout/MainLayout';
import { TracksPage } from './features/tracks/TracksPage';
import { TrackDetailPage } from './features/tracks/TrackDetailPage';
import { PersonDetailPage } from './features/tracks/PersonDetailPage';
import { CatalogPage } from './features/catalog/CatalogPage';
import { ReportPage } from './features/report/ReportPage';
import { CreateReportPage } from './features/report/CreateReportPage';
import { AuthPage } from './features/auth/AuthPage';
import { ForgotPassword } from './features/auth/ForgotPassword';
import { ResetPassword } from './features/auth/ResetPassword';
import { VerifyEmail } from './features/auth/VerifyEmail';

import './assets/style/minimal.css';

function App() {
  const [currentUser, setCurrentUser] = useState(() => {
    const saved = localStorage.getItem('user');
    return saved ? JSON.parse(saved) : null;
  });

  const [page, setPage] = useState(() => {
      const saved = localStorage.getItem('user');
      const path = window.location.pathname;
      const params = new URLSearchParams(window.location.search);
      const token = params.get('token') || params.get('resetToken');

      // 1. Сначала проверяем путь в URL (pathname)
      if (path.includes('reset-password')) {
        return { type: 'resetPassword', token };
      }
      
      if (path.includes('verify-email')) {
        return { type: 'verifyEmail', token };
      }

      // 2. Если путей нет, но есть параметры
      if (params.has('resetToken')) {
        return { type: 'resetPassword', token };
      }

      // 3. Авторизация и главная страница
      if (saved) return { type: 'list' };
      return { type: 'auth' };
    });

  // Очистка URL параметров после загрузки
  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    if (searchParams.has('token') || searchParams.has('resetToken')) {
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const goToTrack = (id) => setPage({ type: 'track', id });
  const goToPerson = (id) => setPage({ type: 'person', id, prev: page });
  const goToCatalog = () => setPage({ type: 'catalog', prev: page });
  const goToReport = () => setPage({ type: 'report', prev: page });
  const goToCreateReport = () => setPage({ type: 'createReport', prev: page });
  const goToTracks = () => setPage({ type: 'list', prev: page });
  const goToForgotPassword = () => setPage({ type: 'forgotPassword' });
  const goBackToAuth = () => setPage({ type: 'auth' });

  const handleAuthSuccess = (user) => {
    setCurrentUser(user);
    setPage({ type: 'list' });
  };

  const handleVerifyEmailComplete = () => {
    setPage({ type: 'auth' });
  };

  const handleResetPasswordComplete = () => {
    setPage({ type: 'auth' });
  };

  const handleLogout = () => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user');
    setCurrentUser(null);
    setPage({ type: 'auth' });
  };

  const goBack = () => {
    if (page.prev) {
      setPage(page.prev);
    } else {
      setPage({ type: 'list' });
    }
  };

  return (
    <>
      {/* ─── AUTHENTICATION PAGES ─────────────────────────────────────────────── */}
      {page.type === 'auth' && (
        <AuthPage 
          onAuthSuccess={handleAuthSuccess}
          onShowForgot={goToForgotPassword}
        />
      )}

      {page.type === 'forgotPassword' && (
        <ForgotPassword onBack={goBackToAuth} />
      )}

      {page.type === 'resetPassword' && (
        <ResetPassword 
          token={page.token}
          onComplete={handleResetPasswordComplete}
        />
      )}

      {page.type === 'verifyEmail' && (
        <VerifyEmail 
          token={page.token}
          onComplete={handleVerifyEmailComplete}
        />
      )}

      {/* ─── MAIN APPLICATION (requires authentication) ──────────────────────── */}
      {currentUser && (
        <MainLayout
          currentPage={page.type}
          currentUser={currentUser}
          onLogout={handleLogout}
          onMenuClick={(mod) => {
            if (mod === 'catalog') goToCatalog();
            else if (mod === 'report') goToReport();
            else if (mod === 'createReport') goToCreateReport();
            else goToTracks();
          }}
        >
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
      )}
    </>
  );
}

export default App;