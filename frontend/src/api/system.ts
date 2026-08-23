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

export interface AiPolicy {
  zero_egress_enforced: boolean;
  provider: string;
  model: string;
  endpoint: string;
  message: string;
}

export const getAiPolicy = () => 
  apiClient.get<AiPolicy>(`/system/ai-policy`);
