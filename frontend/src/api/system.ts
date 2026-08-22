import { apiClient } from './client';

export interface SystemHealth {
  api: string;
  database: string;
  brain1: string;
  brain2_provider: string;
  privacy_gateway: string;
  provider_config: {
    name: string;
    model: string;
  };
}

export const getSystemHealth = () => 
  apiClient.get<SystemHealth>(`/system/health`);
