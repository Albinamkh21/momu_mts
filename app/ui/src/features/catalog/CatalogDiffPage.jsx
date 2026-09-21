import React, { useEffect, useRef, useState } from 'react';
import { recalculateDiff, getDiffResult, getLabels } from './api/catalog.api';
import { CatalogDiffGrid } from './components/CatalogDiffGrid';
import './catalogDiff.css';

const POLL_INTERVAL_MS = 2000;

export function CatalogDiffPage() {
  const [labels, setLabels] = useState([]);
  const [labelId, setLabelId] = useState('');
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');
  const [rows, setRows] = useState([]);
  const [searchTrigger, setSearchTrigger] = useState(0);
  const fileInputRef = useRef();
  const pollRef = useRef(null);

  useEffect(() => {
    getLabels().then(setLabels).catch(() => setLabels([]));
    return () => clearInterval(pollRef.current);
  }, []);

  const pollForResult = (taskId) => {
    pollRef.current = setInterval(async () => {
      try {
        const res = await getDiffResult(taskId);
        if (!res.ready) return;

        clearInterval(pollRef.current);
        setUploading(false);

        if (res.status === 'FAILURE') {
          setMessage('❌ Ошибка при пересчёте: ' + (res.error || 'неизвестная ошибка'));
          return;
        }

        const diffRows = res.result?.diff || [];
        setRows(diffRows);
        setSearchTrigger((prev) => prev + 1);
        const totalTracks = res.result?.total_diff_rows ?? diffRows.length / 2;
        setMessage(
          totalTracks > 0
            ? `✅ Найдено изменённых треков: ${totalTracks}`
            : '✅ Изменений не найдено — каталог уже соответствует файлу'
        );
      } catch (err) {
        clearInterval(pollRef.current);
        setUploading(false);
        setMessage('❌ Ошибка при получении результата: ' + err.message);
      }
    }, POLL_INTERVAL_MS);
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    const file = fileInputRef.current?.files[0];
    if (!file || !labelId) {
      setMessage('Выберите лейбл и файл!');
      return;
    }

    clearInterval(pollRef.current);
    setRows([]);
    setUploading(true);
    setMessage('⏳ Файл загружается и сверяется с каталогом...');

    try {
      const res = await recalculateDiff(file, labelId);
      if (res.task_id) {
        pollForResult(res.task_id);
      } else {
        setUploading(false);
        setMessage('❌ Не удалось получить task_id');
      }
    } catch (err) {
      setUploading(false);
      setMessage('❌ Ошибка при загрузке: ' + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <div className="page-container">
      <h1 className="page-title">Проверка изменений каталога</h1>

      <form onSubmit={handleUpload} className="action-section">
        <div className="form-group">
          <label className="form-label">Лейбл:</label>
          <select value={labelId} onChange={(e) => setLabelId(e.target.value)} className="form-control" disabled={uploading}>
            <option value="">Выберите лейбл</option>
            {labels.map((l) => (
              <option key={l.id} value={l.id}>{l.name}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Файл (.xlsx, .csv):</label>
          <input type="file" ref={fileInputRef} accept=".xlsx,.csv" disabled={uploading} className="form-control" />
        </div>
        <div className="form-group">
          <button type="submit" disabled={uploading || !labelId} className="btn btn-primary">
            {uploading ? 'Загрузка...' : 'Загрузить'}
          </button>
        </div>
      </form>

      {message && (
        <div className={`alert-message ${message.includes('❌') ? 'error' : 'success'}`}>
          {message}
        </div>
      )}

      {rows.length > 0 && (
        <div style={{ height: '600px', marginTop: '1rem' }}>
          <CatalogDiffGrid rows={rows} searchTrigger={searchTrigger} />
        </div>
      )}
    </div>
  );
}
