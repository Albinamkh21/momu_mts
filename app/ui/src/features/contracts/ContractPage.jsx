import React, { useState, useEffect } from 'react';
import { useContracts } from './hooks/useContracts';
import { ContractGrid } from './components/ContractGrid';
import { CrudPageLayout } from '../../components/shared/CrudPageLayout';
import { getContractFilterFields } from './components/contractFilterFields';
import { ContractForm } from './editor/ContractForm';
import { deleteContract } from './api/contracts.api';
import { getRightHolders } from '../rightHolders/api/rightHolders.api';
import './contracts.css';

const STORAGE_KEY = 'contracts_filters';

const getInitialFilters = () => {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    try {
      return JSON.parse(saved);
    } catch {
      return { search: '', status: '', direction_type: '', rights_holder_id: '' };
    }
  }
  return { search: '', status: '', direction_type: '', rights_holder_id: '' };
};

export const ContractPage = ({ onViewRightHolder }) => {
  const { loading, fetchContractsData } = useContracts();
  const [filters, setFilters] = useState(getInitialFilters);
  const [searchTrigger, setSearchTrigger] = useState(0);
  const [rightHolders, setRightHolders] = useState([]);
  const [editorState, setEditorState] = useState(null);
  const [actionError, setActionError] = useState('');

  // Load right holders for filter dropdown (API limit ≤ 500)
  useEffect(() => {
    getRightHolders({})
      .then((data) => setRightHolders(data.items))
      .catch(() => setRightHolders([]));
  }, []);

  const handleSearch = () => {
    if (!loading) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
      setSearchTrigger((prev) => prev + 1);
    }
  };

  const handleFiltersChange = (newFilters) => {
    setFilters(newFilters);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newFilters));
  };

  const openNewEditor = () => setEditorState({ contractId: null, mode: 'create' });
  const openViewEditor = (contractId) => setEditorState({ contractId, mode: 'view' });
  const openEditEditor = (contractId) => setEditorState({ contractId, mode: 'edit' });
  const closeEditor = () => setEditorState(null);

  const handleEditorDone = () => {
    closeEditor();
    setSearchTrigger((prev) => prev + 1);
  };

  const handleDelete = async (contractId) => {
    setActionError('');
    try {
      await deleteContract(contractId);
      setSearchTrigger((prev) => prev + 1);
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Не удалось удалить договор.');
    }
  };

  return (
    <CrudPageLayout
      className="contracts-page"
      filterFields={getContractFilterFields(rightHolders)}
      filters={filters}
      onFiltersChange={handleFiltersChange}
      onSearch={handleSearch}
      loading={loading}
      addButton={{ label: 'Новый договор', onClick: openNewEditor }}
      editorSlot={editorState && (
        <div className="contract-editor-inline">
          <ContractForm
            contractId={editorState.contractId}
            mode={editorState.mode}
            onDone={handleEditorDone}
            onCancel={closeEditor}
            onSwitchToEdit={() => setEditorState({ contractId: editorState.contractId, mode: 'edit' })}
          />
        </div>
      )}
      error={actionError}
    >
      <ContractGrid
        fetchContracts={fetchContractsData}
        filters={filters}
        searchTrigger={searchTrigger}
        onView={openViewEditor}
        onEdit={openEditEditor}
        onDelete={handleDelete}
        onViewRightHolder={onViewRightHolder}
      />
    </CrudPageLayout>
  );
};
