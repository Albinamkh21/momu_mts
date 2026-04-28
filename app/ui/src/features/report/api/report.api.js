import { httpClient } from '../../../api/httpClient';

export const getPartners = async () => {
  const { data } = await httpClient.get('/report/partners');
  return data;
};

export const getRightCategories = async () => {
  const { data } = await httpClient.get('/report/right_categories');
  return data;
};

export const getRightUsageTypes = async () => {
  const { data } = await httpClient.get('/report/right_usage_types');
  return data;
};

export const uploadReport = async (formData) => {
  // use plain axios call to allow multipart/form-data
  const { data } = await httpClient.post('/report/get_report_data', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};
