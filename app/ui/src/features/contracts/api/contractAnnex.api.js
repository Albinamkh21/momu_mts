import { httpClient } from '../../../api/httpClient';

// ContractAnnex (приложения к договору) — всегда существуют в связке с Contract,
// поэтому все маршруты вложены в /v1/contracts/{contractId}/annexes.

export const getContractAnnexes = async (contractId, params) => {
  const { data } = await httpClient.get(`/v1/contracts/${contractId}/annexes`, { params });
  return data; // { items, total }
};

export const getContractAnnexDetail = async (contractId, annexId) => {
  const { data } = await httpClient.get(`/v1/contracts/${contractId}/annexes/${annexId}`);
  return data;
};

export const createContractAnnex = async (contractId, payload) => {
  const { data } = await httpClient.post(`/v1/contracts/${contractId}/annexes`, payload);
  return data;
};

export const updateContractAnnex = async (contractId, annexId, payload) => {
  const { data } = await httpClient.put(`/v1/contracts/${contractId}/annexes/${annexId}`, payload);
  return data;
};

export const deleteContractAnnex = async (contractId, annexId) => {
  await httpClient.delete(`/v1/contracts/${contractId}/annexes/${annexId}`);
};

// ContractAnnexItem (строки табличной части приложения — произведения/авторы)

export const addAnnexItem = async (contractId, annexId, payload) => {
  const { data } = await httpClient.post(
    `/v1/contracts/${contractId}/annexes/${annexId}/items`,
    payload
  );
  return data;
};

export const updateAnnexItem = async (contractId, annexId, itemId, payload) => {
  const { data } = await httpClient.put(
    `/v1/contracts/${contractId}/annexes/${annexId}/items/${itemId}`,
    payload
  );
  return data;
};

export const deleteAnnexItem = async (contractId, annexId, itemId) => {
  await httpClient.delete(`/v1/contracts/${contractId}/annexes/${annexId}/items/${itemId}`);
};
