import { httpClient } from '../../../api/httpClient';

// ─── История отчётов (независимая вкладка) ───────────────────────────────────
// Все запросы к /v1/report/report реализованы через контроллер -> сервис ->
// репозиторий на бэкенде (см. app/api/v1/endpoints/reports.py,
// app/services/report_history_service.py, app/__crud/report_repository.py).

export const getReportHistory = async (params) => {
  // Возвращаем полный axios-ответ, чтобы прочитать заголовок X-Total-Count
  const response = await httpClient.get('/v1/report/report', { params });
  return response;
};

export const deleteReportHistory = async (ids) => {
  const { data } = await httpClient.delete('/v1/report/report', { data: { ids } });
  return data;
};

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
