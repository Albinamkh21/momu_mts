import React, { useEffect, useState } from 'react';
import { getPartners, getRightCategories, getRightUsageTypes, uploadReport } from './api/report.api';

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
      setMessage(result.message || 'Запущено');
    } catch (err) {
      console.error(err);
      setMessage(err?.response?.data?.detail || 'Ошибка при отправке');
    }
  };

  return (
    <div>
      <h2>Загрузка отчёта</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label>Партнёр</label>
          <select name="partner_id" value={form.partner_id} onChange={handleChange} required>
            <option value="">-- выберите --</option>
            {partners.map(p => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label>Категория прав</label>
          <select name="right_category_id" value={form.right_category_id} onChange={handleChange} required>
            <option value="">-- выберите --</option>
            {categories.map(c => (
              <option key={c.id} value={c.id}>{c.label || c.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label>Тип использования</label>
          <select name="right_usage_type_id" value={form.right_usage_type_id} onChange={handleChange} required>
            <option value="">-- выберите --</option>
            {usageTypes.map(u => (
              <option key={u.id} value={u.id}>{u.label || u.code}</option>
            ))}
          </select>
        </div>

        <div>
          <label>Месяц</label>
          <input name="month" type="number" min="1" max="12" value={form.month} onChange={handleChange} required />
        </div>

        <div>
          <label>Год</label>
          <input name="year" type="number" value={form.year} onChange={handleChange} required />
        </div>

        <div>
          <label>Группировать данные</label>
          <input name="group_data" type="checkbox" checked={form.group_data} onChange={handleChange} />
        </div>

        <div>
          <label>Файл отчёта (.xlsx или .csv)</label>
          <input type="file" accept=".xlsx,.csv" onChange={(e) => setFile(e.target.files[0])} required />
        </div>

        <div>
          <button type="submit">Отправить</button>
        </div>
      </form>
      {message && <div style={{marginTop:10}}>{message}</div>}
    </div>
  );
}

export default ReportPage;
