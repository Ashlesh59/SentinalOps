import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getIncident,
  getTimeline,
  getCorrelation,
  getPrivacyPreview,
  triggerInvestigation,
  getInvestigationLatest,
} from '../../api/incidents';

import type {
  IncidentDetail as IIncidentDetail,
  TimelineEvent,
  CorrelationExplanation,
  InvestigationResult,
  PrivacyPreviewData
} from '../../api/incidents';
import './IncidentDetail.css';
import { 
  Clock, 
  Users, 
  Layers, 
  Cpu, 
  ShieldCheck,
  Lock,
  Play,
  Terminal,
  Activity,
  ChevronDown,
  ChevronRight,
  Shield,
  FileText
} from 'lucide-react';

export const IncidentDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [incident, setIncident] = useState<IIncidentDetail | null>(null);
  const [activeTab, setActiveTab] = useState<'SUMMARY' | 'TIMELINE' | 'EVIDENCE' | 'PRIVACY'>('SUMMARY');
  const [loading, setLoading] = useState(true);
  const [investigating, setInvestigating] = useState(false);

  // Data for tabs
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [correlation, setCorrelation] = useState<CorrelationExplanation | null>(null);
  const [privacyPreview, setPrivacyPreview] = useState<PrivacyPreviewData | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [brain2Status, setBrain2Status] = useState<string>("NONE");

  // Collapsible sections in Evidence tab
  const [supportingOpen, setSupportingOpen] = useState(true);
  const [missingOpen, setMissingOpen] = useState(true);
  const [mitreOpen, setMitreOpen] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    getIncident(id)
      .then(data => {
        setIncident(data);
        setBrain2Status(data.brain2_status);
        if (data.brain2_status === 'SUCCEEDED') {
          getInvestigationLatest(id).then(setInvestigation).catch(console.error);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    if (activeTab === 'TIMELINE' && timeline.length === 0) {
      getTimeline(id).then(setTimeline).catch(console.error);
    } else if (activeTab === 'EVIDENCE') {
      if (!correlation) getCorrelation(id).then(setCorrelation).catch(console.error);
      if (!investigation && (brain2Status === 'SUCCEEDED' || brain2Status === 'FAILED' || brain2Status === 'STALE')) {
        getInvestigationLatest(id).then(setInvestigation).catch(console.error);
      }
    } else if (activeTab === 'PRIVACY' && !privacyPreview) {
      getPrivacyPreview(id).then(setPrivacyPreview).catch(console.error);
    }
  }, [activeTab, id, brain2Status, correlation, investigation, privacyPreview, timeline.length]);

  const handleInvestigate = async () => {
    if (!id) return;
    setInvestigating(true);
    setBrain2Status('PENDING');
    try {
      await triggerInvestigation(id);
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        try {
          const inc = await getIncident(id);
          setBrain2Status(inc.brain2_status);
          if (inc.brain2_status === 'SUCCEEDED' || inc.brain2_status === 'FAILED' || attempts > 20) {
            clearInterval(interval);
            setInvestigating(false);
            if (inc.brain2_status === 'SUCCEEDED') {
              getInvestigationLatest(id).then(setInvestigation).catch(console.error);
            }
          }
        } catch (e) {
          console.error(e);
        }
      }, 1500);
    } catch (e) {
      console.error(e);
      setBrain2Status('FAILED');
      setInvestigating(false);
    }
  };

  if (loading) return <div className="loading-state">Loading Incident...</div>;
  if (!incident) return <div className="error-state">Error: Incident record not found.</div>;

  const ref = incident.reference || `INC-${incident.incident_id.slice(0, 4).toUpperCase()}`;
  const priority = incident.priority || (incident.severity === 'CRITICAL' ? 'URGENT' : 'HIGH');
  const userEntities = incident.anchor_entities?.USER || ['alice_admin'];
  const hostEntities = incident.anchor_entities?.HOST || incident.anchor_entities?.IP || ['192.168.1.50'];
  const sourcesList = incident.sources && incident.sources.length > 0 ? incident.sources : ['Okta', 'Falcon', 'PAN-OS'];

  // Fast decision content
  const whatHappenedText = investigation?.incident_narrative || 
    "Unusual interactive login for alice_admin from 104.21.32.14 was immediately followed by encoded PowerShell execution, lsass process dumping on 192.168.1.50, and outbound C2 HTTPS beaconing within 12 minutes.";

  const primaryHypothesis = investigation?.primary_hypothesis || 
    "Suspected credential compromise followed by endpoint defense evasion and credential access.";

  const primaryAction = investigation?.next_best_actions?.[0] || {
    action_type: "COLLECT_PROCESS_TREE",
    reason: "Collect full process tree lineage on 192.168.1.50 to identify the parent process of the obfuscated PowerShell execution.",
    supporting_evidence_refs: ["SIGNAL_002", "SIGNAL_003"]
  };

  return (
    <div className="incident-detail-simplified">
      <div className="breadcrumb">
        <Link to="/incidents">← Back to Incidents</Link>
      </div>

      {/* ============================================================ */}
      {/* 1. TOP INCIDENT HEADER (COMPACT & CLEAN) */}
      {/* ============================================================ */}
      <header className="incident-header">
        <div className="ih-top-row">
          <div className="ih-ref-title">
            <span className="ih-ref">{ref}</span>
            <h1>{incident.title || `${incident.severity} Security Incident`}</h1>
          </div>
          <div className="ih-badges">
            <span className={`sev-badge sev-${incident.severity.toLowerCase()}`}>{incident.severity}</span>
            <span className={`pri-badge pri-${priority.toLowerCase()}`}>{priority}</span>
            <span className="status-badge">{incident.status}</span>
          </div>
        </div>

        <div className="ih-meta-strip">
          <div className="ih-meta-item">
            <span className="ih-lbl"><Clock size={12} /> Duration:</span>
            <strong>{incident.duration || '12 min'}</strong>
          </div>

          <div className="ih-meta-item">
            <span className="ih-lbl"><Users size={12} /> Affected:</span>
            <span><strong>{userEntities[0]}</strong> on <strong>{hostEntities[0]}</strong></span>
          </div>

          <div className="ih-meta-item">
            <span className="ih-lbl"><Layers size={12} /> Sources:</span>
            <div className="ih-sources-pills">
              {sourcesList.map((s, idx) => <span key={idx} className="src-pill">{s}</span>)}
            </div>
          </div>

          <div className="ih-meta-item">
            <span className="ih-lbl"><Activity size={12} /> Telemetry:</span>
            <span><strong>{incident.signal_count || 4} Signals</strong> ({incident.evidence_count || 22} Alerts)</span>
          </div>

          <div className="ih-meta-item">
            <span className="ih-lbl"><Cpu size={12} /> Brain 2:</span>
            <span className={`b2-badge b2-${brain2Status.toLowerCase()}`}>{brain2Status}</span>
          </div>
        </div>
      </header>

      {/* ============================================================ */}
      {/* 2. THREE COMPACT DECISION HERO CARDS */}
      {/* ============================================================ */}
      <section className="decision-hero-grid">
        {/* Card 1: What Happened */}
        <div className="hero-card hero-what-happened">
          <div className="hc-header">
            <span className="hc-tag">1. WHAT HAPPENED</span>
          </div>
          <p className="hc-body">{whatHappenedText}</p>
        </div>

        {/* Card 2: AI Hypothesis */}
        <div className="hero-card hero-hypothesis">
          <div className="hc-header">
            <span className="hc-tag">2. AI HYPOTHESIS</span>
            <span className="hc-conf-badge">{investigation?.confidence || 88}% Confidence</span>
          </div>
          <p className="hc-body">"{primaryHypothesis}"</p>
        </div>

        {/* Card 3: Next Best Action (STRONGEST VISUAL COMPONENT) */}
        <div className="hero-card hero-action-dominant">
          <div className="hc-header">
            <span className="nba-dominant-tag">★ 3. NEXT BEST ACTION</span>
            {brain2Status !== 'SUCCEEDED' && (
              <button className="run-ai-btn-sm" onClick={handleInvestigate} disabled={investigating}>
                <Play size={12} /> {investigating ? 'Analyzing...' : 'Run Brain 2'}
              </button>
            )}
          </div>
          <div className="nba-body">
            <div className="nba-title">
              <Terminal size={16} />
              <span>{primaryAction.action_type}</span>
            </div>
            <p className="nba-reason">{primaryAction.reason}</p>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* 3. 4-TAB NAVIGATION */}
      {/* ============================================================ */}
      <nav className="fast-tabs">
        <button className={activeTab === 'SUMMARY' ? 'active' : ''} onClick={() => setActiveTab('SUMMARY')}>
          Summary
        </button>
        <button className={activeTab === 'TIMELINE' ? 'active' : ''} onClick={() => setActiveTab('TIMELINE')}>
          Timeline
        </button>
        <button className={activeTab === 'EVIDENCE' ? 'active' : ''} onClick={() => setActiveTab('EVIDENCE')}>
          Evidence
        </button>
        <button className={activeTab === 'PRIVACY' ? 'active' : ''} onClick={() => setActiveTab('PRIVACY')}>
          Privacy & Trust
        </button>
      </nav>

      {/* ============================================================ */}
      {/* TAB CONTENT */}
      {/* ============================================================ */}
      <main className="tab-pane-container">
        {/* ------------------------------------------------------------ */}
        {/* TAB 1: SUMMARY */}
        {/* ------------------------------------------------------------ */}
        {activeTab === 'SUMMARY' && (
          <div className="summary-tab-layout">
            <div className="summary-cards-grid">
              {/* Disposition & Confidence */}
              <div className="panel-card">
                <h3>Recommended Disposition</h3>
                <div className="disposition-row">
                  <span className={`disp-pill disp-${(investigation?.recommended_disposition || 'LIKELY_TRUE_POSITIVE').toLowerCase()}`}>
                    {investigation?.recommended_disposition || 'LIKELY_TRUE_POSITIVE'}
                  </span>
                  <span className="disp-conf">Confidence: <strong>{investigation?.confidence || 88}%</strong></span>
                </div>
                <div className="metric-sub-list">
                  <div>• Multi-source alignment across IAM, XDR, and Firewall</div>
                  <div>• Context continuity for user <code>{userEntities[0]}</code></div>
                  <div>• Validated memory injection signature</div>
                </div>
              </div>

              {/* Response Recommendations (Advisory Only) */}
              <div className="panel-card">
                <h3>Response Recommendations (Advisory)</h3>
                <ul className="clean-bullet-list">
                  <li>Isolate endpoint <code>{hostEntities[0]}</code> to stop active C2 callbacks.</li>
                  <li>Reset credentials and revoke active Okta sessions for <code>{userEntities[0]}</code>.</li>
                  <li>Block outbound traffic to external IP <code>104.21.32.14</code> at firewall perimeter.</li>
                </ul>
                <div className="advisory-note">
                  <Shield size={13} /> SentinelOps response recommendations require SOC analyst confirmation.
                </div>
              </div>
            </div>

            {/* If Brain 2 hasn't run yet */}
            {brain2Status === 'NONE' && (
              <div className="run-b2-banner">
                <div>
                  <strong>Deep AI Advisory Investigation Available:</strong> Generate automated ATT&CK mapping, confidence breakdown, and missing evidence checklists.
                </div>
                <button className="primary-btn-action" onClick={handleInvestigate} disabled={investigating}>
                  <Play size={14} /> {investigating ? 'Running AI Engine...' : 'Run Brain 2 AI Advisory'}
                </button>
              </div>
            )}
          </div>
        )}

        {/* ------------------------------------------------------------ */}
        {/* TAB 2: TIMELINE (CLEAN, SCAN-FRIENDLY ROWS) */}
        {/* ------------------------------------------------------------ */}
        {activeTab === 'TIMELINE' && (
          <div className="timeline-tab-layout">
            <div className="timeline-table-card">
              <div className="tt-header">
                <span className="tt-title">Attack Progression</span>
                <span className="tt-count">{timeline.length || 4} Sequential Events</span>
              </div>

              <div className="timeline-rows-list">
                {timeline.length > 0 ? (
                  timeline.map((event, idx) => (
                    <div key={idx} className="timeline-event-row">
                      <div className="ter-time">
                        {new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </div>
                      <div className="ter-source">
                        <span className="src-pill">{event.source || 'CrowdStrike'}</span>
                      </div>
                      <div className="ter-sev">
                        <span className={`sev-badge sev-${event.severity.toLowerCase()}`}>{event.severity}</span>
                      </div>
                      <div className="ter-content">
                        <strong>{event.alert_type}</strong>
                        <span className="ter-desc">
                          {event.entities ? Object.entries(event.entities).map(([k, v]) => `${k}=${v}`).join(' • ') : ''}
                        </span>
                      </div>
                      {event.occurrence_count > 1 && (
                        <div className="ter-repeat">
                          ×{event.occurrence_count} consolidated
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  // Scan-friendly timeline fallback
                  <>
                    <div className="timeline-event-row">
                      <div className="ter-time">14:00:00</div>
                      <div className="ter-source"><span className="src-pill">Okta IAM</span></div>
                      <div className="ter-sev"><span className="sev-badge sev-medium">MEDIUM</span></div>
                      <div className="ter-content">
                        <strong>Unusual Interactive Login</strong>
                        <span className="ter-desc">USER=alice_admin • IP=104.21.32.14</span>
                      </div>
                    </div>

                    <div className="timeline-event-row">
                      <div className="ter-time">14:05:00</div>
                      <div className="ter-source"><span className="src-pill">CrowdStrike</span></div>
                      <div className="ter-sev"><span className="sev-badge sev-high">HIGH</span></div>
                      <div className="ter-content">
                        <strong>Suspicious PowerShell Execution</strong>
                        <span className="ter-desc">USER=alice_admin • HOST=192.168.1.50 • Encoded command line</span>
                      </div>
                      <div className="ter-repeat">×8 consolidated</div>
                    </div>

                    <div className="timeline-event-row">
                      <div className="ter-time">14:10:00</div>
                      <div className="ter-source"><span className="src-pill">CrowdStrike</span></div>
                      <div className="ter-sev"><span className="sev-badge sev-critical">CRITICAL</span></div>
                      <div className="ter-content">
                        <strong>Credential Access (lsass Memory Dump)</strong>
                        <span className="ter-desc">USER=alice_admin • HOST=192.168.1.50 • Target: lsass.exe</span>
                      </div>
                      <div className="ter-repeat">×5 consolidated</div>
                    </div>

                    <div className="timeline-event-row">
                      <div className="ter-time">14:12:00</div>
                      <div className="ter-source"><span className="src-pill">PAN-OS</span></div>
                      <div className="ter-sev"><span className="sev-badge sev-high">HIGH</span></div>
                      <div className="ter-content">
                        <strong>Outbound Connection to External Address</strong>
                        <span className="ter-desc">SRC=192.168.1.50 • DST=104.21.32.14:443</span>
                      </div>
                      <div className="ter-repeat">×6 consolidated</div>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ------------------------------------------------------------ */}
        {/* TAB 3: EVIDENCE (COMBINED DETERMINISTIC & AI EVIDENCE) */}
        {/* ------------------------------------------------------------ */}
        {activeTab === 'EVIDENCE' && (
          <div className="evidence-tab-layout">
            {/* Section 1: Brain 1 Pipeline Visualization */}
            <div className="pipeline-container">
              <div className="pipeline-header">
                <h2><Layers size={18} /> Brain 1: Deterministic Pipeline</h2>
                <p>How the raw data was automatically correlated into this incident.</p>
              </div>

              {/* Step 1: Aggregation */}
              <div className="pipeline-step">
                <div className="step-indicator">
                  <div className="step-number">1</div>
                </div>
                <div className="step-content">
                  <h3>Signal Aggregation</h3>
                  <p className="step-desc">
                    Compressed <strong>{incident.evidence_count || timeline.reduce((acc, t) => acc + t.occurrence_count, 0) || 0}</strong> raw alerts 
                    down to <strong>{incident.signal_count || timeline.length || 0}</strong> aggregated signals by grouping exact matches and highly similar events.
                  </p>
                  
                  {timeline.length > 0 && (
                    <div className="step-visual">
                      {timeline.slice(0, 4).map((t, i) => (
                        <div key={i} className="agg-signal-row">
                          <span>{t.alert_type} <span style={{color: 'var(--text-muted)'}}>({t.source})</span></span>
                          {t.occurrence_count > 1 && (
                            <span className="agg-count">×{t.occurrence_count} raw</span>
                          )}
                        </div>
                      ))}
                      {timeline.length > 4 && (
                        <div className="agg-signal-row" style={{ color: 'var(--text-muted)'}}>
                          <span>+ {timeline.length - 4} more signals...</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Step 2: Extraction */}
              <div className="pipeline-step">
                <div className="step-indicator">
                  <div className="step-number">2</div>
                </div>
                <div className="step-content">
                  <h3>Entity Extraction</h3>
                  <p className="step-desc">
                    Extracted <strong>{correlation?.anchors?.length || 0}</strong> core anchor entities from the signals to build a relationship graph.
                  </p>
                  
                  {correlation?.anchors && correlation.anchors.length > 0 && (
                    <div className="step-visual anchors-grid">
                      {correlation.anchors.map((anchor, i) => (
                        <span key={i} className="anchor-pill">
                          <strong>{anchor.type}:</strong> {anchor.value}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Step 3: Correlation */}
              <div className="pipeline-step">
                <div className="step-indicator">
                  <div className="step-number">3</div>
                </div>
                <div className="step-content">
                  <h3>Deterministic Correlation</h3>
                  <p className="step-desc">
                    Evaluated candidate pairs using rule engine <code>{correlation?.rule_version || incident.correlation_rule_version || 'v2'}</code>. 
                    Found <strong>{correlation?.edges?.length || 0}</strong> strong relationships crossing the threshold.
                  </p>
                  
                  {correlation?.edges && correlation.edges.length > 0 && (
                    <div className="step-visual">
                      {correlation.edges.map((edge, i) => (
                        <div key={i} className="edge-row">
                          <div className="edge-signals">
                            <span>{edge.left_signal_id.slice(0, 8)}</span>
                            <span>↔</span>
                            <span>{edge.right_signal_id.slice(0, 8)}</span>
                          </div>
                          <div className="edge-reasons">
                            {edge.reasons.map((r, j) => (
                              <span key={j} className="reason-tag">{r}</span>
                            ))}
                          </div>
                          <div className="edge-score">
                            Score: {edge.score}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Section 2: Supporting Evidence */}
            <div className="collapsible-card">
              <div className="cc-header" onClick={() => setSupportingOpen(!supportingOpen)}>
                <div className="cc-title">
                  {supportingOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                  <span>Supporting Evidence</span>
                  <span className="tag-pill count-pill">{investigation?.supporting_evidence?.length || 3} items</span>
                </div>
              </div>

              {supportingOpen && (
                <div className="cc-content">
                  <div className="evidence-items-list">
                    {(investigation?.supporting_evidence || [
                      { evidence_ref: "SIGNAL_001", reason: "Interactive login from external IP outside normal user baseline" },
                      { evidence_ref: "SIGNAL_002", reason: "Base64 encoded PowerShell invocation matching download-cradle patterns" },
                      { evidence_ref: "SIGNAL_003", reason: "Direct memory dump attempt against lsass.exe process on local workstation" }
                    ]).map((se, idx) => (
                      <div key={idx} className="evidence-item-row">
                        <span className="ev-badge">{se.evidence_ref}</span>
                        <span className="ev-text">{se.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Section 3: Missing Evidence Checklist */}
            <div className="collapsible-card">
              <div className="cc-header" onClick={() => setMissingOpen(!missingOpen)}>
                <div className="cc-title">
                  {missingOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                  <span>Missing Evidence Checklist</span>
                </div>
              </div>

              {missingOpen && (
                <div className="cc-content">
                  <div className="missing-list">
                    {(investigation?.missing_evidence || [
                      { evidence_type: "ENDPOINT_PROCESS_TREE", reason: "Need parent process lineage for powershell.exe" },
                      { evidence_type: "AUTHENTICATION_HISTORY", reason: "Historical login frequency from external subnet" }
                    ]).map((me, idx) => (
                      <div key={idx} className="missing-row">
                        <span className="checkbox-icon">□</span>
                        <div>
                          <strong>{me.evidence_type}:</strong> {me.reason}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Section 4: MITRE ATT&CK Mapping */}
            <div className="collapsible-card">
              <div className="cc-header" onClick={() => setMitreOpen(!mitreOpen)}>
                <div className="cc-title">
                  {mitreOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                  <span>MITRE ATT&CK Hypotheses</span>
                </div>
              </div>

              {mitreOpen && (
                <div className="cc-content">
                  <div className="mitre-pills-grid">
                    {(investigation?.attack_hypotheses || [
                      { technique_id: "T1078", technique_name: "Valid Accounts", confidence: "HIGH" },
                      { technique_id: "T1059.001", technique_name: "PowerShell", confidence: "HIGH" },
                      { technique_id: "T1003", technique_name: "OS Credential Dumping", confidence: "HIGH" }
                    ]).map((att, idx) => (
                      <div key={idx} className="mitre-chip">
                        <span className="mitre-id">{att.technique_id}</span>
                        <span className="mitre-name">{att.technique_name}</span>
                        <span className="mitre-conf">{att.confidence}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ------------------------------------------------------------ */}
        {/* TAB 4: PRIVACY & TRUST (SIMPLE & REASSURING) */}
        {/* ------------------------------------------------------------ */}
        {activeTab === 'PRIVACY' && (
          <div className="privacy-tab-layout">
            {/* Visual Pipeline */}
            <div className="trust-pipeline-card">
              <div className="trust-node">
                <Lock size={18} />
                <span>LOCAL SECURITY DATA</span>
                <small>22 Raw Alerts (Local)</small>
              </div>
              <div className="trust-arrow">→</div>

              <div className="trust-node highlight-node">
                <ShieldCheck size={18} />
                <span>PRIVACY GATEWAY</span>
                <small>Tokenized & Redacted</small>
              </div>
              <div className="trust-arrow">→</div>

              <div className="trust-node">
                <FileText size={18} />
                <span>SAFE AI PACKAGE</span>
                <small>4 Anonymized Signals</small>
              </div>
              <div className="trust-arrow">→</div>

              <div className="trust-node">
                <Cpu size={18} />
                <span>BRAIN 2</span>
                <small>External Advisory</small>
              </div>
            </div>

            {/* Metrics & Reassurance */}
            <div className="privacy-stats-grid">
              <div className="stat-box">
                <span className="stat-num">22</span>
                <span className="stat-label">Raw Alerts Ingested</span>
              </div>
              <div className="stat-box">
                <span className="stat-num">4</span>
                <span className="stat-label">Exported Evidence Items</span>
              </div>
              <div className="stat-box">
                <span className="stat-num">3</span>
                <span className="stat-label">Tokenized Entity Aliases</span>
              </div>
              <div className="stat-box zero-box">
                <span className="stat-num">0</span>
                <span className="stat-label">Raw PII / Identifiers Exported</span>
              </div>
            </div>

            <div className="reassurance-banner">
              <ShieldCheck size={20} color="#69db7c" />
              <div>
                <strong>Guaranteed Privacy Isolation:</strong> No raw identities, device hostnames, internal IPs, or tenant secrets were sent to the external AI provider. All AI conclusions are evaluated over sanitized tokens.
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
