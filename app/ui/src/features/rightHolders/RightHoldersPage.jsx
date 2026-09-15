import React, { useEffect, useState } from 'react';
import { useRightHolders } from './hooks/useRightHolders';
import { RightHolderGrid } from './components/RightHolderGrid';
import { CrudPageLayout } from '../../components/shared/CrudPageLayout';
import { getRightHolderFilterFields } from './components/rightHolderFilterFields';
import { RightHolderForm } from './editor/RightHolderForm';
import { deleteRightHolder } from './api/rightHolders.api';
import './rightHolders.css';

const STORAGE_KEY = 'right_holders_filters';

const getInitialFilters = () => {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    try {
      return JSON.parse(saved);
    } catch {
      return { search: '', alias: '', type: '', label_id: '' };
    }
  }
  return { search: '', alias: '', type: '', label_id: '' };
};

export const RightHoldersPage = ({ initialViewId }) => {
  const { loading, labels, fetchRightHoldersData } = useRightHolders();
  const [filters, setFilters] = useState(getInitialFilters);
  const [searchTrigger, setSearchTrigger] = useState(0);
  // null = closed, { rightHolderId, mode: 'create' | 'view' | 'edit' } otherwise
  const [editorState, setEditorState] = useState(null);
  const [actionError, setActionError] = useState('');

  const openNewEditor = () => setEditorState({ rightHolderId: null, mode: 'create' });
  const openViewEditor = (rightHolderId) => setEditorState({ rightHolderId, mode: 'view' });
  const openEditEditor = (rightHolderId) => setEditorState({ rightHolderId, mode: 'edit' });
  const closeEditor = () => setEditorState(null);

  // Открываем ПО в режиме просмотра, если сюда перешли по ссылке из другого модуля (например, из Договоров)
  useEffect(() => {
    if (initialViewId) {
      openViewEditor(initialViewId);
    }
  }, [initialViewId]);

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

  const handleEditorDone = () => {
    closeEditor();
    setSearchTrigger((prev) => prev + 1);
  };

  const handleDelete = async (rightHolderId) => {
    setActionError('');
    try {
      await deleteRightHolder(rightHolderId);
      setSearchTrigger((prev) => prev + 1);
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Не удалось удалить правообладателя.');
    }
  };

  return (
    <CrudPageLayout
      className="right-holders-page"
      filterFields={getRightHolderFilterFields(labels)}
      filters={filters}
      onFiltersChange={handleFiltersChange}
      onSearch={handleSearch}
      loading={loading}
      addButton={{ label: 'Новый правообладатель', onClick: openNewEditor }}
      editorSlot={editorState && (
        <div className="right-holder-editor-inline">
          <RightHolderForm
            rightHolderId={editorState.rightHolderId}
            mode={editorState.mode}
            onDone={handleEditorDone}
            onCancel={closeEditor}
            onSwitchToEdit={() => setEditorState({ rightHolderId: editorState.rightHolderId, mode: 'edit' })}
          />
        </div>
      )}
      error={actionError}
    >
      <RightHolderGrid
        fetchRightHolders={fetchRightHoldersData}
        filters={filters}
        searchTrigger={searchTrigger}
        onView={openViewEditor}
        onEdit={openEditEditor}
        onDelete={handleDelete}
      />
    </CrudPageLayout>
  );
};
