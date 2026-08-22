import { apiClient, DEMO_TENANT_ID } from './client';

export interface Incident {
  incident_id: string;
  reference?: string;
  title?: string;
  incident_type: string;
  severity: string;
  priority?: string;
  status: string;
  first_seen: string | null;
  last_seen: string | null;
  duration?: string;
  incident_version: number;
  anchor_entities?: Record<string, any>;
  sources?: string[];
  signal_count?: number;
  evidence_count?: number;
  brain2_status: string;
  brain2_stale: boolean;
}

export interface IncidentDetail extends Incident {
  tenant_id: string;
  title: string;
  anchor_entities: any;
  correlation_rule_version: string;
  member_signal_summary: {
    count: number;
    sources: string[];
  };
}

export interface TimelineEvent {
  timestamp: string;
  category: string;
  alert_type: string;
  severity: string;
  occurrence_count: number;
  source: string;
  entities: any;
}

export interface CorrelationExplanation {
  incident_id: string;
  rule_version: string;
  anchors: { type: string; value: string }[];
  edges: {
    left_signal_id: string;
    right_signal_id: string;
    score: number;
    reasons: string[];
  }[];
}

export interface EvidenceReference {
  evidence_ref: string;
  reason: string;
}

export interface MissingEvidenceItem {
  evidence_type: string;
  reason: string;
}

export interface NextBestActionItem {
  action_type: string;
  reason: string;
  supporting_evidence_refs?: string[];
}

export interface AttackHypothesisItem {
  technique_id: string;
  technique_name?: string;
  confidence: string;
  evidence_refs?: string[];
}

export interface AuditCard {
  provider: string;
  model: string;
  privacy_profile: string;
  evidence_exported: number;
  total_raw_telemetry: number;
  raw_identifiers_detected: number;
  internal_uuids_exported: number;
  raw_events_exported: number;
  package_fingerprint: string;
}

export interface PrivacyPreviewData {
  incident_type: string;
  package_fingerprint: string;
  incident_version: number;
  signals: any[];
  graph_edges?: any[];
  anchor_entities?: any;
  audit_card?: AuditCard;
}

export interface InvestigationResult {
  job_id?: string;
  job_status?: string;
  is_stale?: boolean;
  result_id?: string;
  primary_hypothesis: string;
  incident_narrative?: string;
  supporting_evidence: EvidenceReference[];
  contradicting_evidence: EvidenceReference[];
  missing_evidence: MissingEvidenceItem[];
  recommended_disposition: string;
  confidence?: number;
  recommended_priority: string;
  estimated_impact?: string;
  confidence_drivers?: string[];
  confidence_reducers?: string[];
  next_best_actions: NextBestActionItem[];
  response_considerations?: string[];
  attack_hypotheses: AttackHypothesisItem[];
  limitations: string;
}

export const getIncidents = () => 
  apiClient.get<Incident[]>(`/incidents?tenant_id=${DEMO_TENANT_ID}`);

export const getIncident = (id: string) => 
  apiClient.get<IncidentDetail>(`/incidents/${id}?tenant_id=${DEMO_TENANT_ID}`);

export const getTimeline = (id: string) => 
  apiClient.get<TimelineEvent[]>(`/incidents/${id}/timeline?tenant_id=${DEMO_TENANT_ID}`);

export const getCorrelation = (id: string) => 
  apiClient.get<CorrelationExplanation>(`/incidents/${id}/correlation-explanation?tenant_id=${DEMO_TENANT_ID}`);

export const getPrivacyPreview = (id: string) => 
  apiClient.get<PrivacyPreviewData>(`/incidents/${id}/privacy-preview?tenant_id=${DEMO_TENANT_ID}`);

export const triggerInvestigation = (id: string) => 
  apiClient.post<{status: string, job_id: string}>(`/incidents/${id}/investigations?tenant_id=${DEMO_TENANT_ID}`);

export const getInvestigationLatest = (id: string) => 
  apiClient.get<InvestigationResult>(`/incidents/${id}/investigations/latest?tenant_id=${DEMO_TENANT_ID}`);
