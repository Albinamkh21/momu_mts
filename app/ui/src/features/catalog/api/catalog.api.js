import { httpClient } from '../../../api/httpClient';

// Upload catalog (v2)
export const uploadCatalogV2 = async (file, user_id) => {
  const formData = new FormData();
  formData.append('file', file);
  if (user_id) formData.append('user_id', user_id);
  const { data } = await httpClient.post('/v1/catalog_v2/upload_v2', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

// Download catalog
export const downloadCatalog = async (label_id) => {
  const payload = label_id ? { label_id: parseInt(label_id) } : {};
  console.log("DEBUG: downloadCatalog called with label_id:", label_id, "payload:", payload);
  const { data } = await httpClient.post('/v1/catalog/download', payload);
  return data;
};

export const downloadCatalogWithUsage = async (label_id, right_usage_type_id, export_format) => {
  const payload = {};
  if (label_id) payload.label_id = parseInt(label_id);
  if (right_usage_type_id) payload.right_usage_type_id = parseInt(right_usage_type_id);
  if (export_format) payload.export_format = export_format;
  console.log("DEBUG: downloadCatalogWithUsage payload:", payload);
  const { data } = await httpClient.post('/v1/catalog/download', payload);
  return data;
};

// Delete label data
export const deleteLabelData = async (label_id) => {
  const { data } = await httpClient.delete(`/v1/catalog/label/${label_id}`);
  return data;
};

export const getLabels = async () => {
  const { data } = await httpClient.get('/labels');
  return data;
};

export const getRightUsageTypes = async () => {
  const { data } = await httpClient.get('/v1/report/right_usage_types');
  return data;
};
