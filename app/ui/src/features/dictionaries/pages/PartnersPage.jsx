import React from 'react';
import { DictionaryBuilder } from '../DictionaryBuilder';

const columns = [
  { key: 'id', label: 'ID' },
  { key: 'organization_name', label: 'Организация' },
  { key: 'service_name', label: 'Сервис' },
  { key: 'contract_number', label: '№ Договора' },
  { key: 'code', label: 'Код' },
];

const formFields = [
  { key: 'organization_name', label: 'Организация', required: true },
  { key: 'service_name', label: 'Сервис', required: true },
  { key: 'right_usage_type_id', label: 'ID Типа использования прав', type: 'number', required: true },
  { key: 'contract_number', label: '№ Договора' },
  { key: 'code', label: 'Код' },
  { key: 'note', label: 'Примечание', type: 'textarea' },
];

const searchFields = [
  { key: 'organization_name', label: 'Название' },
  { key: 'code', label: 'Код' },
];

export function PartnersPage() {
  return (
    <DictionaryBuilder
      endpointKey="partners"
      title="Справочник Партнёров"
      columns={columns}
      formFields={formFields}
      searchFields={searchFields}
    />
  );
}
