export const RIGHT_HOLDER_TYPE_OPTIONS = [
  { value: 'INDIVIDUAL', label: 'Физ. лицо' },
  { value: 'COMPANY', label: 'Юр. лицо' },
  { value: 'IP', label: 'ИП' },
];

export const getRightHolderFilterFields = (labels) => [
  { key: 'search', label: 'Поиск', type: 'text', placeholder: 'Имя, псевдоним, ИИН/БИН...' },
  { key: 'alias', label: 'Псевдоним', type: 'text', placeholder: 'Псевдоним...' },
  {
    key: 'type',
    label: 'Тип',
    type: 'select',
    placeholder: 'Все типы',
    options: RIGHT_HOLDER_TYPE_OPTIONS,
  },
  {
    key: 'label_id',
    label: 'Лейбл',
    type: 'select',
    placeholder: 'Все лейблы',
    options: labels.map((l) => ({ value: l.id, label: l.name })),
  },
];
