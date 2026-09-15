import React, { useEffect, useRef, useState } from 'react';
import { RightHolderForm } from '../../rightHolders/editor/RightHolderForm';
import { getRightHolders } from '../../rightHolders/api/rightHolders.api';

const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_RESULTS_LIMIT = 20;

/**
 * Autocomplete for selecting or creating a RightHolder.
 * Searches RightHolder.name (server-side) as the user types and shows matches
 * directly under the input. Reuses RightHolderForm from rightHolders module
 * to avoid code duplication when creating a new one.
 */
export const RightHolderSelector = ({
  selectedRightHolderId,
  selectedRightHolderName = '',
  onSelect,
  onRightHolderCreated,
  readOnly = false,
}) => {
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [query, setQuery] = useState(selectedRightHolderName);
  const [results, setResults] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const debounceRef = useRef(null);

  // Синхронизируем поле ввода с внешним значением (загрузка договора, создание ПО)
  useEffect(() => {
    setQuery(selectedRightHolderName || '');
  }, [selectedRightHolderName]);

  const runSearch = (text) => {
    setIsSearching(true);
    getRightHolders({ search: text || undefined, limit: SEARCH_RESULTS_LIMIT })
      .then((data) => setResults(data.items || []))
      .catch(() => setResults([]))
      .finally(() => setIsSearching(false));
  };

  const handleInputChange = (e) => {
    const value = e.target.value;
    setQuery(value);
    setIsOpen(true);
    if (!value.trim()) {
      // Значение очищено — сбрасываем выбор, пока не выберут ПО из списка заново
      onSelect(null);
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runSearch(value), SEARCH_DEBOUNCE_MS);
  };

  const handleFocus = () => {
    setIsOpen(true);
    runSearch(query);
  };

  const handleBlur = () => {
    // Небольшая задержка, чтобы клик по пункту списка успел сработать раньше закрытия
    setTimeout(() => setIsOpen(false), 150);
  };

  const handlePick = (rh) => {
    setQuery(rh.name);
    setIsOpen(false);
    onSelect({ id: rh.id, name: rh.name });
  };

  const handleCreateDone = (createdRightHolder) => {
    setIsCreatingNew(false);
    if (createdRightHolder) {
      setQuery(createdRightHolder.name);
      onSelect({ id: createdRightHolder.id, name: createdRightHolder.name });
    }
    if (onRightHolderCreated) {
      onRightHolderCreated(createdRightHolder);
    }
  };

  const handleCancel = () => {
    setIsCreatingNew(false);
  };

  return (
    <div className="right-holder-selector">
      <div className="selector-group">
        <label className="form-label">Правообладатель *</label>
        <div className="right-holder-selector__row">
          <div className="right-holder-selector__combobox">
            <input
              type="text"
              className="form-control right-holder-selector__select"
              placeholder="Начните вводить название/имя..."
              value={query}
              onChange={handleInputChange}
              onFocus={handleFocus}
              onBlur={handleBlur}
              disabled={readOnly || isCreatingNew}
              autoComplete="off"
            />
            {isOpen && !readOnly && !isCreatingNew && (
              <ul className="right-holder-selector__dropdown">
                {isSearching && (
                  <li className="right-holder-selector__dropdown-item right-holder-selector__dropdown-item--muted">
                    Поиск...
                  </li>
                )}
                {!isSearching && results.length === 0 && (
                  <li className="right-holder-selector__dropdown-item right-holder-selector__dropdown-item--muted">
                    Ничего не найдено
                  </li>
                )}
                {!isSearching && results.map((rh) => (
                  <li
                    key={rh.id}
                    className="right-holder-selector__dropdown-item"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => handlePick(rh)}
                  >
                    {rh.name}
                    {rh.id === selectedRightHolderId && ' ✓'}
                  </li>
                ))}
              </ul>
            )}
          </div>
          {!readOnly && (
            <button
              type="button"
              className="btn-search right-holder-selector__add-btn"
              onClick={() => setIsCreatingNew(!isCreatingNew)}
              disabled={isCreatingNew}
              style={{ background: '#999' }}
            >
              {isCreatingNew ? '✕ Отмена' : 'Добавить ПО'}
            </button>
          )}
        </div>
      </div>

      {isCreatingNew && (
        <div style={{ marginTop: '16px', padding: '16px', backgroundColor: '#f5f5f5', borderRadius: '6px' }}>
          <h4 style={{ marginTop: 0, marginBottom: '12px' }}>Создание нового правообладателя</h4>
          <RightHolderForm
            rightHolderId={null}
            mode="create"
            onDone={handleCreateDone}
            onCancel={handleCancel}
          />
        </div>
      )}
    </div>
  );
};
