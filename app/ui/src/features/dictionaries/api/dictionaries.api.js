import { httpClient } from '../../../api/httpClient';

// Generic API client for the Dynamic CRUD / Generic Admin Engine.
// Works against GET/POST/PUT/DELETE /v1/dictionaries/{endpointKey}[/id]

export const getDictionaryList = async (endpointKey, { search, limit = 50, offset = 0 } = {}) => {
  const { data } = await httpClient.get(`/v1/dictionaries/${endpointKey}`, {
    params: { search: search || undefined, limit, offset },
  });
  return data; // { items, total, limit, offset }
};

export const getDictionaryItem = async (endpointKey, id) => {
  const { data } = await httpClient.get(`/v1/dictionaries/${endpointKey}/${id}`);
  return data;
};

export const createDictionaryItem = async (endpointKey, payload) => {
  const { data } = await httpClient.post(`/v1/dictionaries/${endpointKey}`, payload);
  return data;
};

export const updateDictionaryItem = async (endpointKey, id, payload) => {
  const { data } = await httpClient.put(`/v1/dictionaries/${endpointKey}/${id}`, payload);
  return data;
};

export const deleteDictionaryItem = async (endpointKey, id) => {
  await httpClient.delete(`/v1/dictionaries/${endpointKey}/${id}`);
};
