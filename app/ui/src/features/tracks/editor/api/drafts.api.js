import { httpClient } from '../../../../api/httpClient';

const BASE = '/drafts';
const REF = '/drafts-ref';

// ── Draft lifecycle ──────────────────────────────────────────────────────────

export const createDraft = async (userId = null) => {
  const { data } = await httpClient.post(BASE, { user_id: userId });
  return data; // { id, status, payload }
};

export const createDraftFromTrack = async (trackId) => {
  const { data } = await httpClient.post(`${BASE}/from-track/${trackId}`);
  return data; // { id, status, payload, track_id }
};

export const getDraft = async (draftId) => {
  const { data } = await httpClient.get(`${BASE}/${draftId}`);
  return data;
};

export const patchDraft = async (draftId, stepPatch) => {
  const { data } = await httpClient.patch(`${BASE}/${draftId}`, stepPatch);
  return data;
};

export const activateDraft = async (draftId) => {
  const { data } = await httpClient.post(`${BASE}/${draftId}/activate`);
  return data; // { track_id, message }
};

// ── Reference data ───────────────────────────────────────────────────────────

export const getLabelsRef = async () => {
  const { data } = await httpClient.get('/labels');
  return data;
};

export const getReleasesRef = async () => {
  const { data } = await httpClient.get(`${REF}/releases`);
  return data;
};

export const getRightHoldersRef = async () => {
  const { data } = await httpClient.get(`${REF}/right-holders`);
  return data;
};

export const getRightCategoriesRef = async () => {
  const { data } = await httpClient.get(`${REF}/right-categories`);
  return data;
};

export const getRightUsageTypesRef = async () => {
  const { data } = await httpClient.get(`${REF}/right-usage-types`);
  return data;
};

export const searchPersonsRef = async (q = '') => {
  const { data } = await httpClient.get(`${REF}/persons`, { params: { q } });
  return data;
};
