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
