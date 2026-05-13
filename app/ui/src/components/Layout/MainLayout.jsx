// src/components/Layout/MainLayout.jsx
import React from 'react';

export function MainLayout({ children, currentPage, onMenuClick }) {
  // Проверяем, активен ли раздел Треков (включая детализацию)
  const isTracksActive = ['list', 'track', 'person'].includes(currentPage);
  const isCatalogActive = currentPage === 'catalog';
  const isReportActive = currentPage === 'report';
  const isCreateReportActive = currentPage === 'createReport';

  return (
    <div className="app-minimal">
      <aside className="sidebar">
        <div className="sidebar-title">Music Archive</div>
        <nav className="nav-menu">
          {/* Используем обычные кнопки вместо NavLink */}
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
        </nav>
      </aside>
      
      <main className="content-area">
        {children}
      </main>
    </div>
  );
}