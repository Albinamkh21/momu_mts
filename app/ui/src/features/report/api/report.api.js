import { httpClient } from '../../../api/httpClient';

export const getPartners = async () => {
  const { data } = await httpClient.get('/v1/report/partners');
  return data;
};

export const getRightCategories = async () => {
  const { data } = await httpClient.get('/v1/report/right_categories');
  return data;
};

export const getRightUsageTypes = async () => {
  const { data } = await httpClient.get('/v1/report/right_usage_types');
  return data;
};

export const getLabels = async () => {
  const { data } = await httpClient.get('/v1/report/labels');
  return data;
};

export const uploadReport = async (formData) => {
  // use plain axios call to allow multipart/form-data
  const { data } = await httpClient.post('/v1/report/get_report_data', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

export const createReport = async (partnerId, year, monthFrom, monthTo, rightCategoryId, rightUsageTypeId, labelIds) => {
  const formData = new FormData();
  formData.append('partner_id', partnerId);
  formData.append('year', year);
  formData.append('month_from', monthFrom);
  formData.append('month_to', monthTo);
  formData.append('right_category_id', rightCategoryId);
  formData.append('right_usage_type_id', rightUsageTypeId);
  formData.append('label_ids', labelIds || '');
  
  const { data } = await httpClient.post('/v1/report/create_report', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};
