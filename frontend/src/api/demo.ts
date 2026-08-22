import { apiClient } from './client';

export const triggerDemoScenario = () => 
  apiClient.post<{status: string, message: string}>(`/demo/scenarios/attack-chain`);
