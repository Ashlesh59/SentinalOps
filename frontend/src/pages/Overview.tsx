import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getDashboardSummary, type DashboardSummary } from '../api/dashboard';
import { getIncidents, type Incident } from '../api/incidents';
import { getAlerts, type Alert } from '../api/alerts';
import { triggerDemoScenario } from '../api/demo';
import { Play, ShieldAlert, AlertTriangle, Cpu, ArrowRight, ArrowDown, ShieldCheck, Layers, Terminal } from 'lucide-react';
import './Overview.css';

export const Overview: React.FC = () => {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [recentAlerts, setRecentAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [demoRunning, setDemoRunning] = useState(false);
  const navigate = useNavigate();

  const fetchData = async () => {
    try {
      const [sumData, incData, alertData] = await Promise.all([
        getDashboardSummary(),
        getIncidents(),
        getAlerts().catch(() => [])
      ]);
      setSummary(sumData);
      setIncidents(incData);
      setRecentAlerts(alertData.slice(0, 5));
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const runDemo = async () => {
    setDemoRunning(true);
    try {
      await triggerDemoScenario();
      setTimeout(fetchData, 1200);
    } catch (e) {
      console.error(e);
      alert("Failed to run demo scenario.");
    } finally {
      setDemoRunning(false);
    }
  };

  if (loading) return <div className="loading-state">Loading SOC Overview...</div>;
  if (!summary) return <div className="error-state">Error loading dashboard summary.</div>;

  const topIncidents = incidents.slice(0, 5);

  return (
    <div className="overview-page">
      <div className="page-header">
        <div>
          <h1>SOC Security Overview</h1>
          <p className="page-subtitle">Deterministic correlation & AI advisory intelligence layer</p>
        </div>
        <button className="demo-btn" onClick={runDemo} disabled={demoRunning} id="btn-run-demo">
          <Play size={16} /> {demoRunning ? 'Injecting Telemetry & Brain 1...' : 'Run Demo Scenario (22 Events)'}
        </button>
      </div>

      {/* Top SOC Action KPIs */}
      <div className="kpi-grid">
        <div className="kpi-card critical">
          <div className="kpi-icon"><ShieldAlert size={24} /></div>
          <div className="kpi-info">
            <div className="kpi-title">Critical Incidents</div>
            <div className="kpi-val">{summary.critical_incidents}</div>
            <div className="kpi-sub">Immediate SOC Review</div>
          </div>
        </div>

        <div className="kpi-card warning">
          <div className="kpi-icon"><AlertTriangle size={24} /></div>
          <div className="kpi-info">
            <div className="kpi-title">HIGH+ Severity</div>
            <div className="kpi-val">{summary.high_priority_incidents}</div>
            <div className="kpi-sub">Incidents (HIGH or CRITICAL)</div>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-icon"><Cpu size={24} /></div>
          <div className="kpi-info">
            <div className="kpi-title">AI Investigations</div>
            <div className="kpi-val">{summary.investigations_succeeded}</div>
            <div className="kpi-sub">Completed AI investigations</div>
          </div>
        </div>

        <div className="kpi-card highlight">
          <div className="kpi-icon"><Layers size={24} /></div>
          <div className="kpi-info">
            <div className="kpi-title">Noise Reduction</div>
            <div className="kpi-val">
              {summary.noise_reduction_percent}%
            </div>
            <div className="kpi-sub">{summary.normalized_alerts} alerts → {summary.analytical_signals} signals</div>
          </div>
        </div>
      </div>

      {/* Main Attention Panels */}
      <div className="overview-main-grid">
        {/* Left Column: Top Incidents & Recent Ingested Telemetry */}
        <div className="overview-left-col">
          <div className="panel attention-panel">
            <div className="panel-header">
              <div>
                <h2>Top Incidents Requiring Attention</h2>
                <p className="subtitle">Prioritized security incidents derived deterministically by Brain 1</p>
              </div>
              <button className="text-btn" onClick={() => navigate('/incidents')}>
                View All Queue ({incidents.length}) <ArrowRight size={14} />
              </button>
            </div>

            {topIncidents.length === 0 ? (
              <div className="empty-panel">
                <ShieldCheck size={44} />
                <p>No open incidents requiring attention.</p>
                <button className="secondary-btn" onClick={runDemo}>Inject Attack Chain Telemetry</button>
              </div>
            ) : (
              <div className="incident-cards-list">
                {topIncidents.map((inc) => {
                  const ref = inc.reference;
                  const userAnchor = inc.anchor_entities?.USER?.[0];
                  return (
                    <div 
                      key={inc.incident_id} 
                      className={`incident-attention-card sev-border-${inc.severity.toLowerCase()}`}
                      onClick={() => navigate(`/incidents/${inc.incident_id}`)}
                    >
                      <div className="iac-left">
                        <div className="iac-header">
                          <span className="iac-ref">{ref}</span>
                          <span className={`sev-badge sev-${inc.severity.toLowerCase()}`}>{inc.severity}</span>
                          {inc.priority && (
                            <span className={`pri-badge pri-${inc.priority.toLowerCase()}`}>
                              Priority: {inc.priority}
                            </span>
                          )}
                          <span className="iac-status">{inc.status}</span>
                        </div>
                        <div className="iac-title">{inc.title}</div>
                        <div className="iac-meta">
                          {userAnchor ? <span><strong>Affected:</strong> {userAnchor}</span> : <span className="empty-val">Affected: N/A</span>}
                          <span>•</span>
                          <span><strong>Duration:</strong> {inc.duration}</span>
                          <span>•</span>
                          <span><strong>Sources:</strong> {inc.sources?.length ? inc.sources.join(', ') : 'Security Telemetry'}</span>
                          <span>•</span>
                          <span><strong>Signals:</strong> {inc.signal_count} ({inc.evidence_count} Alerts)</span>
                        </div>
                      </div>
                      <div className="iac-right">
                        <div className="iac-b2-status">
                          <span className="b2-lbl">Brain 2:</span>
                          <span className={`b2-badge b2-${inc.brain2_status.toLowerCase()}`}>
                            {inc.brain2_status}
                          </span>
                        </div>
                        <button className="investigate-link-btn">
                          Investigate <ArrowRight size={14} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Recent Normalized Telemetry Feed */}
          {recentAlerts.length > 0 && (
            <div className="panel alerts-feed-panel">
              <div className="panel-header">
                <div>
                  <h2>Live Normalized Telemetry Feed</h2>
                  <p className="subtitle">Real-time normalized security events feeding Brain 1 aggregation</p>
                </div>
                <button className="text-btn" onClick={() => navigate('/alerts')}>
                  View All Alerts ({summary.normalized_alerts}) <ArrowRight size={14} />
                </button>
              </div>
              <div className="mini-alerts-list">
                {recentAlerts.map((alert) => (
                  <div key={alert.id} className="mini-alert-item">
                    <div className="mai-left">
                      <span className={`sev-badge sev-${alert.severity.toLowerCase()}`}>{alert.severity}</span>
                      <span className="mai-vendor">{alert.source_product || 'Agent'}</span>
                      <strong className="mai-type">{alert.alert_type}</strong>
                    </div>
                    <div className="mai-right">
                      {alert.user && <span className="mai-entity"><Terminal size={12} /> {alert.user}</span>}
                      <span className="mai-time">{new Date(alert.timestamp).toLocaleTimeString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Truthful Reduction & Source Breakdown */}
        <div className="overview-side-col">
          {/* Noise Reduction Flow */}
          <div className="panel">
            <h2>Deterministic Compression</h2>
            <p className="subtitle">Forensics preserved while duplicate alerts are consolidated</p>
            <div className="reduction-flow">
              <div className="reduction-step">
                <span className="num">{summary.normalized_alerts}</span>
                <span className="lbl">Raw Ingested Alerts</span>
              </div>
              <div className="arrow"><ArrowDown size={18} /></div>
              <div className="reduction-step">
                <span className="num">{summary.analytical_signals}</span>
                <span className="lbl">Deduplicated Signals</span>
              </div>
              <div className="arrow"><ArrowDown size={18} /></div>
              <div className="reduction-step highlight-step">
                <span className="num">{summary.open_incidents}</span>
                <span className="lbl">Correlated Incident</span>
              </div>
            </div>
            <div className="reduction-stat">
              <strong>{summary.noise_reduction_percent}%</strong>
              <span>Analytical Compression
                <span style={{ display: 'block', fontSize: '0.74rem', color: '#868e96', marginTop: '4px' }}>
                  Formula: 1 − (signals ÷ alerts)
                </span>
              </span>
            </div>
          </div>

          {/* Telemetry Sources */}
          <div className="panel">
            <h2>Telemetry Sources</h2>
            <p className="subtitle">Connected security product detections</p>
            <div className="dist-list">
              {Object.entries(summary.source_distribution || {}).map(([src, count]) => (
                <div key={src} className="dist-item">
                  <span className="dist-name">{src}</span>
                  <span className="dist-count">{count} alerts</span>
                </div>
              ))}
              {Object.keys(summary.source_distribution || {}).length === 0 && (
                <div className="empty-sub">No telemetry ingested yet.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
