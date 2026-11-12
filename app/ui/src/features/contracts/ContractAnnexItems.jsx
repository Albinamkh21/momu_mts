import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { DataGrid } from '../../components/shared/DataGrid';
import { getContractAnnexDetail, deleteAnnexItem } from './api/contractAnnex.api';
import { getAnnexItemColumns } from './components/annexItemColumns';
import { AnnexItemForm } from './editor/AnnexItemForm';

/**
 * Список произведений (ContractAnnexItem), относящихся к одному приложению
 * (ContractAnnex). Не является отдельной страницей — встраивается в
 * ContractAnnexPage при открытии конкретного приложения. Полностью владеет
 * CRUD произведений: добавление, редактирование, удаление строки.
 */
export const ContractAnnexItems = ({ contractId, annexId }) => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [reloadTrigger, setReloadTrigger] = useState(0);
  // null = закрыто, { item: null } = создание новой строки, { item } = редактирование
  const [editorState, setEditorState] = useState(null);
  const [actionError, setActionError] = useState('');

  useEffect(() => {
    if (!contractId || !annexId) return;
    setLoading(true);
    getContractAnnexDetail(contractId, annexId)
      .then((data) => setItems(data.items || []))
      .catch(() => setActionError('Не удалось загрузить произведения приложения.'))
      .finally(() => setLoading(false));
  }, [contractId, annexId, reloadTrigger]);

  const openAddForm = () => setEditorState({ item: null });
  const openEditForm = (item) => setEditorState({ item });
  const closeForm = () => setEditorState(null);

  const handleEditorDone = () => {
    closeForm();
    setReloadTrigger((prev) => prev + 1);
  };

  const handleDelete = async (itemId) => {
    setActionError('');
    try {
      await deleteAnnexItem(contractId, annexId, itemId);
      setReloadTrigger((prev) => prev + 1);
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Не удалось удалить произведение.');
    }
  };

  const columnDefs = useMemo(() => getAnnexItemColumns({ onEdit: openEditForm }), []);

  // Данные приложения уже загружены целиком выше — грид просто нарезает
  // локальный массив постранично, без отдельного списочного эндпоинта.
  const fetchRows = useCallback(
    async (_filters, limit, offset) => ({
      items: items.slice(offset, offset + limit),
      total: items.length,
    }),
    [items]
  );

  return (
    <div className="annex-items-section">
      <div className="annex-items-section__header">
        <h3 className="annex-items-section__title">Произведения</h3>
        <button type="button" className="btn-primary" onClick={openAddForm}>
          + Добавить произведение
        </button>
      </div>

      {actionError && <div className="wizard-error">{actionError}</div>}

      {editorState && (
        <div className="annex-item-form-inline">
          <AnnexItemForm
            contractId={contractId}
            annexId={annexId}
            item={editorState.item}
            onDone={handleEditorDone}
            onCancel={closeForm}
          />
        </div>
      )}

      <div className="annex-items-section__grid">
        {loading ? (
          <div className="loading-text">Загружаем произведения...</div>
        ) : (
          <DataGrid
            columnDefs={columnDefs}
            fetchRows={fetchRows}
            filters={{}}
            searchTrigger={reloadTrigger}
            deleteConfirm={{
              getMessage: (row) => `Удалить произведение "${row.track_title}"?`,
              onConfirm: (row) => handleDelete(row.id),
            }}
          />
        )}
      </div>
    </div>
  );
};
