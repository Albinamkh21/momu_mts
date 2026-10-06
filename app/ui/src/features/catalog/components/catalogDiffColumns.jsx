import React from 'react';

const ROW_TYPE_LABELS = { old: 'Было', new: 'Стало' };

// Подсвечивает ячейку, если это поле попало в changed_fields строки
const changedCellClass = (field) => (params) =>
  !!params.data?.changed_fields?.includes(field);

const diffColumn = (field, headerName, extra = {}) => ({
  field,
  headerName,
  sortable: false,
  cellClassRules: { 'diff-cell-changed': changedCellClass(field) },
  ...extra,
});

export const getCatalogDiffColumns = () => [
  {
    field: 'row_type',
    headerName: '',
    width: 90,
    pinned: 'left',
    sortable: false,
    filter: false,
    cellRenderer: (params) => {
      if (!params.data) return null;
      const label = ROW_TYPE_LABELS[params.value] || params.value;
      return <span className={`diff-row-badge diff-row-badge--${params.value}`}>{label}</span>;
    },
  },
  diffColumn('track_id', 'ID трека', { pinned: 'left', width: 100 }),
  diffColumn('right_id', 'Right ID', { width: 110 }),
  diffColumn('isrc', 'ISRC', { width: 140 }),
  diffColumn('upc', 'UPC', { width: 130 }),
  diffColumn('track_name', 'Название трека', { flex: 1.4, minWidth: 180 }),
  diffColumn('genre_name', 'Жанр', { width: 120 }),
  diffColumn('album_name', 'Альбом', { flex: 1 }),
  diffColumn('album_single', 'Альбом/Сингл', { width: 120 }),
  diffColumn('track_number', '№ трека', { width: 100 }),
  diffColumn('artist_name', 'Исполнитель', { flex: 1 }),
  diffColumn('track_artist_name', 'Артист трека', { flex: 1 }),
  diffColumn('composer', 'Композитор', { flex: 1 }),
  diffColumn('lyricist', 'Автор текста', { flex: 1 }),
  diffColumn('authors', 'Авторы', { flex: 1 }),
  diffColumn('explicit', 'Explicit', { width: 100 }),
  diffColumn('duration', 'Длительность', { width: 120 }),
  diffColumn('label_name', 'Лейбл', { width: 140 }),
  diffColumn('author_right_int', 'Автор. право INT', { width: 140 }),
  diffColumn('author_right_mob', 'Автор. право MOB', { width: 140 }),
  diffColumn('author_right_pub', 'Автор. право PUB', { width: 140 }),
  diffColumn('ar_label_treaty_number', 'Правообладатель (авт.)', { flex: 1 }),
  diffColumn('related_right_id_int', 'Смежное право INT', { width: 140 }),
  diffColumn('related_right_id_mob', 'Смежное право MOB', { width: 140 }),
  diffColumn('related_right_id_pub', 'Смежное право PUB', { width: 140 }),
  diffColumn('rr_label_treaty_number', 'Правообладатель (смежн.)', { flex: 1 }),
];

export const getCatalogDeletedColumns = () => [
  {
    field: 'diff_type',
    headerName: '',
    width: 100,
    pinned: 'left',
    sortable: false,
    filter: false,
    cellRenderer: () => {
      // Используем тот же класс, что и для "Было", чтобы бейдж был красным/серым
      return <span className="diff-row-badge diff-row-badge--old">Удалён</span>;
    },
  },
  diffColumn('id', 'ID трека', { pinned: 'left', width: 100 }),
  diffColumn('isrc', 'ISRC', { width: 110 }),
  diffColumn('label_own_code', 'Код лейбла', { flex: 1 }),
  diffColumn('title', 'Название трека', { flex: 1.4, minWidth: 180 }),
  
];
