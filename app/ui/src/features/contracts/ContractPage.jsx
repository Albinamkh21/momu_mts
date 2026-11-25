import React, { useState, useEffect, useRef } from 'react';
import { useContracts } from './hooks/useContracts';
import { ContractGrid } from './components/ContractGrid';
import { CrudPageLayout } from '../../components/shared/CrudPageLayout';
import { getContractFilterFields } from './components/contractFilterFields';
import { ContractForm } from './editor/ContractForm';
import { deleteContract, openContractFolder, exportContractsExcel, downloadContract, downloadExport, uploadContractFile } from './api/contracts.api';
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

export const ContractPage = ({ onViewRightHolder, onViewAnnexes }) => {
  const { loading, fetchContractsData } = useContracts();
  const [filters, setFilters] = useState(getInitialFilters);
  const [searchTrigger, setSearchTrigger] = useState(0);
  const [rightHolders, setRightHolders] = useState([]);
  const [editorState, setEditorState] = useState(null);
  const [actionError, setActionError] = useState('');
  const [downloadFilename, setDownloadFilename] = useState(null);
  const [logs, setLogs] = useState([]);
  const [activeTaskId, setActiveTaskId] = useState(null);
  const [exportStatusMessage, setExportStatusMessage] = useState('');
  const fileInputRef = useRef(null);
  const [uploadingContractId, setUploadingContractId] = useState(null);


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
  const [exporting, setExporting] = useState(false);

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

  const handleOpenFolder = (contract) => {
    setActionError('');
    if (!contract.file_path || !contract.file_name) {
      setActionError('Файл или папка договора не найдены в данных.');
      return;
    }
    // Формируем ссылку на бэкенд (порт 8000), а не на Vite (5173)
    const webPath = contract.file_path.replace(/^\/docs/, '/files');
    const fileUrl = `http://localhost:8000${webPath}/${contract.file_name}`;
    
    // Открываем в новом окне
    window.open(fileUrl, '_blank');
  };

  const handleDownloadContract = async (contract) => {
  setActionError('');
  try {
    const blob = await downloadContract(contract.id);
    
    // Создаем временный URL для полученного блоба
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    
    // Указываем имя файла (можно взять из данных контракта или заголовоков)
    link.download = contract.file_name || `Договор_${contract.contract_number}.docx`;
    
    document.body.appendChild(link);
    link.click();
    
    // Очищаем за собой
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    setActionError(err.response?.data?.detail || 'Не удалось скачать файл договора.');
  }
};

  const handleExportExcel = async () => {
      if (exporting) return;
      setActionError('');
      setExportStatusMessage('');
      setDownloadFilename(null);
      setExporting(true);

      try {
        const res = await exportContractsExcel(filters);
        if (res?.filename) {
          setDownloadFilename(res.filename);
        }
        setExportStatusMessage(
          res?.rows_exported != null
            ? `Выгрузка завершена (строк: ${res.rows_exported})`
            : 'Выгрузка завершена'
        );
      } catch (err) {
        setActionError(err.response?.data?.detail || 'Не удалось выполнить выгрузку в Excel.');
      } finally {
        setExporting(false);
      }
    };

  const handleDownloadExport = async (filename) => {
    if (!filename) return;
    setActionError('');
    try {
      await downloadExport(filename);
    } catch {
      setActionError('Не удалось скачать файл выгрузки.');
    }
  };

  const handleOpenUploadDialog = (contract) => {
    const contractId = typeof contract === 'object' ? contract?.id : contract;
    if (!contractId) return;
    setActionError('');
    setUploadingContractId(contractId);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
      fileInputRef.current.click();
    }
  };

  const handleFileSelected = async (e) => {
    const file = e.target.files?.[0];
    const contractId = uploadingContractId;
    setUploadingContractId(null);

    if (!file || !contractId) return;

    setActionError('');
    try {
      await uploadContractFile(contractId, file);
      setSearchTrigger((prev) => prev + 1);
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Не удалось загрузить файл в папку договора.');
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
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
      exportButton={{
          label: exporting ? 'Выгрузка...' : 'Выгрузить в Excel',
          onClick: handleExportExcel,
          disabled: exporting || loading,
        }}
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

      <input
        ref={fileInputRef}
        type="file"
        style={{ display: 'none' }}
        onChange={handleFileSelected}
      />

      <ContractGrid
        fetchContracts={fetchContractsData}
        filters={filters}
        searchTrigger={searchTrigger}
        onView={openViewEditor}
        onEdit={openEditEditor}
        onDelete={handleDelete}
        onViewRightHolder={onViewRightHolder}
        onViewAnnexes={onViewAnnexes}
        onOpenFolder={handleOpenFolder}
        onDownloadContract={handleDownloadContract}
        onUploadFile={handleOpenUploadDialog}
      />
     {exportStatusMessage && (
      <div className="page-notice page-notice--success" role="status">
        <span>{exportStatusMessage}</span>
        {downloadFilename && !exporting && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => handleDownloadExport(downloadFilename)}
          >
            Скачать файл
          </button>
        )}
      </div>
    )}


    </CrudPageLayout>
  );
};
