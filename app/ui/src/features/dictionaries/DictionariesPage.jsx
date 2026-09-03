import React from 'react';
import { DICTIONARIES } from './dictionariesConfig';

export function DictionariesPage({ activeKey }) {
  const active = DICTIONARIES.find((d) => d.key === activeKey) || DICTIONARIES[0];
  const ActiveComponent = active.Component;

  return <ActiveComponent />;
}

