import React, { useEffect, useState } from 'react';
import { getPartners, getRightCategories, getRightUsageTypes, getLabels, createReport } from './api/report.api';
import { useTaskLogs } from '../../hooks/useTaskLogs';
import TaskLogsPanel from '../../components/TaskLogsPanel';

export function CreateReportPage() {
  const [partners, setPartners] = useState([]);
  const [categories, setCategories] = useState([]);
  const [usageTypes, setUsageTypes] = useState([]);
  const [labels, setLabels] = useState([]);

  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;

  const [form, setForm] = useState({
    partner_id: '',
    year: currentYear,
    month_from: 1,
    month_to: currentMonth,
    right_category_id: '',
    right_usage_type_id: '',
  });

  const [selectedLabelIds, setSelectedLabelIds] = useState([]);

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
        const l = await getLabels();
        setPartners(p || []);
        setCategories(c || []);
        setUsageTypes(u || []);
        setLabels(l || []);
      } catch (err) {
        console.error(err);
        setMessage('Ошибка при загрузке справочников');
      }
    })();
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((s) => ({ ...s, [name]: name === 'year' || name === 'month_from' || name === 'month_to' ? parseInt(value, 10) : value }));
  };

  const handleLabelChange = (e) => {
    const selected = Array.from(e.target.selectedOptions, option => parseInt(option.value, 10));
    setSelectedLabelIds(selected);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!form.right_category_id || !form.right_usage_type_id) {
      setMessage('Выберите категорию прав и тип использования');
      return;
    }

    if (form.month_from > form.month_to) {
      setMessage('Начальный месяц не может быть больше конечного');
      return;
    }

    setSubmitting(true);

    try {
      setMessage('Запуск создания отчёта...');
      const result = await createReport(
        form.partner_id,
        form.year,
        form.month_from,
        form.month_to,
        form.right_category_id,
        form.right_usage_type_id,
        selectedLabelIds.length > 0 ? selectedLabelIds.join(',') : ''
      );

      if (result.task_id) {
        setActiveTaskId(result.task_id);
        setLogs([]);
        setMessage('⚙️ Задача запущена, формирование в фоне. Логи появятся ниже...');
      } else {
        setMessage(result.message || 'Задача запущена');
        setSubmitting(false);
      }
    } catch (err) {
      console.error(err);
      setMessage(err?.response?.data?.detail || 'Ошибка при создании отчёта');
      setSubmitting(false);
    }
  };

  // Re-enable submit when logs indicate completion
  useEffect(() => {
    if (!activeTaskId || logs.length === 0) return;
    const lastLog = logs[logs.length - 1];
    if (!lastLog || !lastLog.message) return;
    const m = lastLog.message;
    if (m.includes('✅') || m.includes('❌') || m.includes('завершён') || m.includes('завершена')) {
      setSubmitting(false);
    }
  }, [logs, activeTaskId]);

  return (
    <div className="page-container">
      <h2 className="page-title">Создание отчёта</h2>

      <form onSubmit={handleSubmit} className="action-section">
        <div className="form-group">
          <label className="form-label">Партнёр (опционально)</label>
          <select name="partner_id" value={form.partner_id} onChange={handleChange} className="form-control">
            <option value="">-- выберите --</option>
            {partners.map(p => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Год</label>
          <input
            name="year"
            type="number"
            value={form.year}
            onChange={handleChange}
            required
            className="form-control"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Месяц от</label>
          <input
            name="month_from"
            type="number"
            min="1"
            max="12"
            value={form.month_from}
            onChange={handleChange}
            required
            className="form-control"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Месяц до</label>
          <input
            name="month_to"
            type="number"
            min="1"
            max="12"
            value={form.month_to}
            onChange={handleChange}
            required
            className="form-control"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Категория прав</label>
          <select
            name="right_category_id"
            value={form.right_category_id}
            onChange={handleChange}
            required
            className="form-control"
          >
            <option value="">-- выберите --</option>
            {categories.map(c => (
              <option key={c.id} value={c.id}>{c.label || c.name}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Тип использования</label>
          <select
            name="right_usage_type_id"
            value={form.right_usage_type_id}
            onChange={handleChange}
            required
            className="form-control"
          >
            <option value="">-- выберите --</option>
            {usageTypes.map(u => (
              <option key={u.id} value={u.id}>{u.label || u.code}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Лейблы (опционально)</label>
          <select
            multiple
            value={selectedLabelIds.map(String)}
            onChange={handleLabelChange}
            className="form-control"
          >
            {labels.map(l => (
              <option key={l.id} value={l.id}>{l.label}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? 'Создание...' : 'Создать отчёт'}
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
        onClose={() => { setActiveTaskId(null); setLogs([]); }}
      />
    </div>
  );
}

export default CreateReportPage;
