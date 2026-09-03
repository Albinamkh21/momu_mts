import { LabelsPage } from './pages/LabelsPage';
import { RightCategoriesPage } from './pages/RightCategoriesPage';
import { RightUsageTypesPage } from './pages/RightUsageTypesPage';
import { FindingSourcesPage } from './pages/FindingSourcesPage';
import { RegionsPage } from './pages/RegionsPage';
import { PartnersPage } from './pages/PartnersPage';

// Single source of truth for the "Справочники" menu/pages. Adding an entry
// here automatically makes it appear in the sidebar submenu.
export const DICTIONARIES = [
  { key: 'labels', label: 'Лейблы', Component: LabelsPage },
  { key: 'right_categories', label: 'Категории прав', Component: RightCategoriesPage },
  { key: 'right_usage_types', label: 'Типы использования', Component: RightUsageTypesPage },
  { key: 'finding_sources', label: 'Источники поиска', Component: FindingSourcesPage },
  { key: 'regions', label: 'Регионы', Component: RegionsPage },
  { key: 'partners', label: 'Партнёры', Component: PartnersPage },
];
