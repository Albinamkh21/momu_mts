import React, { useEffect, useRef, useState } from 'react';
// ДОБАВЛЕНО: импорт getCatalogDiff
import { recalculateDiff, getDiffResult, getLabels, updateCatalog, getCatalogDiff } from './api/catalog.api';
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

  const handleSaveCatalogDiff = async () => {
    // Проверяем, что labelId заполнен (не пустая строка и не null/undefined)
    if (!labelId) {
      setMessage('❌ Ошибка: не выбран лейбл');
      return;
    }

    setUploading(true);
    setMessage('⏳ Обновление данных из каталога...');

    try {
      // Передаем значение labelId из state
      await updateCatalog(labelId);
      setMessage('✅ Данные успешно обновлены из каталога');
    } catch (err) {
      setMessage('❌ Ошибка при обновлении: ' + (err.response?.data?.detail || err.message));
    } finally {
      setUploading(false);
    }
  };

  const handleGetCatalogDiff = async () => {
    if (!labelId) {
      setMessage('❌ Ошибка: не выбран лейбл');
      return;
    }

    setUploading(true);
    setMessage('⏳ Получение изменений каталога...');
    // Очищаем текущую таблицу перед новым запросом
    setRows([]);

    try {
      const response = await getCatalogDiff(labelId);
      const taskId = response.task_id;
      
      // Используем polling для получения результата асинхронной задачи
      const pollInterval = setInterval(async () => {
        try {
          const res = await getDiffResult(taskId);
          if (!res.ready) return;

          clearInterval(pollInterval);
          setUploading(false);

          if (res.status === 'FAILURE') {
            setMessage('❌ Ошибка при получении изменений: ' + (res.error || 'неизвестная ошибка'));
            return;
          }

          const diffRows = res.result?.diff || [];
          setRows(diffRows);
          setSearchTrigger((prev) => prev + 1);
          const totalTracks = res.result?.total_diff_rows ?? diffRows.length / 2;
          setMessage(
            totalTracks > 0
              ? `✅ Успешно получены изменения. Изменённых треков: ${totalTracks}`
              : '✅ Активных изменений (в статусе PROCESSING) для данного лейбла не найдено.'
          );
        } catch (err) {
          clearInterval(pollInterval);
          setUploading(false);
          setMessage('❌ Ошибка при получении результата: ' + err.message);
        }
      }, POLL_INTERVAL_MS);
    } catch (err) {
      setUploading(false);
      setMessage('❌ Ошибка при запуске получения изменений: ' + (err.response?.data?.detail || err.message));
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

      <div className="action-section">
        <button onClick={handleSaveCatalogDiff} disabled={uploading} className="btn btn-primary">
          {uploading ? 'Обновление...' : 'Обновить данные из каталога'}
        </button>
      </div>
      <div className="action-section">
        <button onClick={handleGetCatalogDiff} disabled={uploading} className="btn btn-primary">
          {uploading ? 'Получение...' : 'Получить изменения каталога'}
        </button>
      </div>

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