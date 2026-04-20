import React, { useEffect, useState } from 'react';
import { getTrackDetail } from './api/tracks.api';
import './tracks.css';

export const TrackDetailPage = ({ trackId, onBack, onPersonClick }) => {
  const [track, setTrack] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getTrackDetail(trackId)
      .then(setTrack)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [trackId]);

  if (loading) {
    return (
      <div className="detail-page">
        <div className="loading-overlay" style={{ position: 'relative', height: '200px' }}>
          <div className="loading-spinner" />
          <span className="loading-text">Загружаем данные трека...</span>
        </div>
      </div>
    );
  }

  if (!track) {
    return (
      <div className="detail-page">
        <button className="btn-back" onClick={onBack}>← Назад к списку</button>
        <p>Трек не найден</p>
      </div>
    );
  }

  // Группируем persons по роли
  const personsByRole = {};
  (track.persons || []).forEach((p) => {
    if (!personsByRole[p.role]) personsByRole[p.role] = [];
    personsByRole[p.role].push(p);
  });

  // Группируем rights по category
  const authorRights = (track.rights || []).filter((r) => r.category?.toLowerCase().includes('author'));
  const relatedRights = (track.rights || []).filter((r) => r.category?.toLowerCase().includes('related'));

  return (
    <div className="detail-page">
      <button className="btn-back" onClick={onBack}>← Назад к списку</button>

      {/* Основная информация */}
      <section className="detail-section">
        <h2 className="detail-section__title">Трек</h2>
        <div className="detail-fields">
          <div className="detail-field">
            <span className="detail-field__label">ID</span>
            <span className="detail-field__value">{track.id}</span>
          </div>
          <div className="detail-field">
            <span className="detail-field__label">Название</span>
            <span className="detail-field__value">{track.title}</span>
          </div>
          <div className="detail-field">
            <span className="detail-field__label">ISRC</span>
            <span className="detail-field__value">{track.isrc || '—'}</span>
          </div>
          <div className="detail-field">
            <span className="detail-field__label">Код лейбла</span>
            <span className="detail-field__value">{track.label_own_code || '—'}</span>
          </div>
          <div className="detail-field">
            <span className="detail-field__label">Лейблы</span>
            <span className="detail-field__value">
              {track.labels?.map((l) => l.name).join(', ') || '—'}
            </span>
          </div>
          {track.duration && (
            <div className="detail-field">
              <span className="detail-field__label">Длительность</span>
              <span className="detail-field__value">{track.duration}</span>
            </div>
          )}
        </div>
      </section>

      {/* Релиз */}
      <section className="detail-section">
        <h2 className="detail-section__title">Релиз</h2>
        {track.release ? (
          <div className="detail-fields">
            <div className="detail-field">
              <span className="detail-field__label">UPC</span>
              <span className="detail-field__value">{track.release.upc || '—'}</span>
            </div>
            <div className="detail-field">
              <span className="detail-field__label">Название альбома</span>
              <span className="detail-field__value">{track.release.title}</span>
            </div>
            <div className="detail-field">
              <span className="detail-field__label">Дата релиза</span>
              <span className="detail-field__value">{track.release.release_date || '—'}</span>
            </div>
            <div className="detail-field">
              <span className="detail-field__label">Статус</span>
              <span className="detail-field__value">{track.release.status || '—'}</span>
            </div>
          </div>
        ) : (
          <p className="detail-empty">Нет данных о релизе</p>
        )}
      </section>

      {/* Участники */}
      <section className="detail-section">
        <h2 className="detail-section__title">Участники</h2>
        {Object.keys(personsByRole).length > 0 ? (
          <div className="detail-persons">
            {Object.entries(personsByRole).map(([role, persons]) => (
              <div key={role} className="detail-person-group">
                <span className="detail-person-group__role">{role}</span>
                <span className="detail-person-group__names">
                  {persons.map((p, i) => (
                    <React.Fragment key={p.id}>
                      {i > 0 && ', '}
                      <span
                        className="track-title-link"
                        onClick={() => onPersonClick && onPersonClick(p.id)}
                      >
                        {p.name}
                      </span>
                    </React.Fragment>
                  ))}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="detail-empty">Нет данных об участниках</p>
        )}
      </section>

      {/* Правообладатели */}
      <section className="detail-section">
        <h2 className="detail-section__title">Правообладатели</h2>
        {renderRightsTable('Author', authorRights)}
        {renderRightsTable('Related', relatedRights)}
      </section>
    </div>
  );
};

function renderRightsTable(title, rows) {
  if (!rows.length) {
    return (
      <div className="rights-block">
        <h3 className="rights-block__title">{title}</h3>
        <p className="detail-empty">Нет данных</p>
      </div>
    );
  }
  return (
    <div className="rights-block">
      <h3 className="rights-block__title">{title}</h3>
      <table className="rights-table">
        <thead>
          <tr>
            <th>Правообладатель</th>
            <th>ALL</th>
            <th>INT</th>
            <th>MOB</th>
            <th>PUB</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{r.holder}</td>
              <td>{r.ALL != null ? `${r.ALL}%` : '—'}</td>
              <td>{r.INT != null ? `${r.INT}%` : '—'}</td>
              <td>{r.MOB != null ? `${r.MOB}%` : '—'}</td>
              <td>{r.PUB != null ? `${r.PUB}%` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
