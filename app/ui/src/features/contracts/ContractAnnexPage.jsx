import React, { useEffect, useState } from 'react';
import { useContractAnnexes } from './hooks/useContractAnnexes';
import { ContractAnnexGrid } from './components/ContractAnnexGrid';
import { CrudPageLayout } from '../../components/shared/CrudPageLayout';
import { getContractAnnexFilterFields } from './components/contractAnnexFilterFields';
import { ContractAnnexForm } from './editor/ContractAnnexForm';
import { ContractAnnexItems } from './ContractAnnexItems';
import { getContractDetail } from './api/contracts.api';
import { deleteContractAnnex } from './api/contractAnnex.api';
import './contracts.css';

/**
 * Список приложений (ContractAnnex) конкретного договора. Приложение не может
 * существовать без договора, поэтому страница всегда открывается с contractId
 * (переход из ContractPage). При клике на приложение открывается само
 * приложение (шапка + таблица произведений — ContractAnnexItems).
 */
export const ContractAnnexPage = ({ contractId, onBack }) => {
  const { loading, fetchContractAnnexesData } = useContractAnnexes(contractId);
  const [contract, setContract] = useState(null);
  const [filters, setFilters] = useState({ search: '' });
  const [searchTrigger, setSearchTrigger] = useState(0);
  // null = закрыто, { annexId: null, mode: 'create' } | { annexId, mode: 'view' | 'edit' }
  const [editorState, setEditorState] = useState(null);
  const [actionError, setActionError] = useState('');

  useEffect(() => {
    if (!contractId) return;
    getContractDetail(contractId)
      .then(setContract)
      .catch(() => setContract(null));
  }, [contractId]);

  const handleSearch = () => {
    if (!loading) setSearchTrigger((prev) => prev + 1);
  };

  const handleFiltersChange = (newFilters) => setFilters(newFilters);

  const openNewEditor = () => setEditorState({ annexId: null, mode: 'create' });
  const openViewEditor = (annexId) => setEditorState({ annexId, mode: 'view' });
  const openEditEditor = (annexId) => setEditorState({ annexId, mode: 'edit' });
  const closeEditor = () => setEditorState(null);

  // После создания приложения сразу открываем его в режиме просмотра, чтобы
  // можно было продолжить работу с произведениями (ContractAnnexItems).
  const handleEditorDone = (savedAnnex) => {
    if (editorState?.mode === 'create' && savedAnnex?.id) {
      setEditorState({ annexId: savedAnnex.id, mode: 'view' });
    } else {
      closeEditor();
    }
    setSearchTrigger((prev) => prev + 1);
  };

  const handleDelete = async (annexId) => {
    setActionError('');
    try {
      await deleteContractAnnex(contractId, annexId);
      if (editorState?.annexId === annexId) closeEditor();
      setSearchTrigger((prev) => prev + 1);
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Не удалось удалить приложение.');
    }
  };

  return (
    <div className="contract-annex-page">
      <button type="button" className="btn" onClick={onBack}>← Назад к договору</button>
      <h2 className="contract-annex-page__title">
        Приложения к договору {contract?.contract_number || ''}
      </h2>

      <CrudPageLayout
        className="contract-annexes-page"
        filterFields={getContractAnnexFilterFields()}
        filters={filters}
        onFiltersChange={handleFiltersChange}
        onSearch={handleSearch}
        loading={loading}
        addButton={{ label: 'Новое приложение', onClick: openNewEditor }}
        editorSlot={editorState && (
          <div className="contract-editor-inline">
            <ContractAnnexForm
              contractId={contractId}
              annexId={editorState.annexId}
              mode={editorState.mode}
              onDone={handleEditorDone}
              onCancel={closeEditor}
              onSwitchToEdit={() => setEditorState({ annexId: editorState.annexId, mode: 'edit' })}
            />
            {editorState.annexId && (editorState.mode === 'view' || editorState.mode === 'edit') && (
              <ContractAnnexItems contractId={contractId} annexId={editorState.annexId} />
            )}
          </div>
        )}
        error={actionError}
      >
        <ContractAnnexGrid
          fetchContractAnnexes={fetchContractAnnexesData}
          filters={filters}
          searchTrigger={searchTrigger}
          onView={openViewEditor}
          onEdit={openEditEditor}
          onDelete={handleDelete}
        />
      </CrudPageLayout>
    </div>
  );
};
