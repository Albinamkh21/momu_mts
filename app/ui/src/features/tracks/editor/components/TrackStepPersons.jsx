import React, { useRef, useState } from 'react';
import { PersonCreateModal } from './modals/PersonCreateModal';
import { searchPersonsRef } from '../api/drafts.api';

const ROLES = [
  { value: 'artist_name', label: 'Исполнитель' },
  { value: 'composer', label: 'Композитор' },
  { value: 'lyricist', label: 'Автор текста' },
];

const emptyContributor = () => ({
  _key: Math.random().toString(36).slice(2),
  person_id: null,
  full_name: '',
  role: 'artist_name',
});

/**
 * Step 3 – Contributors: artists, composers, lyricists.
 * Each row holds a person (existing or new) and a role.
 */
export function TrackStepPersons({ data, onChange }) {
  const contributors = data.contributors || [];
  const [modalOpen, setModalOpen] = useState(false);
  const [editingIdx, setEditingIdx] = useState(null);
  // Search dropdown state per row: { [idx]: { results: [], open: false } }
  const [searches, setSearches] = useState({});
  const debounceTimers = useRef({});

  const update = (list) => onChange({ contributors: list });

  const addRow = (role) => {
    update([...contributors, { ...emptyContributor(), role }]);
  };

  const removeRow = (idx) => {
    update(contributors.filter((_, i) => i !== idx));
    setSearches((prev) => {
      const next = { ...prev };
      delete next[idx];
      return next;
    });
  };

  // Single-call update to avoid stale-closure double-setter bug
  const setRowFields = (idx, fields) => {
    update(
      contributors.map((c, i) => (i === idx ? { ...c, ...fields } : c))
    );
  };

  const handleNameChange = (idx, value) => {
    // Fix: combine both field updates in one call to avoid stale-closure revert
    setRowFields(idx, { full_name: value, person_id: null });

    if (debounceTimers.current[idx]) clearTimeout(debounceTimers.current[idx]);

    if (value.trim().length >= 2) {
      debounceTimers.current[idx] = setTimeout(async () => {
        try {
          const results = await searchPersonsRef(value.trim());
          setSearches((prev) => ({ ...prev, [idx]: { results, open: true } }));
        } catch {
          setSearches((prev) => ({ ...prev, [idx]: { results: [], open: false } }));
        }
      }, 300);
    } else {
      setSearches((prev) => ({ ...prev, [idx]: { results: [], open: false } }));
    }
  };

  const selectExistingPerson = (idx, person) => {
    setRowFields(idx, { person_id: person.id, full_name: person.full_name });
    setSearches((prev) => ({ ...prev, [idx]: { results: [], open: false } }));
  };

  const closeDropdown = (idx) => {
    setTimeout(() => {
      setSearches((prev) => ({ ...prev, [idx]: { ...(prev[idx] || {}), open: false } }));
    }, 150);
  };

  const openCreateModal = (idx) => {
    setEditingIdx(idx);
    setModalOpen(true);
  };

  const handlePersonCreated = (person) => {
    if (editingIdx !== null) {
      setRowFields(editingIdx, { person_id: person.id, full_name: person.full_name });
    }
    setModalOpen(false);
    setEditingIdx(null);
  };

  return (
    <div className="wizard-step">
      <h3>Шаг 3 — Участники</h3>

      {contributors.length === 0 && (
        <p style={{ color: '#888' }}>Добавьте хотя бы одного участника.</p>
      )}

      <table className="contributors-table">
        <thead>
          <tr>
            <th>Роль</th>
            <th>Имя</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {contributors.map((c, idx) => {
            const search = searches[idx] || { results: [], open: false };
            return (
              <tr key={c._key || idx}>
                <td>
                  <select
                    className="form-input"
                    value={c.role}
                    onChange={(e) => setRowFields(idx, { role: e.target.value })}
                  >
                    {ROLES.map((r) => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                  </select>
                </td>
                <td style={{ position: 'relative' }}>
                  <input
                    className="form-input"
                    type="text"
                    value={c.full_name}
                    onChange={(e) => handleNameChange(idx, e.target.value)}
                    onBlur={() => closeDropdown(idx)}
                    placeholder="Начните вводить имя..."
                  />
                  {c.person_id && (
                    <span style={{ fontSize: '0.75rem', color: '#0a0' }}>
                      {' '}✓ ID: {c.person_id}
                    </span>
                  )}
                  {search.open && search.results.length > 0 && (
                    <ul className="person-search-dropdown">
                      {search.results.map((p) => (
                        <li
                          key={p.id}
                          className="person-search-item"
                          onMouseDown={() => selectExistingPerson(idx, p)}
                        >
                          {p.full_name}
                        </li>
                      ))}
                    </ul>
                  )}
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button
                    type="button"
                    className="btn-sm"
                    onClick={() => openCreateModal(idx)}
                    title="Создать нового автора"
                  >
                    + Новый
                  </button>
                  <button
                    type="button"
                    className="btn-sm btn-danger"
                    onClick={() => removeRow(idx)}
                    title="Удалить строку"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="add-buttons">
        {ROLES.map((r) => (
          <button
            key={r.value}
            type="button"
            className="btn-add"
            onClick={() => addRow(r.value)}
          >
            + {r.label}
          </button>
        ))}
      </div>

      {modalOpen && (
        <PersonCreateModal
          onCreated={handlePersonCreated}
          onClose={() => { setModalOpen(false); setEditingIdx(null); }}
        />
      )}
    </div>
  );
}
