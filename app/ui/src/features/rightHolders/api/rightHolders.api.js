import { httpClient } from '../../../api/httpClient';

export const getRightHolders = async (params) => {
  const { data } = await httpClient.get('/v1/rights-holders', { params });
  return data; // { items, total }
};

export const getRightHolderDetail = async (id) => {
  const { data } = await httpClient.get(`/v1/rights-holders/${id}`);
  return data;
};

export const createRightHolder = async (payload) => {
  const { data } = await httpClient.post('/v1/rights-holders', payload);
  return data;
};

export const updateRightHolder = async (id, payload) => {
  const { data } = await httpClient.put(`/v1/rights-holders/${id}`, payload);
  return data;
};

export const deleteRightHolder = async (id) => {
  await httpClient.delete(`/v1/rights-holders/${id}`);
};

export const getLabels = async () => {
  const { data } = await httpClient.get('/labels');
  return data;
};
