import { httpClient } from '../../../api/httpClient';

export const getTracks = async (params) => {
  const response = await httpClient.get('/tracks', { params });
  return response;
};

export const getTrackDetail = async (id) => {
  const { data } = await httpClient.get(`/tracks/${id}`);
  
  return data;
};

export const getLabels = async () => {
  const { data } = await httpClient.get('/labels');
  return data;
};

export const getPerson = async (id) => {
  const { data } = await httpClient.get(`/persons/${id}`);
  return data;
};

export const updatePerson = async (id, fullName) => {
  const { data } = await httpClient.put(`/persons/${id}`, { full_name: fullName });
  return data;
};