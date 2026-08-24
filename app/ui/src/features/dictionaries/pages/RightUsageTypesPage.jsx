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

export function RightUsageTypesPage() {
  return (
    <DictionaryBuilder
      endpointKey="right_usage_types"
      title="Справочник Типов Использования Прав"
      columns={columns}
      formFields={formFields}
    />
  );
}
