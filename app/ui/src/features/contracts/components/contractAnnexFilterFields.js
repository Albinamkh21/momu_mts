export const ANNEX_STATUS_OPTIONS = [
  { value: 'DRAFT', label: 'Черновик' },
  { value: 'PROCESSING', label: 'В обработке' },
  { value: 'PARSED', label: 'Обработано' },
  { value: 'FAILED', label: 'Ошибка' },
];

export const getContractAnnexFilterFields = () => [
  { key: 'search', label: 'Поиск', type: 'text', placeholder: 'Номер приложения...' },
];
