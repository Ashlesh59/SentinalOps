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

export interface PipelineStage {
  id: string;
  label: string;
  status: 'idle' | 'pending' | 'running' | 'completed' | 'failed';
  duration_ms?: number;
}

export interface PipelineStatus {
  status: 'IDLE' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  pipeline_type: string;
  current_stage: string;
  total_duration_ms: number;
  stages: PipelineStage[];
  metrics: {
    raw_events: number;
    normalized_alerts: number;
    analytical_signals: number;
    correlated_incidents: number;
  };
}

export const getPipelineStatus = () => 
  apiClient.get<PipelineStatus>(`/system/pipeline-status`);
