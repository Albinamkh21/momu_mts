import React, { useEffect, useState } from 'react';
import { getPartners, getRightCategories, getRightUsageTypes, uploadReport } from './api/report.api';
import { useTaskLogs } from '../../hooks/useTaskLogs';
import TaskLogsPanel from '../../components/TaskLogsPanel';

export function ReportPage() {
  const [partners, setPartners] = useState([]);
  const [categories, setCategories] = useState([]);
  const [usageTypes, setUsageTypes] = useState([]);

  const [form, setForm] = useState({
    partner_id: '',
    right_category_id: '',
    right_usage_type_id: '',
    month: new Date().getMonth() + 1,
    year: new Date().getFullYear(),
    group_data: true,
  });
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState('');
  const [activeTaskId, setActiveTaskId] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const { logs, setLogs } = useTaskLogs(activeTaskId);

  useEffect(() => {
    (async () => {
      try {
        const p = await getPartners();
        const c = await getRightCategories();
        const u = await getRightUsageTypes();
        setPartners(p || []);
        setCategories(c || []);
        setUsageTypes(u || []);
      } catch (err) {
        console.error(err);
      }
    })();
  }, []);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((s) => ({ ...s, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setMessage('Выберите файл');
      return;
    }

    setSubmitting(true);

    const fd = new FormData();
    fd.append('file', file);
    fd.append('partner_id', form.partner_id);
    fd.append('right_category_id', form.right_category_id);
    fd.append('right_usage_type_id', form.right_usage_type_id);
    fd.append('month', form.month);
    fd.append('year', form.year);
    fd.append('group_data', form.group_data ? 'true' : 'false');

    try {
      setMessage('Отправка...');
      const result = await uploadReport(fd);
      if (result.task_id) {
        setActiveTaskId(result.task_id);
        setLogs([]);
        setMessage('⚙️ Файл отправлен, формирование в фоне. Логи появятся ниже...');
      } else {
        setMessage(result.message || 'Запущено');
        setSubmitting(false);
      }
    } catch (err) {
      console.error(err);
      setMessage(err?.response?.data?.detail || 'Ошибка при отправке');
      setSubmitting(false);
    }
  };

  // Re-enable submit when logs indicate completion (success or error)
  useEffect(() => {
    if (!activeTaskId || logs.length === 0) return;
    const lastLog = logs[logs.length - 1];
    if (!lastLog || !lastLog.message) return;
    const m = lastLog.message;
    if (m.includes('✅') || m.includes('❌') || m.includes('Пайплайн завершён') || m.includes('Пайплайн завершён успешно')) {
      setSubmitting(false);
    }
  }, [logs, activeTaskId]);

  return (
    <div className="page-container">
      <h2 className="page-title">Загрузка отчёта</h2>

      <form onSubmit={handleSubmit} className="action-section">
        <div className="form-group">
          <label className="form-label">Партнёр</label>
          <select name="partner_id" value={form.partner_id} onChange={handleChange} required className="form-control">
            <option value="">-- выберите --</option>
            {partners.map(p => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Категория прав</label>
          <select name="right_category_id" value={form.right_category_id} onChange={handleChange} required className="form-control">
            <option value="">-- выберите --</option>
            {categories.map(c => (
              <option key={c.id} value={c.id}>{c.label || c.name}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Тип использования</label>
          <select name="right_usage_type_id" value={form.right_usage_type_id} onChange={handleChange} required className="form-control">
            <option value="">-- выберите --</option>
            {usageTypes.map(u => (
              <option key={u.id} value={u.id}>{u.label || u.code}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Месяц</label>
          <input name="month" type="number" min="1" max="12" value={form.month} onChange={handleChange} required className="form-control" />
        </div>

        <div className="form-group">
          <label className="form-label">Год</label>
          <input name="year" type="number" value={form.year} onChange={handleChange} required className="form-control" />
        </div>

        <div className="form-group">
          <label className="form-label">Группировать данные</label>
          <input name="group_data" type="checkbox" checked={form.group_data} onChange={handleChange} />
        </div>

        <div className="form-group">
          <label className="form-label">Файл отчёта (.xlsx или .csv)</label>
          <input type="file" accept=".xlsx,.csv" onChange={(e) => setFile(e.target.files[0])} required className="form-control" />
        </div>

        <div className="form-group">
          <button type="submit" className="btn btn-primary" disabled={submitting}>{submitting ? 'Отправка...' : 'Отправить'}</button>
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
        onClose={() => { setActiveTaskId(null); setLogs([]); }}
      />
    </div>
  );
}

export default ReportPage;
