import React from 'react';
import { DictionaryBuilder } from '../DictionaryBuilder';

const columns = [
  { key: 'id', label: 'ID' },
  { key: 'name', label: 'Название' },
  { key: 'code', label: 'Код' },
];

const formFields = [
  { key: 'name', label: 'Название', required: true },
  { key: 'code', label: 'Код' },
];

const searchFields = [
  { key: 'name', label: 'Название' },
  { key: 'code', label: 'Код' },
];

export function LabelsPage() {
  return (
    <DictionaryBuilder
      endpointKey="labels"
      title="Справочник Лейблов"
      columns={columns}
      formFields={formFields}
      searchFields={searchFields}
    />
  );
}
