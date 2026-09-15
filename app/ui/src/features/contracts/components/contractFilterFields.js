export const CONTRACT_STATUS_OPTIONS = [
  { value: 'DRAFT', label: 'Черновик' },
  { value: 'ACTIVE', label: 'Активный' },
  { value: 'TERMINATED', label: 'Прекращен' },
];

export const CONTRACT_DIRECTION_TYPE_OPTIONS = [
  { value: 'DIRECT_ARTIST', label: 'Прямой артист' },
  { value: 'LABEL_CATALOG', label: 'Каталог лейбла' },
];

export const getContractFilterFields = (rightHolders) => [
  { key: 'search', label: 'Поиск', type: 'text', placeholder: 'Номер договора...' },
  {
    key: 'status',
    label: 'Статус',
    type: 'select',
    placeholder: 'Все статусы',
    options: CONTRACT_STATUS_OPTIONS,
  },
  {
    key: 'direction_type',
    label: 'Тип направления',
    type: 'select',
    placeholder: 'Все типы',
    options: CONTRACT_DIRECTION_TYPE_OPTIONS,
  },
  {
    key: 'rights_holder_id',
    label: 'Правообладатель',
    type: 'select',
    placeholder: 'Все правообладатели',
    options: (rightHolders || []).map((rh) => ({ value: rh.id, label: rh.name })),
  },
];
