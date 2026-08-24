import React from 'react';
import { DictionaryBuilder } from '../DictionaryBuilder';

const columns = [
  { key: 'id', label: 'ID' },
  { key: 'name', label: 'Название' },
];

const formFields = [
  { key: 'name', label: 'Название', required: true },
];

export function RightCategoriesPage() {
  return (
    <DictionaryBuilder
      endpointKey="right_categories"
      title="Справочник Категорий Прав"
      columns={columns}
      formFields={formFields}
    />
  );
}
