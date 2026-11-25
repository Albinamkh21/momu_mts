import { httpClient } from '../../../api/httpClient';

export const getContracts = async (params) => {
  const { data } = await httpClient.get('/v1/contracts', { params });
  return data; // { items, total }
};

export const getContractDetail = async (id) => {
  const { data } = await httpClient.get(`/v1/contracts/${id}`);
  return data;
};

export const createContract = async (payload) => {
  const { data } = await httpClient.post('/v1/contracts', payload);
  return data;
};

export const updateContract = async (id, payload) => {
  const { data } = await httpClient.put(`/v1/contracts/${id}`, payload);
  return data;
};

export const deleteContract = async (id) => {
  await httpClient.delete(`/v1/contracts/${id}`);
};

export const openContractFolder = async (id) => {
  const { data } = await httpClient.post(`/v1/contracts/${id}/open-folder`);
  return data;
};
export const downloadContract = async (id) => {
  const { data } = await httpClient.get(`/v1/contracts/${id}/download`, {
    responseType: 'blob',
  });
  return data;
};

export const exportContractsExcel = async (filters = {}) => {
  const params = {};
  
  if (filters.search && String(filters.search).trim()) {
    params.search = String(filters.search).trim();
  }
  if (filters.rights_holder_id && Number(filters.rights_holder_id) > 0) {
    params.rights_holder_id = Number(filters.rights_holder_id);
  }
  if (filters.status && String(filters.status).trim()) {
    params.status = filters.status;
  }
  if (filters.direction_type && String(filters.direction_type).trim()) {
    params.direction_type = filters.direction_type;
  }

  const { data } = await httpClient.post('/v1/contracts/export', null, { params });
  return data;
};

export const downloadExport = async (filename) => {
  // Очищаем от возможных путей, оставляем чистое имя файла
  const cleanName = String(filename).split('/').pop();
  const safeFilename = encodeURIComponent(cleanName);

  const response = await httpClient.get(`/v1/contracts/download_export/${safeFilename}`, {
    responseType: 'blob',
  });

  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', cleanName);

  document.body.appendChild(link);
  link.click();

  link.parentNode.removeChild(link);
  window.URL.revokeObjectURL(url);
};


export const uploadContractFile = async (contractId, file) => {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await httpClient.post(`/v1/contracts/${contractId}/upload-file`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};