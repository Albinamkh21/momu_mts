import React, { useEffect, useRef, useState } from 'react';
import {
  recalculateDiff,
  getDiffResult,
  getLabels,
  updateCatalog,
  getCatalogDiff,
  deleteCatalogDiff,
  downloadCatalogDiff,
  getCatalogDeleted,
} from './api/catalog.api';
import { CatalogDiffGrid } from './components/CatalogDiffGrid';
import { ConfirmModal } from '../../components/ConfirmModal';
import { useTaskLogs } from '../../hooks/useTaskLogs';
import TaskLogsPanel from '../../components/TaskLogsPanel';
import './catalogDiff.css';

const POLL_INTERVAL_MS = 2000;

export function CatalogDiffPage() {
  const [labels, setLabels] = useState([]);
  const [labelId, setLabelId] = useState('');
  // Единый флаг активного действия — какая именно кнопка сейчас выполняется
  const [actionLoading, setActionLoading] = useState(null);
  const [message, setMessage] = useState('');
  const [rows, setRows] = useState([]);
  const [searchTrigger, setSearchTrigger] = useState(0);
  const [isAdditionalData, setIsAdditionalData] = useState(false);
  const [confirmAdditionalOpen, setConfirmAdditionalOpen] = useState(false);
  const [pendingAdditionalValue, setPendingAdditionalValue] = useState(null);
  const [activeTaskId, setActiveTaskId] = useState(null);
  const fileInputRef = useRef();
  const pollRef = useRef(null);

  const { logs, setLogs } = useTaskLogs(activeTaskId);

  const busy = actionLoading !== null;

  useEffect(() => {
    getLabels().then(setLabels).catch(() => setLabels([]));
    return () => clearInterval(pollRef.current);
  }, []);

  // Единая точка обработки результата задачи: diff-задачи возвращают result.diff,
  // save/delete — только статистику, поэтому таблица очищается как устаревшая (п.6).
  const applyTaskResult = (res, emptyMessage) => {
    const diffRows = res.result?.diff;
    const stats = res.result?.stats;
    
    if (Array.isArray(diffRows)) {
      setRows(diffRows);
      setSearchTrigger((prev) => prev + 1);
      const totalTracks = res.result?.total_diff_rows ?? diffRows.length / 2;
      
      // Формируем сообщение со статистикой
      let message = totalTracks > 0
        ? `✅ Найдено изменённых треков: ${totalTracks}`
        : emptyMessage;
      
      // Добавляем детальную статистику если она есть
      if (stats && (stats.new_tracks > 0 || stats.existing_tracks > 0 || stats.modified_tracks > 0)) {
        message += ` | 📊 Статистика: новых треков: ${stats.new_tracks}, существующих: ${stats.existing_tracks}, изменённых: ${stats.modified_tracks}`;
      }
      
      setMessage(message);
    } else {
      setRows([]);
      setSearchTrigger((prev) => prev + 1);
      
      // Отображаем статистику даже если нет diff (например, при save/delete)
      if (stats && (stats.new_tracks > 0 || stats.existing_tracks > 0 || stats.modified_tracks > 0)) {
        setMessage(`✅ Операция выполнена успешно | 📊 Статистика: новых треков: ${stats.new_tracks}, существующих: ${stats.existing_tracks}, изменённых: ${stats.modified_tracks}`);
      } else {
        setMessage('✅ Операция выполнена успешно');
      }
    }
  };

  const runPolling = (taskId, emptyMessage) => {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await getDiffResult(taskId);
        if (!res.ready) return;

        clearInterval(pollRef.current);
        setActionLoading(null);

        if (res.status === 'FAILURE') {
          setMessage('❌ Ошибка: ' + (res.error || 'неизвестная ошибка'));
          return;
        }

        applyTaskResult(res, emptyMessage);
      } catch (err) {
        clearInterval(pollRef.current);
        setActionLoading(null);
        setMessage('❌ Ошибка при получении результата: ' + err.message);
      }
    }, POLL_INTERVAL_MS);
  };

  const startAction = (action) => {
    clearInterval(pollRef.current);
    setActionLoading(action);
    setLogs([]);
    setActiveTaskId(null);
  };

  const dispatchTask = async (promise, emptyMessage) => {
    try {
      const res = await promise;
      if (res.task_id) {
        setActiveTaskId(res.task_id);
        runPolling(res.task_id, emptyMessage);
      } else {
        setActionLoading(null);
        setMessage('❌ Не удалось получить task_id');
      }
    } catch (err) {
      setActionLoading(null);
      setMessage('❌ Ошибка: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    const file = fileInputRef.current?.files[0];
    if (!file || !labelId) {
      setMessage('Выберите лейбл и файл!');
      return;
    }

    startAction('upload');
    setRows([]);
    setMessage('⏳ Файл загружается и сверяется с каталогом...');

    await dispatchTask(
      recalculateDiff(file, labelId, isAdditionalData),
      '✅ Изменений не найдено — каталог уже соответствует файлу'
    );
  };

  const handleGetCatalogDiff = async () => {
    if (!labelId) {
      setMessage('❌ Ошибка: не выбран лейбл');
      return;
    }

    startAction('diff');
    setRows([]);
    setMessage('⏳ Получение изменений каталога...');

    await dispatchTask(
      getCatalogDiff(labelId),
      '✅ Активных изменений (в статусе PROCESSING) для данного лейбла не найдено.'
    );
  };

  const handleSaveCatalogDiff = async () => {
    if (!labelId) {
      setMessage('❌ Ошибка: не выбран лейбл');
      return;
    }

    startAction('save');
    setRows([]);
    setMessage('⏳ Сохранение загрузки...');

    await dispatchTask(updateCatalog(labelId), '✅ Сохранять было нечего.');
  };

  const handleDeleteCatalogDiff = async () => {
    if (!labelId) {
      setMessage('❌ Ошибка: не выбран лейбл');
      return;
    }

    startAction('delete');
    setRows([]);
    setMessage('⏳ Удаление загрузки...');

    await dispatchTask(deleteCatalogDiff(labelId), '✅ Удалять было нечего.');
  };

  const handleDownloadCatalogDiff = async () => {
    if (!labelId) {
      setMessage('❌ Ошибка: не выбран лейбл');
      return;
    }

    startAction('download');
    setRows([]);
    setMessage('⏳ Формирование файла...');

    await dispatchTask(downloadCatalogDiff(labelId), '✅ Данных для сохранения в файл не найдено.');
  };

  const handleGetCatalogDeleted = async () => {
    if (!labelId) {
      setMessage('❌ Ошибка: не выбран лейбл');
      return;
    }

    startAction('deleted');
    setRows([]);
    setMessage('⏳ Получение удалённых треков...');

    await dispatchTask(getCatalogDeleted(labelId), '✅ Удалённых треков не найдено.');
  };

  const handleAdditionalDataToggle = (e) => {
    if (e.target.checked) {
      // При выборе запрашиваем подтверждение
      setPendingAdditionalValue(true);
      setConfirmAdditionalOpen(true);
    } else {
      // При снятии галочки отключаем сразу без модалки
      setIsAdditionalData(false);
    }
  };

  const confirmAdditionalDataToggle = () => {
    setIsAdditionalData(pendingAdditionalValue);
    setConfirmAdditionalOpen(false);
    setPendingAdditionalValue(null);
  };

  const cancelAdditionalDataToggle = () => {
    setConfirmAdditionalOpen(false);
    setPendingAdditionalValue(null);
  };

  return (
    <div className="page-container catalog-diff-page">
      <h1 className="page-title">Проверка изменений каталога</h1>

      <form onSubmit={handleUpload} className="action-section">
        <div className="form-group">
          <label className="form-label">Лейбл:</label>
          <select value={labelId} onChange={(e) => setLabelId(e.target.value)} className="form-control" disabled={busy}>
            <option value="">Выберите лейбл</option>
            {labels.map((l) => (
              <option key={l.id} value={l.id}>{l.name}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Файл (.xlsx, .csv):</label>
          <input type="file" ref={fileInputRef} accept=".xlsx,.csv" disabled={busy} className="form-control" />
        </div>
        <div className="form-group">
          <label className="catalog-diff-checkbox">
            <input
              type="checkbox"
              checked={isAdditionalData}
              disabled={busy}
              onChange={handleAdditionalDataToggle}
            />
            Дополнительный файл по лейблу
          </label>
        </div>

        <div className="catalog-diff-actions">
          <button type="submit" disabled={busy || !labelId} className="btn btn-primary">
            {actionLoading === 'upload' ? 'Загрузка...' : 'Загрузить'}
          </button>
          <button type="button" onClick={handleGetCatalogDiff} disabled={busy || !labelId} className="btn btn-primary">
            {actionLoading === 'diff' ? 'Получение...' : 'Показать изменения'}
          </button>
          <button type="button" onClick={handleSaveCatalogDiff} disabled={busy || !labelId} className="btn btn-primary">
            {actionLoading === 'save' ? 'Сохранение...' : 'Сохранить загрузку'}
          </button>
          <button type="button" onClick={handleDeleteCatalogDiff} disabled={busy || !labelId} className="btn btn-danger">
            {actionLoading === 'delete' ? 'Удаление...' : 'Удалить загрузку'}
          </button>
        </div>
        <div className="catalog-diff-actions">
          <button type="button" onClick={handleDownloadCatalogDiff} disabled={busy || !labelId} className="btn btn-primary">
            {actionLoading === 'download' ? 'Формирование...' : 'Сохранить в файл'}
          </button>
          <button type="button" onClick={handleGetCatalogDeleted} disabled={busy || !labelId} className="btn btn-primary">
            {actionLoading === 'deleted' ? 'Получение...' : 'Показать удаленные треки'}
          </button>
        </div>
      </form>

      {message && (
        <div className={`alert-message ${message.includes('❌') ? 'error' : 'success'}`}>
          {message}
        </div>
      )}

      {rows.length > 0 && (

        <div className="catalog-diff-grid-wrap">
          <CatalogDiffGrid rows={rows} searchTrigger={searchTrigger} />
        </div>
      )}

      <TaskLogsPanel
        activeTaskId={activeTaskId}
        logs={logs}
        onClose={() => {
          setActiveTaskId(null);
          setLogs([]);
        }}
      />

      <ConfirmModal
        open={confirmAdditionalOpen}
        title="Подтверждение"
        message="Вы уверены? Данные будут добавлены к уже существующим."
        confirmLabel="Подтвердить"
        cancelLabel="Отмена"
        onConfirm={confirmAdditionalDataToggle}
        onCancel={cancelAdditionalDataToggle}
      />
    </div>
  );
}