export type DashboardView =
  | 'portfolio'
  | 'risk'
  | 'market'
  | 'recommendation'
  | 'operations'
  | 'compliance'
  | 'admin';

export interface ViewDefinition {
  id: DashboardView;
  label: string;
  shortLabel: string;
  description: string;
}

export const DASHBOARD_VIEWS: ViewDefinition[] = [
  {
    id: 'portfolio',
    label: 'Portfolio Intelligence Hub',
    shortLabel: 'Portfolio',
    description: 'Portfolio holdings, valuations, position management, and health overview.',
  },
  {
    id: 'risk',
    label: 'Risk & Exposure',
    shortLabel: 'Risk & Exposure',
    description: 'Structural concentration, sector allocations, 4-component risk scores, and data completeness.',
  },
  {
    id: 'market',
    label: 'Market Movement',
    shortLabel: 'Market',
    description: 'Live simulated quotes, price movements, sentiment news feed, and deterministic insights.',
  },
  {
    id: 'recommendation',
    label: 'Recommendation Review',
    shortLabel: 'AI Review',
    description: 'Evidence-grounded AI intelligence reports, verified drivers, risk alerts, and review cards.',
  },
  {
    id: 'operations',
    label: 'Operations',
    shortLabel: 'Operations',
    description: 'System health monitoring, database connectivity, cache performance, and provider state.',
  },
  {
    id: 'compliance',
    label: 'Compliance & Audit',
    shortLabel: 'Compliance',
    description: 'Regulatory SEBI disclaimers, claim-grounding verification audit trail, and zero-spend tracking.',
  },
  {
    id: 'admin',
    label: 'Admin Configuration',
    shortLabel: 'Admin',
    description: 'System environment details, zero-cost policy parameters, and demo data re-seeding.',
  },
];
