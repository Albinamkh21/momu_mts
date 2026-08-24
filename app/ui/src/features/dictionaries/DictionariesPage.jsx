import React, { useState } from 'react';
import { LabelsPage } from './pages/LabelsPage';
import { RightCategoriesPage } from './pages/RightCategoriesPage';
import { RightUsageTypesPage } from './pages/RightUsageTypesPage';
import { FindingSourcesPage } from './pages/FindingSourcesPage';
import { RegionsPage } from './pages/RegionsPage';
import { PartnersPage } from './pages/PartnersPage';

const TABS = [
  { key: 'labels', label: 'Лейблы', Component: LabelsPage },
  { key: 'right_categories', label: 'Категории прав', Component: RightCategoriesPage },
  { key: 'right_usage_types', label: 'Типы использования', Component: RightUsageTypesPage },
  { key: 'finding_sources', label: 'Источники поиска', Component: FindingSourcesPage },
  { key: 'regions', label: 'Регионы', Component: RegionsPage },
  { key: 'partners', label: 'Партнёры', Component: PartnersPage },
];

export function DictionariesPage() {
  const [activeTab, setActiveTab] = useState(TABS[0].key);
  const ActiveComponent = TABS.find((t) => t.key === activeTab).Component;

  return (
    <div>
      <div className="action-section" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={activeTab === tab.key ? 'btn btn-primary' : 'btn-secondary'}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <ActiveComponent />
    </div>
  );
}
