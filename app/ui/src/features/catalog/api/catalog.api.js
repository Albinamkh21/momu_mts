  import { httpClient } from '../../../api/httpClient';

  export const uploadCatalogV2 = async (file, labelId) => {

    const formData = new FormData();
    formData.append('file', file);
    formData.append('label_id', labelId);

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

  export const getUsers = async () => {
    const { data } = await httpClient.get('/v1/users'); 
    return data;
  };

  // Пересчёт diff (сверка staging-файла с боевым каталогом)
  export const recalculateDiff = async (file, label_id, isAdditionalData = true) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('label_id', label_id);
    formData.append('is_additional_data', isAdditionalData);
    const { data } = await httpClient.post('/v1/catalog_v2/recalculate_diff', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  };

  // Результат задачи пересчёта diff (опрашивается по task_id до готовности)
  export const getDiffResult = async (taskId) => {
    const { data } = await httpClient.get(`/v1/catalog_v2/diff_result/${taskId}`);
    return data;
  };
  

export const updateCatalog = async (labelId) => {
  const params = new URLSearchParams();
  params.append('label_id', parseInt(labelId));
  
  const { data } = await httpClient.post('/v1/catalog_v2/save_catalog_diff', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data;
};

export const getCatalogDiff = async (labelId) => {
  // Параметр передается прямо в URL (Path Parameter), поэтому query params не нужны
  const { data } = await httpClient.get(`/v1/catalog_v2/get_catalog_diff/${labelId}`);
  return data; // Вернет { message, task_id, filename }
};

// Удаление текущей загрузки (незасинхронизированного diff) по лейблу
export const deleteCatalogDiff = async (labelId) => {
  const params = new URLSearchParams();
  params.append('label_id', parseInt(labelId));
  const { data } = await httpClient.post('/v1/catalog_v2/delete_catalog_diff', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data;
};

// Получение удалённых треков по лейблу
export const getCatalogDeleted = async (labelId) => {
  const { data } = await httpClient.get(`/v1/catalog_v2/get_catalog_deleted/${labelId}`);
  return data;
};

// Единая выгрузка каталога в файл (CSV): type = 'changed' | 'deleted'
export const exportCatalog = async (labelId, type) => {
  return httpClient.get(`/v1/catalog_v2/export_catalog/${labelId}`, {
    params: { type },
    responseType: 'blob',
  });
};

export const updateViews = async (labelId) => {
  const params = new URLSearchParams();
  params.append('label_id', parseInt(labelId));
  const { data } = await httpClient.post('/v1/catalog_v2/update_views', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data;
};

