import React, { useEffect, useState } from 'react';
import { getPerson, updatePerson } from './api/tracks.api';
import './tracks.css';

export const PersonDetailPage = ({ personId, onBack, onTrackClick }) => {
  const [person, setPerson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editName, setEditName] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setLoading(true);
    getPerson(personId)
      .then((p) => {
        setPerson(p);
        setEditName(p.full_name);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [personId]);

  const handleSave = async () => {
    if (saving || !editName.trim()) return;
    setSaving(true);
    setSaved(false);
    try {
      const updated = await updatePerson(personId, editName.trim());
      setPerson((prev) => ({ ...prev, full_name: updated.full_name }));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error(err);
      alert('Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSave();
  };

  if (loading) {
    return (
      <div className="detail-page">
        <div className="loading-overlay" style={{ position: 'relative', height: '200px' }}>
          <div className="loading-spinner" />
          <span className="loading-text">Загружаем данные...</span>
        </div>
      </div>
    );
  }

  if (!person) {
    return (
      <div className="detail-page">
        <button className="btn-back" onClick={onBack}>← Назад</button>
        <p>Участник не найден</p>
      </div>
    );
  }

  return (
    <div className="detail-page">
      <button className="btn-back" onClick={onBack}>← Назад</button>

      <section className="detail-section">
        <h2 className="detail-section__title">Участник</h2>
        <div className="person-edit-row">
          <label className="filter-field__label">Полное имя</label>
          <div className="person-edit-controls">
            <input
              className="filter-field__input person-edit-input"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={saving}
            />
            <button
              className={`btn-search ${saving ? 'btn-search--loading' : ''}`}
              onClick={handleSave}
              disabled={saving || editName.trim() === person.full_name}
            >
              {saving ? 'Сохранение...' : 'Сохранить'}
            </button>
            {saved && <span className="person-saved-badge">✓ Сохранено</span>}
          </div>
        </div>
      </section>

      <section className="detail-section">
        <h2 className="detail-section__title">Треки</h2>
        {person.tracks?.length > 0 ? (
          <table className="rights-table">
            <thead>
              <tr>
                <th>Название</th>
                <th>ISRC</th>
                <th>Роль</th>
              </tr>
            </thead>
            <tbody>
              {person.tracks.map((t) => (
                <tr key={`${t.id}-${t.role}`}>
                  <td>
                    <span
                      className="track-title-link"
                      onClick={() => onTrackClick && onTrackClick(t.id)}
                    >
                      {t.title}
                    </span>
                  </td>
                  <td>{t.isrc || '—'}</td>
                  <td>{t.role}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="detail-empty">Нет связанных треков</p>
        )}
      </section>
    </div>
  );
};
