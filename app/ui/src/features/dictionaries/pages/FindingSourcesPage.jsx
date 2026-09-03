import React from 'react';
import { DictionaryBuilder } from '../DictionaryBuilder';

const columns = [
  { key: 'id', label: 'ID' },
  { key: 'code', label: 'Код' },
  { key: 'name', label: 'Название' },
  { key: 'description', label: 'Описание' },
];

const formFields = [
  { key: 'code', label: 'Код', required: true },
  { key: 'name', label: 'Название' },
  { key: 'description', label: 'Описание', type: 'textarea' },
];

const searchFields = [
  { key: 'name', label: 'Название' },
  { key: 'code', label: 'Код' },
];

export function FindingSourcesPage() {
  return (
    <DictionaryBuilder
      endpointKey="finding_sources"
      title="Справочник Источников Поиска"
      columns={columns}
      formFields={formFields}
      searchFields={searchFields}
    />
  );
}
