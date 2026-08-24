// src/components/Layout/MainLayout.jsx
import React from 'react';

export function MainLayout({ children, currentPage, currentUser, onLogout, onMenuClick }) {
  // Проверяем, активен ли раздел Треков (включая детализацию)
  const isTracksActive = ['list', 'track', 'person'].includes(currentPage);
  const isCatalogActive = currentPage === 'catalog';
  const isReportActive = currentPage === 'report';
  const isCreateReportActive = currentPage === 'createReport';
  const isDictionariesActive = currentPage === 'dictionaries';

  return (
    <div className="app-minimal">
      <aside className="sidebar">
        <div className="sidebar-title">Music Archive</div>
        
        <nav className="nav-menu">
          <button
            onClick={() => onMenuClick('tracks')}
            className={`nav-link-btn ${isTracksActive ? 'active' : ''}`}
          >
            🎵 Треки
          </button>
          <button
            onClick={() => onMenuClick('catalog')}
            className={`nav-link-btn ${isCatalogActive ? 'active' : ''}`}
          >
            📂 Каталог
          </button>
          <button
            onClick={() => onMenuClick('report')}
            className={`nav-link-btn ${isReportActive ? 'active' : ''}`}
          >
            📑 Отчёты
          </button>
          <button
            onClick={() => onMenuClick('createReport')}
            className={`nav-link-btn ${isCreateReportActive ? 'active' : ''}`}
          >
            ✨ Создать отчёт
          </button>
          <button
            onClick={() => onMenuClick('dictionaries')}
            className={`nav-link-btn ${isDictionariesActive ? 'active' : ''}`}
          >
            📚 Справочники
          </button>
        </nav>

        {/* ─── USER INFO & LOGOUT ────────────────────────────────────────── */}
        {currentUser && (
          <div className="sidebar-footer" style={{
            borderTop: '1px solid #e0e0e0',
            paddingTop: '15px',
            marginTop: 'auto'
          }}>
            <div style={{
              fontSize: '12px',
              color: '#666',
              marginBottom: '8px',
              wordBreak: 'break-word'
            }}>
              <div style={{ fontWeight: 'bold' }}>👤 {currentUser.name || currentUser.email}</div>
              <div style={{ fontSize: '11px', opacity: 0.7 }}>{currentUser.role}</div>
            </div>
            <button
              onClick={onLogout}
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: '#e74c3c',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 'bold',
                transition: 'background-color 0.2s'
              }}
              onMouseEnter={(e) => e.target.style.backgroundColor = '#c0392b'}
              onMouseLeave={(e) => e.target.style.backgroundColor = '#e74c3c'}
            >
              🚪 Выход
            </button>
          </div>
        )}
      </aside>

      <main className="content-area">
        {children}
      </main>
    </div>
  );
}