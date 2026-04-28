import React, { useState, useRef, useEffect } from 'react';
import { uploadCatalogV2, downloadCatalog, deleteLabelData, getLabels } from './api/catalog.api';

export function CatalogPage() {
  const [uploading, setUploading] = useState(false);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [labelId, setLabelId] = useState('');
  const [labels, setLabels] = useState([]);
    const [users, setUsers] = useState([]);
    const [userId, setUserId] = useState('');
  const [message, setMessage] = useState('');
  const fileInputRef = useRef();

  useEffect(() => {
    getLabels().then(setLabels).catch(() => setLabels([]));
    // load users for upload picker
    fetch('/api/v1/users')
      .then(r => r.json())
      .then(setUsers)
      .catch(() => setUsers([]));
  }, []);

  const handleUpload = async (e) => {
    e.preventDefault();
    const file = fileInputRef.current.files[0];
    if (!file) return;
    setUploading(true);
    setMessage('');
    try {
      const res = await uploadCatalogV2(file, userId);
      setMessage(res.message || (res.data && res.data.message) || 'Файл загружен');
    } catch (err) {
      setMessage('Ошибка загрузки файла');
    } finally {
      setUploading(false);
    }
  };

  const handleDownload = async (e) => {
    e.preventDefault();
    setDownloadLoading(true);
    setMessage('');
    try {
      const res = await downloadCatalog(labelId);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'catalog_normalized.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      setMessage('Каталог экспортирован');
    } catch (err) {
      setMessage('Ошибка экспорта каталога');
    } finally {
      setDownloadLoading(false);
    }
  };

  const handleDelete = async (e) => {
    e.preventDefault();
    if (!labelId) {
      setMessage('Выберите лейбл для удаления');
      return;
    }
    setDeleteLoading(true);
    setMessage('');
    try {
      const res = await deleteLabelData(labelId);
      setMessage(res.data.message || 'Данные по лейблу удалены');
    } catch (err) {
      setMessage('Ошибка удаления данных по лейблу');
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 500, margin: '0 auto', padding: 24 }}>
      <h1>Catalog Management</h1>
      <form onSubmit={handleUpload} style={{ marginBottom: 24 }}>
        <label>Загрузить каталог (.xlsx, .csv): </label>
        <input type="file" ref={fileInputRef} accept=".xlsx,.csv" disabled={uploading} />
        <select value={userId} onChange={e => setUserId(e.target.value)} style={{ marginLeft: 8 }}>
          <option value="">Выберите пользователя</option>
          {users.map(u => (
            <option key={u.id} value={u.id}>{u.login}</option>
          ))}
        </select>
        <button type="submit" disabled={uploading} style={{ marginLeft: 8 }}>
          {uploading ? 'Загрузка...' : 'Загрузить'}
        </button>
      </form>
      <form onSubmit={handleDownload} style={{ marginBottom: 24 }}>
        <label>Экспортировать каталог (по лейблу): </label>
        <select value={labelId} onChange={e => setLabelId(e.target.value)} style={{ width: 200, marginLeft: 8 }}>
          <option value="">Все лейблы</option>
          {labels.map(l => (
            <option key={l.id} value={l.id}>{l.name}</option>
          ))}
        </select>
        <button type="submit" disabled={downloadLoading} style={{ marginLeft: 8 }}>
          {downloadLoading ? 'Экспорт...' : 'Экспортировать'}
        </button>
      </form>
      <form onSubmit={handleDelete} style={{ marginBottom: 24 }}>
        <label>Удалить данные по лейблу: </label>
        <select value={labelId} onChange={e => setLabelId(e.target.value)} style={{ width: 200, marginLeft: 8 }}>
          <option value="">Выберите лейбл</option>
          {labels.map(l => (
            <option key={l.id} value={l.id}>{l.name}</option>
          ))}
        </select>
        <button type="submit" disabled={deleteLoading || !labelId} style={{ marginLeft: 8 }}>
          {deleteLoading ? 'Удаление...' : 'Удалить'}
        </button>
      </form>
      {message && <div style={{ marginTop: 16, color: '#333' }}>{message}</div>}
    </div>
  );
}
