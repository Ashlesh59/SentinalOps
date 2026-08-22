import { apiClient } from './client';

export interface DashboardSummary {
  normalized_alerts: number;
  analytical_signals: number;
  noise_reduction_percent?: number;
  open_incidents: number;
  critical_incidents: number;
  high_priority_incidents?: number;
  investigations: number;
  investigations_pending?: number;
  investigations_failed?: number;
  investigations_succeeded?: number;
  severity_distribution: Record<string, number>;
  source_distribution: Record<string, number>;
}

export const getDashboardSummary = () => 
  apiClient.get<DashboardSummary>(`/dashboard/summary`);
