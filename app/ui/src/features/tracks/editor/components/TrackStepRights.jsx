import React, { useEffect, useState } from 'react';
import {
  getRightHoldersRef,
  getRightCategoriesRef,
  getRightUsageTypesRef,
} from '../api/drafts.api';

const emptyRight = () => ({
  _key: Math.random().toString(36).slice(2),
  right_holder_id: '',
  right_category_id: '',
  right_usage_type_id: '',
  contract_id: null,
  share_percentage: '',
  region_id: null,
});

/**
 * Searchable select: shows selected option name, on focus opens a filtered
 * dropdown list. Uses onMouseDown so the blur fires after selection.
 */
function SearchableSelect({ options, value, onChange, placeholder }) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);

  const selectedOption = options.find((o) => String(o.id) === String(value));
  const displayValue = isOpen ? query : (selectedOption ? selectedOption.name : '');

  const filtered = query
    ? options.filter((o) => o.name.toLowerCase().includes(query.toLowerCase()))
    : options;

  const handleFocus = () => {
    setQuery('');
    setIsOpen(true);
  };

  const handleChange = (e) => {
    setQuery(e.target.value);
    setIsOpen(true);
  };

  const handleSelect = (id) => {
    onChange(id);
    setIsOpen(false);
    setQuery('');
  };

  const handleBlur = () => {
    setTimeout(() => {
      setIsOpen(false);
      setQuery('');
    }, 150);
  };

  return (
    <div style={{ position: 'relative' }}>
      <input
        className="form-input"
        type="text"
        value={displayValue}
        onChange={handleChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        placeholder={placeholder || '— выберите —'}
      />
      {isOpen && (
        <ul className="person-search-dropdown">
          <li className="person-search-item" onMouseDown={() => handleSelect('')}>
            — выберите —
          </li>
          {filtered.map((o) => (
            <li
              key={o.id}
              className="person-search-item"
              onMouseDown={() => handleSelect(o.id)}
            >
              {o.name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * Step 4 – Rights: assign share percentages per right holder / category / usage type.
 */
export function TrackStepRights({ data, onChange }) {
  const rights = data.rights || [];
  const [holders, setHolders] = useState([]);
  const [categories, setCategories] = useState([]);
  const [usageTypes, setUsageTypes] = useState([]);

  useEffect(() => {
    getRightHoldersRef().then(setHolders).catch(() => setHolders([]));
    getRightCategoriesRef().then(setCategories).catch(() => setCategories([]));
    getRightUsageTypesRef().then(setUsageTypes).catch(() => setUsageTypes([]));
  }, []);

  const update = (list) => onChange({ rights: list });

  const addRow = () => update([...rights, emptyRight()]);

  const removeRow = (idx) => update(rights.filter((_, i) => i !== idx));

  const setField = (idx, field, value) =>
    update(rights.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));

  // Share percentage is capped at 100% per (right_category_id, right_usage_type_id)
  // combination — NOT across the whole track. A track can have several categories
  // and usage types, each independently summing up to 100%.
  const groupKey = (r) => `${r.right_category_id}_${r.right_usage_type_id}`;

  const groupTotals = rights.reduce((acc, r) => {
    if (r.right_category_id && r.right_usage_type_id) {
      const key = groupKey(r);
      acc[key] = (acc[key] || 0) + (parseFloat(r.share_percentage) || 0);
    }
    return acc;
  }, {});

  const grandTotal = rights.reduce(
    (acc, r) => acc + (parseFloat(r.share_percentage) || 0),
    0
  );

  const categoryName = (id) => categories.find((c) => String(c.id) === String(id))?.name || id;
  const usageTypeName = (id) => {
    const u = usageTypes.find((u) => String(u.id) === String(id));
    return u ? (u.name || u.code) : id;
  };

  const hasOverLimitGroup = Object.values(groupTotals).some((t) => t > 100);

  // Normalise usageTypes for SearchableSelect (needs .name)
  const usageTypeOptions = usageTypes.map((u) => ({ ...u, name: u.name || u.code }));

  return (
    <div className="wizard-step">
      <h3>Шаг 4 — Права на трек</h3>

      {rights.length === 0 && (
        <p style={{ color: '#888' }}>Добавьте строки прав.</p>
      )}

      <table className="rights-table">
        <thead>
          <tr>
            <th>Правообладатель</th>
            <th>Категория прав</th>
            <th>Тип использования</th>
            <th>Доля, %</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rights.map((r, idx) => {
            const rowGroupTotal = r.right_category_id && r.right_usage_type_id
              ? groupTotals[groupKey(r)]
              : null;
            return (
              <tr key={r._key || idx}>
                <td>
                  <SearchableSelect
                    options={holders}
                    value={r.right_holder_id}
                    onChange={(id) =>
                      setField(idx, 'right_holder_id', id !== '' ? Number(id) : '')
                    }
                    placeholder="Поиск правообладателя..."
                  />
                </td>
                <td>
                  <select
                    className="form-input"
                    value={r.right_category_id}
                    onChange={(e) =>
                      setField(idx, 'right_category_id', e.target.value ? Number(e.target.value) : '')
                    }
                  >
                    <option value="">— выберите —</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </td>
                <td>
                  <select
                    className="form-input"
                    value={r.right_usage_type_id}
                    onChange={(e) =>
                      setField(idx, 'right_usage_type_id', e.target.value ? Number(e.target.value) : '')
                    }
                  >
                    <option value="">— выберите —</option>
                    {usageTypeOptions.map((u) => (
                      <option key={u.id} value={u.id}>{u.name}</option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    className="form-input"
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    value={r.share_percentage}
                    onChange={(e) => setField(idx, 'share_percentage', e.target.value)}
                    placeholder="0.00"
                    style={{ width: '80px' }}
                  />
                  {rowGroupTotal != null && (
                    <div
                      style={{
                        fontSize: '0.7rem',
                        color: rowGroupTotal > 100 ? 'red' : '#888',
                      }}
                    >
                      по группе: {rowGroupTotal.toFixed(2)}%
                      {rowGroupTotal > 100 && ' ⚠'}
                    </div>
                  )}
                </td>
                <td>
                  <button
                    type="button"
                    className="btn-sm btn-danger"
                    onClick={() => removeRow(idx)}
                  >
                    ✕
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
        <button type="button" className="btn-add" onClick={addRow}>
          + Добавить строку
        </button>
        <span style={{ fontWeight: 'bold', color: hasOverLimitGroup ? 'red' : 'inherit' }}>
          Всего по треку: {grandTotal.toFixed(2)} %
        </span>
      </div>

      {Object.keys(groupTotals).length > 0 && (
        <div style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
          {Object.entries(groupTotals).map(([key, total]) => {
            const [catId, usageId] = key.split('_');
            return (
              <div key={key} style={{ color: total > 100 ? 'red' : '#555' }}>
                {categoryName(catId)} / {usageTypeName(usageId)}: {total.toFixed(2)} %
                {total > 100 && ' ⚠ превышение 100% по этой группе'}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
