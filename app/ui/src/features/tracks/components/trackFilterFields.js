export const getTrackFilterFields = (labels) => [
  { key: 'title', label: 'Название трека', type: 'text', placeholder: 'Название...' },
  { key: 'isrc', label: 'ISRC', type: 'text', placeholder: 'ISRC...' },
  { key: 'label_own_code', label: 'Код лейбла', type: 'text', placeholder: 'Код...' },
  { key: 'artist_name', label: 'Исполнитель (artist)', type: 'text', placeholder: 'Имя исполнителя...' },
  { key: 'author_name', label: 'Авторы (composer / lyricist)', type: 'text', placeholder: 'Имя автора...' },
  {
    key: 'label_id',
    label: 'Лейбл',
    type: 'select',
    placeholder: 'Все лейблы',
    options: labels.map((l) => ({ value: l.id, label: l.name })),
  },
];
