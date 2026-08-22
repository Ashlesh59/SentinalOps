import { apiClient, DEMO_TENANT_ID } from './client';

export interface Alert {
  id: string;
  timestamp: string;
  severity: string;
  source_product: string;
  category_name: string;
  alert_type: string;
  user: string;
  host: string;
}

export const getAlerts = () => 
  apiClient.get<Alert[]>(`/alerts?tenant_id=${DEMO_TENANT_ID}`);
