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
  FileText,
  AlertCircle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  BookOpen,
  Lightbulb,
  Loader2,
} from 'lucide-react';

type TabId = 'OVERVIEW' | 'EVIDENCE' | 'INVESTIGATE' | 'RESPOND' | 'PAST_CASES' | 'PREVENT' | 'PRIVACY';

export const IncidentDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [incident, setIncident] = useState<IIncidentDetail | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>('OVERVIEW');
  const [loading, setLoading] = useState(true);
  const [investigating, setInvestigating] = useState(false);

  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [correlation, setCorrelation] = useState<CorrelationExplanation | null>(null);
  const [privacyPreview, setPrivacyPreview] = useState<PrivacyPreviewData | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [brain2Status, setBrain2Status] = useState<string>('NONE');

  // Progressive disclosure toggles
  const [confExpanded, setConfExpanded] = useState(false);
  const [limitationsExpanded, setLimitationsExpanded] = useState(false);
  const [edgeDetailsExpanded, setEdgeDetailsExpanded] = useState(false);
  const [mitreExpanded, setMitreExpanded] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);

    getIncident(id)
      .then(data => {
        setIncident(data);
        setBrain2Status(data.brain2_status);
        if (data.brain2_status === 'SUCCEEDED' || data.brain2_status === 'FAILED' || data.brain2_status === 'STALE') {
          return getInvestigationLatest(id).then(setInvestigation).catch(console.error);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));

    getTimeline(id).then(setTimeline).catch(console.error);
    getCorrelation(id).then(setCorrelation).catch(console.error);
    getPrivacyPreview(id).then(setPrivacyPreview).catch(console.error);
  }, [id]);

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

  const ref = incident.reference;
  const userEntities = incident.anchor_entities?.USER || [];
  const hostEntities = incident.anchor_entities?.HOST || incident.anchor_entities?.IP || [];
  const sourcesList = incident.sources || [];

  // Above-fold decision content — Backend-derived
  const whatHappenedText = investigation?.incident_narrative;
  const primaryHypothesis = investigation?.primary_hypothesis;
  const primaryAction = investigation?.next_best_actions?.[0];

  const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: 'OVERVIEW',    label: 'Overview',    icon: <Activity size={14} /> },
    { id: 'EVIDENCE',   label: 'Evidence',    icon: <Layers size={14} /> },
    { id: 'INVESTIGATE',label: 'Investigate', icon: <Cpu size={14} /> },
    { id: 'RESPOND',    label: 'Respond',     icon: <Shield size={14} /> },
    { id: 'PAST_CASES', label: 'Past Cases',  icon: <BookOpen size={14} /> },
    { id: 'PREVENT',    label: 'Prevent',     icon: <Lightbulb size={14} /> },
    { id: 'PRIVACY',    label: 'Privacy',     icon: <ShieldCheck size={14} /> },
  ];

  return (
    <div className="incident-workspace">
      {/* ─── BREADCRUMB ─── */}
      <div className="breadcrumb">
        <Link to="/incidents">← Back to Incidents</Link>
      </div>

      {/* ================================================================ */}
      {/* 1. INCIDENT HEADER — compact verified facts */}
      {/* ================================================================ */}
      <header className="incident-header">
        <div className="ih-top-row">
          <div className="ih-ref-title">
            <span className="ih-ref">{ref}</span>
            <h1>{incident.title}</h1>
          </div>
          <div className="ih-badges">
            <span className={`sev-badge sev-${incident.severity.toLowerCase()}`}>{incident.severity}</span>
            {incident.priority && incident.priority !== incident.severity && (
              <span className={`pri-badge pri-${incident.priority.toLowerCase()}`}>{incident.priority}</span>
            )}
            <span className="status-badge">{incident.status}</span>
            <span className={`b2-badge b2-${brain2Status.toLowerCase()}`}>
              Brain 2: {brain2Status}
            </span>
          </div>
        </div>

        <div className="ih-meta-strip">
          <div className="ih-meta-item">
            <span className="ih-lbl"><Clock size={12} /> Duration:</span>
            <strong>{incident.duration || 'N/A'}</strong>
          </div>
          <div className="ih-meta-item">
            <span className="ih-lbl"><Users size={12} /> Affected:</span>
            {userEntities.length > 0 || hostEntities.length > 0 ? (
              <span>
                {userEntities.length > 0 && <strong>{userEntities[0]} </strong>}
                {hostEntities.length > 0 && <>on <strong>{hostEntities[0]}</strong></>}
              </span>
            ) : <span className="empty-val">N/A</span>}
          </div>
          <div className="ih-meta-item">
            <span className="ih-lbl"><Layers size={12} /> Telemetry:</span>
            <span><strong>{incident.signal_count} Signals</strong> ({incident.evidence_count} Alerts)</span>
          </div>
          <div className="ih-meta-item">
            <span className="ih-lbl">Sources:</span>
            <div className="ih-sources-pills">
              {sourcesList.length > 0
                ? sourcesList.map((s, i) => <span key={i} className="src-pill">{s}</span>)
                : <span className="empty-val">None</span>}
            </div>
          </div>
        </div>
      </header>

      {/* ================================================================ */}
      {/* 2. ABOVE-FOLD DECISION CARDS — 5-second analyst view */}
      {/* ================================================================ */}
      <section className="decision-hero-grid">
        {/* WHAT HAPPENED */}
        <div className="hero-card hero-what-happened">
          <div className="hc-header">
            <span className="hc-tag">What Happened</span>
            <span className={`hc-source-badge ${whatHappenedText ? 'badge-ai' : 'badge-obs'}`}>
              {whatHappenedText ? 'AI ADVISORY' : 'OBSERVED'}
            </span>
          </div>
          <p className="hc-body">
            {whatHappenedText
              || `${incident.signal_count} correlated signal${incident.signal_count !== 1 ? 's' : ''} across ${sourcesList.length > 0 ? sourcesList.join(', ') : 'multiple sources'} over ${incident.duration || 'an unknown duration'}.`}
          </p>
        </div>

        {/* PRIMARY HYPOTHESIS */}
        <div className="hero-card hero-hypothesis">
          <div className="hc-header">
            <span className="hc-tag">Primary Hypothesis</span>
            {brain2Status === 'SUCCEEDED' && investigation?.confidence !== undefined && (
              <span className="hc-conf-badge">{investigation.confidence}% Confidence</span>
            )}
          </div>
          <p className="hc-body">
            {brain2Status === 'SUCCEEDED' && primaryHypothesis
              ? `"${primaryHypothesis}"`
              : brain2Status === 'NONE'
              ? <span className="empty-val">AI investigation not run</span>
              : (brain2Status === 'PENDING' || brain2Status === 'RUNNING')
              ? <span className="empty-val">Analyzing...</span>
              : brain2Status === 'FAILED'
              ? <span className="empty-val">AI investigation failed</span>
              : <span className="empty-val">Not available</span>}
          </p>
          {brain2Status === 'SUCCEEDED' && investigation?.recommended_disposition && (
            <div className="hyp-disposition">
              <span className={`disp-pill disp-${investigation.recommended_disposition.toLowerCase()}`}>
                {investigation.recommended_disposition}
              </span>
            </div>
          )}
        </div>

        {/* ★ NEXT BEST ACTION — dominant */}
        <div className="hero-card hero-action-dominant">
          <div className="hc-header">
            <span className="nba-dominant-tag">★ Next Best Action</span>
            {brain2Status !== 'SUCCEEDED' && (
              <button className="run-ai-btn-sm" onClick={handleInvestigate} disabled={investigating}>
                {investigating
                  ? <><Loader2 size={12} className="spin" /> Analyzing...</>
                  : <><Play size={12} /> Run Brain 2</>}
              </button>
            )}
          </div>
          <div className="nba-body">
            {brain2Status === 'SUCCEEDED' && primaryAction ? (
              <>
                <div className="nba-title">
                  <Terminal size={16} />
                  <span>{primaryAction.action_type}</span>
                </div>
                <p className="nba-reason">{primaryAction.reason}</p>
                {primaryAction.supporting_evidence_refs && primaryAction.supporting_evidence_refs.length > 0 && (
                  <div className="nba-evidence-refs">
                    {primaryAction.supporting_evidence_refs.map((r, i) => (
                      <span key={i} className="ev-badge">{r}</span>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <p className="nba-reason">
                <span className="empty-val">
                  {brain2Status === 'NONE' ? 'Run AI investigation to get action guidance.' : 'Awaiting investigation result.'}
                </span>
              </p>
            )}
          </div>
        </div>
      </section>

      {/* ================================================================ */}
      {/* 3. TAB NAVIGATION */}
      {/* ================================================================ */}
      <nav className="fast-tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={activeTab === tab.id ? 'active' : ''}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </nav>

      {/* ================================================================ */}
      {/* 4. TAB CONTENT */}
      {/* ================================================================ */}
      <main className="tab-pane-container">

        {/* ─── OVERVIEW ─── */}
        {activeTab === 'OVERVIEW' && (
          <div className="overview-tab-layout">
            {/* Disposition card (Brain 2 if available, else deterministic summary) */}
            <div className="overview-top-grid">
              <div className="panel-card">
                <h3>Disposition</h3>
                {brain2Status === 'SUCCEEDED' && investigation ? (
                  <div className="disposition-row">
                    <span className={`disp-pill disp-${(investigation.recommended_disposition || 'unknown').toLowerCase()}`}>
                      {investigation.recommended_disposition || 'UNKNOWN'}
                    </span>
                    {investigation.confidence !== undefined && (
                      <span className="disp-conf">Confidence: <strong>{investigation.confidence}%</strong></span>
                    )}
                    <span className="badge-ai-inline">AI ADVISORY</span>
                  </div>
                ) : (
                  <>
                    <div className="disposition-row">
                      <span className="disp-pill disp-pending">PENDING INVESTIGATION</span>
                    </div>
                    {brain2Status === 'NONE' && (
                      <div className="run-b2-banner" style={{ marginTop: '12px' }}>
                        <span>Run Brain 2 to get a recommended disposition and investigation guidance.</span>
                        <button className="primary-btn-action" onClick={handleInvestigate} disabled={investigating}>
                          <Play size={14} /> {investigating ? 'Running...' : 'Run AI Investigation'}
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>

              <div className="panel-card">
                <h3>Correlated Sources</h3>
                <div className="source-breakdown">
                  {sourcesList.length > 0
                    ? sourcesList.map((s, i) => <span key={i} className="src-pill src-pill-lg">{s}</span>)
                    : <span className="empty-val">No source information</span>}
                </div>
                <div className="policy-row">
                  <span className="policy-label">Correlation Policy:</span>
                  <code>{correlation?.rule_version || incident.correlation_rule_version || 'N/A'}</code>
                </div>
              </div>
            </div>

            {/* Attack Progression Timeline */}
            <div className="timeline-table-card">
              <div className="tt-header">
                <span className="tt-title">Attack Progression</span>
                <span className="tt-count">{timeline.length} Sequential Events</span>
              </div>
              <div className="timeline-rows-list">
                {timeline.length > 0 ? (
                  timeline.map((event, idx) => (
                    <div key={idx} className="timeline-event-row">
                      <div className="ter-time">
                        {new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </div>
                      <div className="ter-source">
                        <span className="src-pill">{event.source || '—'}</span>
                      </div>
                      <div className="ter-sev">
                        <span className={`sev-badge sev-${event.severity.toLowerCase()}`}>{event.severity}</span>
                      </div>
                      <div className="ter-content">
                        <strong>{event.alert_type}</strong>
                        <span className="ter-desc">
                          {event.entities ? Object.entries(event.entities).map(([k, v]) => `${k}=${v}`).join(' · ') : ''}
                        </span>
                      </div>
                      {event.occurrence_count > 1 && (
                        <div className="ter-repeat">×{event.occurrence_count} consolidated</div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="empty-state-message">No timeline events available.</div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ─── EVIDENCE (BRAIN 1) ─── */}
        {activeTab === 'EVIDENCE' && (
          <div className="evidence-tab-layout">
            <div className="panel-card evidence-hero-card">
              <div className="evidence-hero-row">
                <div className="ev-hero-stat">
                  <span className="ev-hero-num">{incident.evidence_count}</span>
                  <span className="ev-hero-lbl">Raw Alerts</span>
                </div>
                <div className="ev-hero-arrow">→</div>
                <div className="ev-hero-stat">
                  <span className="ev-hero-num">{incident.signal_count}</span>
                  <span className="ev-hero-lbl">Signals</span>
                </div>
                <div className="ev-hero-arrow">→</div>
                <div className="ev-hero-stat ev-hero-stat-highlight">
                  <span className="ev-hero-num">1</span>
                  <span className="ev-hero-lbl">Incident</span>
                </div>
                <div className="ev-hero-policy">
                  <span className="policy-label">Correlation Policy</span>
                  <code>{correlation?.rule_version || incident.correlation_rule_version || 'N/A'}</code>
                  <span className="badge-det">DETERMINISTIC</span>
                </div>
              </div>
            </div>

            {/* Anchors */}
            {correlation?.anchors && correlation.anchors.length > 0 && (
              <div className="panel-card">
                <h3>Shared Entities (Why One Incident?)</h3>
                <p className="section-desc">Brain 1 identified these entities as incident anchors — the shared context across all signals.</p>
                <div className="anchors-row">
                  {correlation.anchors.map((anchor, i) => (
                    <div key={i} className="anchor-pill">
                      <span className="anchor-type">{anchor.type}</span>
                      <strong>{anchor.value}</strong>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Correlation Edges */}
            <div className="panel-card">
              <h3>Correlation Edges — {correlation?.edges?.length ?? 0}</h3>
              <p className="section-desc">Each edge is a deterministic relationship that Brain 1 used to group signals into this incident.</p>
              {correlation?.edges && correlation.edges.length > 0 ? (
                <div className="edges-list">
                  {correlation.edges.map((edge, i) => (
                    <div key={i} className="edge-card">
                      <div className="edge-reasons-row">
                        {edge.reasons.map((r, j) => (
                          <span key={j} className="reason-tag">{r.replace(/_/g, ' ')}</span>
                        ))}
                        <span className="edge-score-pill">Score {edge.score}</span>
                      </div>
                      {/* Technical detail: collapsed by default */}
                      <button
                        className="expand-link"
                        onClick={() => setEdgeDetailsExpanded(!edgeDetailsExpanded)}
                      >
                        {edgeDetailsExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        Signal IDs
                      </button>
                      {edgeDetailsExpanded && (
                        <div className="edge-signal-ids">
                          <span className="sig-id">{edge.left_signal_id}</span>
                          <span className="sig-sep">↔</span>
                          <span className="sig-id">{edge.right_signal_id}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state-message">No correlation edges available.</div>
              )}
            </div>
          </div>
        )}

        {/* ─── INVESTIGATE (BRAIN 2 — COGNITIVE ORDER) ─── */}
        {activeTab === 'INVESTIGATE' && (
          <div className="investigate-tab-layout">
            {brain2Status === 'SUCCEEDED' && investigation ? (
              <>
                {/* 1. INCIDENT UNDERSTANDING */}
                <div className="inv-section">
                  <div className="inv-section-header">
                    <span className="inv-step-num">1</span>
                    <h3>Incident Understanding</h3>
                    <span className="badge-ai-inline">AI ADVISORY</span>
                  </div>
                  <p className="inv-narrative">{investigation.incident_narrative || <span className="empty-val">Not available</span>}</p>
                </div>

                {/* 2. PRIMARY HYPOTHESIS */}
                <div className="inv-section">
                  <div className="inv-section-header">
                    <span className="inv-step-num">2</span>
                    <h3>Primary Hypothesis</h3>
                    {investigation.confidence !== undefined && (
                      <span className="hc-conf-badge">{investigation.confidence}% Confidence</span>
                    )}
                  </div>
                  <blockquote className="hypothesis-quote">
                    {investigation.primary_hypothesis || <span className="empty-val">Not available</span>}
                  </blockquote>

                  {((investigation.confidence_drivers?.length ?? 0) > 0 || (investigation.confidence_reducers?.length ?? 0) > 0) && (
                    <>
                      <button className="expand-link" onClick={() => setConfExpanded(!confExpanded)}>
                        {confExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        Why this confidence?
                      </button>
                      {confExpanded && (
                        <div className="conf-breakdown">
                          {investigation.confidence_drivers && investigation.confidence_drivers.length > 0 && (
                            <div className="conf-group">
                              <span className="conf-group-lbl conf-positive">Drivers</span>
                              {investigation.confidence_drivers.map((d, i) => <div key={i} className="conf-item conf-pos-item">+ {d}</div>)}
                            </div>
                          )}
                          {investigation.confidence_reducers && investigation.confidence_reducers.length > 0 && (
                            <div className="conf-group">
                              <span className="conf-group-lbl conf-negative">Reducers</span>
                              {investigation.confidence_reducers.map((d, i) => <div key={i} className="conf-item conf-neg-item">- {d}</div>)}
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>

                {/* 3. SUPPORTING EVIDENCE */}
                <div className="inv-section">
                  <div className="inv-section-header">
                    <span className="inv-step-num">3</span>
                    <h3>Supporting Evidence</h3>
                    <span className="count-pill-sm">{investigation.supporting_evidence?.length ?? 0}</span>
                  </div>
                  {investigation.supporting_evidence && investigation.supporting_evidence.length > 0 ? (
                    <div className="ev-item-list">
                      {investigation.supporting_evidence.map((se, i) => (
                        <div key={i} className="ev-item-row">
                          <CheckCircle2 size={14} className="ev-icon-support" />
                          <span className="ev-badge">{se.evidence_ref}</span>
                          <span className="ev-text">{se.reason}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-state-message">No supporting evidence identified.</div>
                  )}
                </div>

                {/* 4. CONTRADICTING EVIDENCE */}
                <div className="inv-section">
                  <div className="inv-section-header">
                    <span className="inv-step-num">4</span>
                    <h3>Contradicting Evidence</h3>
                    <span className="count-pill-sm">{investigation.contradicting_evidence?.length ?? 0}</span>
                  </div>
                  {investigation.contradicting_evidence && investigation.contradicting_evidence.length > 0 ? (
                    <div className="ev-item-list">
                      {investigation.contradicting_evidence.map((ce, i) => (
                        <div key={i} className="ev-item-row">
                          <XCircle size={14} className="ev-icon-contra" />
                          <span className="ev-badge">{ce.evidence_ref}</span>
                          <span className="ev-text">{ce.reason}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-state-message">No contradicting evidence identified in the available evidence.</div>
                  )}
                </div>

                {/* 5. MISSING EVIDENCE */}
                <div className="inv-section">
                  <div className="inv-section-header">
                    <span className="inv-step-num">5</span>
                    <h3>Missing Evidence</h3>
                    <span className="count-pill-sm">{investigation.missing_evidence?.length ?? 0}</span>
                  </div>
                  {investigation.missing_evidence && investigation.missing_evidence.length > 0 ? (
                    <div className="ev-item-list">
                      {investigation.missing_evidence.map((me, i) => (
                        <div key={i} className="ev-item-row">
                          <HelpCircle size={14} className="ev-icon-missing" />
                          <div className="missing-detail">
                            <strong>{me.evidence_type}</strong>
                            <span>{me.reason}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-state-message">No missing evidence identified.</div>
                  )}
                </div>

                {/* 6. ALL INVESTIGATION ACTIONS */}
                <div className="inv-section">
                  <div className="inv-section-header">
                    <span className="inv-step-num">6</span>
                    <h3>Investigation Actions</h3>
                    <span className="count-pill-sm">{investigation.next_best_actions?.length ?? 0}</span>
                  </div>
                  {investigation.next_best_actions && investigation.next_best_actions.length > 0 ? (
                    <div className="actions-list">
                      {investigation.next_best_actions.map((action, i) => (
                        <div key={i} className={`action-card ${i === 0 ? 'action-card-primary' : ''}`}>
                          {i === 0 && <div className="action-priority-flag">★ PRIMARY</div>}
                          <div className="action-type"><Terminal size={13} /> {action.action_type}</div>
                          <p className="action-reason">{action.reason}</p>
                          {action.supporting_evidence_refs && action.supporting_evidence_refs.length > 0 && (
                            <div className="action-refs">
                              {action.supporting_evidence_refs.map((r, j) => (
                                <span key={j} className="ev-badge">{r}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-state-message">No investigation actions provided.</div>
                  )}
                </div>

                {/* MITRE ATT&CK — collapsed by default */}
                {investigation.attack_hypotheses && investigation.attack_hypotheses.length > 0 && (
                  <div className="inv-section inv-section-collapsed">
                    <button className="expand-link expand-link-section" onClick={() => setMitreExpanded(!mitreExpanded)}>
                      {mitreExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      MITRE ATT&CK Hypotheses ({investigation.attack_hypotheses.length})
                    </button>
                    {mitreExpanded && (
                      <div className="mitre-pills-grid" style={{ marginTop: '10px' }}>
                        {investigation.attack_hypotheses.map((att, i) => (
                          <div key={i} className="mitre-chip">
                            <strong className="mitre-id">{att.technique_id}</strong>
                            {att.technique_name && <span className="mitre-name">{att.technique_name}</span>}
                            {att.evidence_refs && (
                              <span className="mitre-conf">Ev: {att.evidence_refs.join(', ')}</span>
                            )}
                            {att.confidence && <span className="mitre-conf">{att.confidence}</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Limitations — collapsed */}
                {investigation.limitations && investigation.limitations !== 'None' && (
                  <div className="inv-section inv-section-collapsed">
                    <button className="expand-link expand-link-section" onClick={() => setLimitationsExpanded(!limitationsExpanded)}>
                      {limitationsExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      Analysis Limitations
                    </button>
                    {limitationsExpanded && (
                      <p className="limitations-text">{investigation.limitations}</p>
                    )}
                  </div>
                )}
              </>
            ) : brain2Status === 'NONE' ? (
              <div className="empty-state-center">
                <AlertCircle size={36} className="empty-icon" />
                <h3>AI Investigation Not Run</h3>
                <p>Brain 2 has not analyzed this incident. Run the investigation to get hypothesis, evidence analysis, and investigation actions.</p>
                <button className="primary-btn-action" onClick={handleInvestigate} disabled={investigating}>
                  <Play size={14} /> Run AI Investigation
                </button>
              </div>
            ) : (brain2Status === 'PENDING' || brain2Status === 'RUNNING') ? (
              <div className="empty-state-center">
                <Loader2 size={36} className="spin empty-icon" />
                <h3>Investigation {brain2Status === 'PENDING' ? 'Queued' : 'Running'}</h3>
                <p>Analyzing privacy-safe evidence package...</p>
              </div>
            ) : brain2Status === 'FAILED' ? (
              <div className="empty-state-center">
                <XCircle size={36} className="empty-icon icon-error" />
                <h3>AI Investigation Failed</h3>
                <p>The investigation could not be completed. Brain 1 evidence remains available in the Evidence tab.</p>
              </div>
            ) : brain2Status === 'STALE' ? (
              <div className="empty-state-center">
                <AlertCircle size={36} className="empty-icon icon-warn" />
                <h3>Stale Investigation</h3>
                <p>The incident has changed since this investigation was run. Re-run to get current results.</p>
                <button className="primary-btn-action" onClick={handleInvestigate} disabled={investigating}>
                  <Play size={14} /> Re-Run Investigation
                </button>
              </div>
            ) : (
              <div className="empty-state-message">Not available.</div>
            )}
          </div>
        )}

        {/* ─── RESPOND ─── */}
        {activeTab === 'RESPOND' && (
          <div className="respond-tab-layout">
            <div className="respond-header-card">
              <Shield size={18} />
              <div>
                <h3>Response Recommendations</h3>
                <p>Advisory actions for analyst consideration. All actions require explicit SOC analyst approval before execution.</p>
              </div>
              <span className="approval-required-badge">ANALYST APPROVAL REQUIRED</span>
            </div>

            {brain2Status === 'SUCCEEDED' && investigation?.response_considerations && investigation.response_considerations.length > 0 ? (
              <div className="respond-list">
                {investigation.response_considerations.map((rec, i) => (
                  <div key={i} className="respond-card">
                    <div className="respond-num">{i + 1}</div>
                    <div className="respond-content">
                      <p className="respond-text">{rec}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : brain2Status === 'SUCCEEDED' ? (
              <div className="empty-state-message">No response recommendations provided by the investigation.</div>
            ) : brain2Status === 'NONE' ? (
              <div className="empty-state-center">
                <Shield size={36} className="empty-icon" />
                <h3>No Response Recommendations</h3>
                <p>Run AI investigation to generate response guidance.</p>
                <button className="primary-btn-action" onClick={handleInvestigate} disabled={investigating}>
                  <Play size={14} /> Run AI Investigation
                </button>
              </div>
            ) : (
              <div className="empty-state-message">AI investigation not yet complete.</div>
            )}
          </div>
        )}

        {/* ─── PAST CASES (NOT IMPLEMENTED) ─── */}
        {activeTab === 'PAST_CASES' && (
          <div className="not-implemented-layout">
            <BookOpen size={40} className="ni-icon" />
            <h3>Organizational Memory — Not Configured</h3>
            <p>
              When enabled, SentinelOps will surface similar past incidents, analyst dispositions,
              and actions that resolved comparable threats.
            </p>
            <div className="ni-capability-list">
              <div className="ni-cap-item"><CheckCircle2 size={14} /> Similar approved cases</div>
              <div className="ni-cap-item"><CheckCircle2 size={14} /> Past analyst dispositions</div>
              <div className="ni-cap-item"><CheckCircle2 size={14} /> Actions that worked</div>
              <div className="ni-cap-item"><CheckCircle2 size={14} /> Lessons learned</div>
            </div>
            <span className="ni-status-badge">NOT CONFIGURED</span>
          </div>
        )}

        {/* ─── PREVENT (NOT IMPLEMENTED) ─── */}
        {activeTab === 'PREVENT' && (
          <div className="not-implemented-layout">
            <Lightbulb size={40} className="ni-icon" />
            <h3>Prevention Advisor — Not Configured</h3>
            <p>
              After this incident is resolved, Prevention Advisor will recommend systemic improvements
              to reduce the likelihood and impact of similar future incidents.
            </p>
            <div className="ni-capability-list">
              <div className="ni-cap-item"><CheckCircle2 size={14} /> Detection gap recommendations</div>
              <div className="ni-cap-item"><CheckCircle2 size={14} /> Visibility improvements</div>
              <div className="ni-cap-item"><CheckCircle2 size={14} /> Identity &amp; endpoint control suggestions</div>
              <div className="ni-cap-item"><CheckCircle2 size={14} /> Playbook improvements</div>
            </div>
            <span className="ni-status-badge">NOT CONFIGURED</span>
          </div>
        )}

        {/* ─── PRIVACY ─── */}
        {activeTab === 'PRIVACY' && (
          <div className="privacy-tab-layout">
            <div className="pipeline-header">
              <h2><ShieldCheck size={18} /> Privacy Gateway</h2>
              <p>SentinelOps minimizes sensitive evidence before any external AI provider can receive it.</p>
            </div>

            <div className="trust-pipeline-card">
              <div className="trust-node">
                <Lock size={18} />
                <span>LOCAL INCIDENT</span>
                <small>{privacyPreview?.audit_card?.total_raw_telemetry ?? 0} Raw Alerts</small>
              </div>
              <div className="trust-arrow">→</div>
              <div className="trust-node highlight-node">
                <ShieldCheck size={18} />
                <span>PRIVACY GATEWAY</span>
                <small>Tokenized &amp; Redacted</small>
              </div>
              <div className="trust-arrow">→</div>
              <div className="trust-node">
                <FileText size={18} />
                <span>AI-SAFE PACKAGE</span>
                <small>{privacyPreview?.audit_card?.evidence_exported ?? 0} Minimized Signals</small>
              </div>
              <div className="trust-arrow">→</div>
              <div className="trust-node">
                <Cpu size={18} />
                <span>BRAIN 2</span>
              </div>
            </div>

            {privacyPreview?.audit_card ? (
              <div className="process-trace-card">
                <h3>Inference Audit</h3>
                <div className="pt-grid">
                  <div className="pt-item"><span className="pt-label">Provider:</span><span className="pt-val">{privacyPreview.audit_card.provider}</span></div>
                  <div className="pt-item"><span className="pt-label">Model:</span><span className="pt-val">{privacyPreview.audit_card.model}</span></div>
                  <div className="pt-item"><span className="pt-label">Privacy Profile:</span><span className="pt-val">{privacyPreview.audit_card.privacy_profile}</span></div>
                  <div className="pt-item"><span className="pt-label">Package Fingerprint:</span><span className="pt-val" style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{privacyPreview.audit_card.package_fingerprint}</span></div>
                  <div className="pt-item"><span className="pt-label">Evidence Exported:</span><span className="pt-val pt-green">{privacyPreview.audit_card.evidence_exported}</span></div>
                  <div className="pt-item"><span className="pt-label">Raw Identifiers Detected:</span><span className="pt-val pt-green">{privacyPreview.audit_card.raw_identifiers_detected}</span></div>
                  <div className="pt-item"><span className="pt-label">Raw Events Exported:</span><span className="pt-val pt-green">{privacyPreview.audit_card.raw_events_exported}</span></div>
                  <div className="pt-item"><span className="pt-label">Internal UUIDs Exported:</span><span className="pt-val pt-green">{privacyPreview.audit_card.internal_uuids_exported}</span></div>
                </div>
              </div>
            ) : (
              <div className="empty-state-message">Awaiting privacy preview data.</div>
            )}
          </div>
        )}
      </main>
    </div>
  );
};
