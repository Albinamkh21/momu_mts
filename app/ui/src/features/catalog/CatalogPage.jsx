import React, { useState, useRef, useEffect } from 'react';
import { uploadCatalogV2, downloadCatalogWithUsage, deleteLabelData, getLabels, getRightUsageTypes } from './api/catalog.api';
import { useTaskLogs } from '../../hooks/useTaskLogs';
import TaskLogsPanel from '../../components/TaskLogsPanel';

export function CatalogPage() {
  const [uploading, setUploading] = useState(false);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [labelId, setLabelId] = useState('');
  const [labels, setLabels] = useState([]);
  const [usageTypes, setUsageTypes] = useState([]);
  const [users, setUsers] = useState([]);
  const [userId, setUserId] = useState('');
  const [rightUsageTypeId, setRightUsageTypeId] = useState('');
  const [exportFormat, setExportFormat] = useState('');
  const [message, setMessage] = useState('');
  const fileInputRef = useRef();
  const [activeTaskId, setActiveTaskId] = useState(null);

  const { logs, setLogs } = useTaskLogs(activeTaskId);

  useEffect(() => {
    getLabels().then(setLabels).catch(() => setLabels([]));
    getRightUsageTypes().then(setUsageTypes).catch(() => setUsageTypes([]));
    fetch('/api/v1/users').then(r => r.json()).then(setUsers).catch(() => setUsers([]));
  }, []);

  // --- Обработчик загрузки ---
  const handleUpload = async (e) => {
    e.preventDefault();
    const file = fileInputRef.current?.files[0];
    if (!file || !userId) {
      setMessage('Выберите файл и пользователя!');
      return;
    }

    setUploading(true);
    setMessage('⏳ Запуск загрузки...');
    setLogs([]);                  // очищаем старые логи
    setActiveTaskId(null);        // сбрасываем старый taskId

    try {
      const res = await uploadCatalogV2(file, userId);
      if (res.task_id) {
        setActiveTaskId(res.task_id);
        setMessage('⚙️ Файл загружается, обработка в фоне. Логи появятся ниже...');
      } else {
        // Если бэкенд не вернул task_id, считаем операцию синхронной
        setMessage('✅ Файл успешно загружен и обработан');
        fileInputRef.current.value = '';
        const freshLabels = await getLabels();
        setLabels(freshLabels);
        setUploading(false);
      }
    } catch (err) {
      setMessage('❌ Ошибка при загрузке: ' + (err.response?.data?.message || err.message));
      setUploading(false);
    }
    // Не снимаем uploading, если есть task_id – снимем по завершении задачи (см. эффект ниже)
  };

  // --- Обработчик выгрузки (скачивания) ---
  const handleDownload = async (e) => {
    e.preventDefault();
    setDownloadLoading(true);
    setMessage('⏳ Запуск генерации...');
    setLogs([]);
    setActiveTaskId(null);

    try {
      const res = await downloadCatalogWithUsage(labelId, rightUsageTypeId, exportFormat === '' ? null : exportFormat);
      if (res.task_id) {
        setActiveTaskId(res.task_id);
        setMessage('⚙️ Файл формируется. Логи ниже...');
      } else {
        setMessage('❌ Не удалось получить task_id');
        setDownloadLoading(false);
      }
    } catch (err) {
      setMessage('❌ Ошибка запуска: ' + err.message);
      setDownloadLoading(false);
    }
  };

  // --- Обработчик удаления ---
  const handleDelete = async (e) => {
    e.preventDefault();
    console.log('Запуск удаления для labelId:', labelId);
    if (!labelId) return;
    if (!window.confirm('Вы уверены, что хотите удалить ВСЕ данные по этому лейблу?')) return;

    setDeleteLoading(true);
    setMessage('⏳ Запуск удаления...');
    setLogs([]);
    setActiveTaskId(null);

    try {
      const res = await deleteLabelData(labelId);
      if (res.task_id) {
        setActiveTaskId(res.task_id);
        setMessage('🗑️ Удаление в фоне. Логи ниже...');
      } else {
        setMessage('✅ Данные удалены');
        const freshLabels = await getLabels();
        setLabels(freshLabels);
        setLabelId('');
        setDeleteLoading(false);
      }
    } catch (err) {
      setMessage('❌ Ошибка при удалении');
      setDeleteLoading(false);
    }
  };

  // --- Эффект для отслеживания завершения задачи (по последнему логу) ---
  useEffect(() => {
    if (!activeTaskId || logs.length === 0) return;
    const lastLog = logs[logs.length - 1];
    // Если последнее сообщение сигнализирует об успехе или ошибке – снимаем лоадер
    if (
      lastLog.message.includes('✅') ||
      lastLog.message.includes('❌') ||
      lastLog.message.includes('Файл сохранён') ||
      lastLog.message.includes('удалены')
    ) {
      // Сбросим соответствующий флаг загрузки в зависимости от операции
      // (можно анализировать по task_id, но проще сбросить все)
      setUploading(false);
      setDownloadLoading(false);
      setDeleteLoading(false);
      // Дополнительно обновим списки, если нужно
      if (lastLog.message.includes('удалены') || lastLog.message.includes('Файл сохранён')) {
        getLabels().then(setLabels).catch(() => setLabels([]));
      }
      if (lastLog.message.includes('загружен') || lastLog.message.includes('удалены')) {
        fileInputRef.current && (fileInputRef.current.value = '');
      }
    }
  }, [logs, activeTaskId]);

  // --- Вёрстка (без изменений, кроме консоли логов) ---
  return (
    <div className="page-container">
      <h1 className="page-title">Работа с каталогом</h1>

      <form onSubmit={handleUpload} className="action-section">
        <div className="form-group">
          <label className="form-label">Загрузить файл (.xlsx, .csv):</label>
          <input type="file" ref={fileInputRef} accept=".xlsx,.csv" disabled={uploading} className="form-control" />
        </div>
        <div className="form-group">
          <label className="form-label">Пользователь:</label>
          <select value={userId} onChange={e => setUserId(e.target.value)} className="form-control" disabled={uploading}>
            <option value="">Выберите владельца данных</option>
            {users.map(u => <option key={u.id} value={u.id}>{u.login}</option>)}
          </select>
          <button type="submit" disabled={uploading} className="btn btn-primary">
            {uploading ? 'Загрузка...' : 'Загрузить в базу'}
          </button>
        </div>
      </form>

      <hr className="divider" />

      <form onSubmit={handleDownload} className="action-section">
        <div className="form-group">
          <label className="form-label">Экспорт данных:</label>
          <select value={labelId} onChange={e => setLabelId(e.target.value)} className="form-control">
            <option value="">Все доступные лейблы</option>
            {labels.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Тип использования:</label>
          <select value={rightUsageTypeId} onChange={e => setRightUsageTypeId(e.target.value)} className="form-control">
          
            {usageTypes.map(u => <option key={u.id} value={u.id}>{u.label || u.code}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Формат выгрузки:</label>
          <select value={exportFormat} onChange={e => setExportFormat(e.target.value)} className="form-control">
            <option value="default">Основной формат (по умолчанию)</option>
            <option value="separate_by_rights">Отдельные каталоги по Авторские/Смежные</option>
            <option value="100plus100">100+100</option>
          </select>
        </div>
        <div className="form-group">
          <button type="submit" disabled={downloadLoading} className="btn btn-primary">
            {downloadLoading ? 'Сборка...' : 'Скачать Excel'}
          </button>
        </div>
      </form>

      <hr className="divider" />

      <form onSubmit={handleDelete} className="action-section">
        <div className="form-group">
          <label className="form-label">Очистка данных (Danger Zone):</label>
          <select value={labelId} onChange={e => setLabelId(e.target.value)} className="form-control">
            <option value="">Выберите лейбл для удаления</option>
            {labels.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
          <button type="submit" disabled={deleteLoading || !labelId} className="btn btn-danger">
            {deleteLoading ? 'Удаление...' : 'Удалить данные'}
          </button>
        </div>
      </form>

      {message && (
        <div className={`alert-message ${message.includes('❌') ? 'error' : 'success'}`}>
          {message}
        </div>
      )}

      <TaskLogsPanel
        activeTaskId={activeTaskId}
        logs={logs}
        onClose={() => {
          setActiveTaskId(null);
          setUploading(false);
          setDownloadLoading(false);
          setDeleteLoading(false);
          setLogs([]);
        }}
      />
    </div>
  );
}