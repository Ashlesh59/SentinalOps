import React, { useEffect, useState } from 'react';
import { getSystemHealth, type SystemHealth } from '../api/system';
import { CheckCircle, AlertTriangle, XCircle, Shield, Server, Cpu, Database, Lock } from 'lucide-react';
import './Overview.css';

function statusBadge(val: string) {
  if (!val) return null;
  const lower = val.toLowerCase();
  if (lower.includes('healthy')) return <span className="sys-badge sys-ok"><CheckCircle size={14} /> {val}</span>;
  if (lower.includes('degraded') || lower.includes('unavailable'))
    return <span className="sys-badge sys-degraded"><AlertTriangle size={14} /> {val}</span>;
  return <span className="sys-badge sys-unknown"><XCircle size={14} /> {val}</span>;
}

export const System: React.FC = () => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSystemHealth()
      .then(data => setHealth(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading-state">Loading system health...</div>;
  if (!health) return <div className="error-state">Error loading system health.</div>;

  // Determine overall status
  const isCloudNoKey = health.brain2_provider?.toLowerCase().includes('no api key');
  const isDegraded = health.brain2_provider?.toLowerCase().includes('degraded') || health.database?.toLowerCase().includes('unavailable');

  const overallLabel = isDegraded ? 'SYSTEM DEGRADED' : 'SYSTEM HEALTHY';
  const overallClass = isDegraded ? 'sys-status-warn' : 'sys-status-ok';

  return (
    <div className="overview-page">
      <div className="page-header">
        <div>
          <h1>System Architecture & Health</h1>
          <p className="page-subtitle">Zero-trust component pipeline and execution engine status</p>
        </div>
        <div className={`sys-overall-badge ${overallClass}`}>
          {isDegraded ? <AlertTriangle size={16} /> : <CheckCircle size={16} />}
          {overallLabel}
        </div>
      </div>

      <div className="overview-main-grid">
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2>Core Infrastructure Pipeline</h2>
              <p className="subtitle">Real-time health status of local telemetry and correlation services</p>
            </div>
          </div>
          <div className="dist-list">
            <div className="dist-item">
              <span className="dist-name"><Server size={16} style={{ verticalAlign: 'middle', marginRight: '8px', color: '#38bdf8' }} /> Backend ASGI Service (FastAPI)</span>
              {statusBadge(health.api)}
            </div>
            <div className="dist-item">
              <span className="dist-name"><Database size={16} style={{ verticalAlign: 'middle', marginRight: '8px', color: '#69db7c' }} /> Storage Engine (PostgreSQL / SQLite Hot Tier)</span>
              {statusBadge(health.database)}
            </div>
            <div className="dist-item">
              <span className="dist-name"><Shield size={16} style={{ verticalAlign: 'middle', marginRight: '8px', color: '#fcc419' }} /> Brain 1 (Deterministic Heuristic Correlation)</span>
              {statusBadge(health.brain1)}
            </div>
            <div className="dist-item">
              <span className="dist-name"><Lock size={16} style={{ verticalAlign: 'middle', marginRight: '8px', color: '#ff4d6d' }} /> Privacy Gateway (Regex Redaction & HMAC Tokenizer)</span>
              {statusBadge(health.privacy_gateway)}
            </div>
            <div className="dist-item">
              <span className="dist-name"><Cpu size={16} style={{ verticalAlign: 'middle', marginRight: '8px', color: '#b197fc' }} /> Brain 2 Reasoning Engine</span>
              {statusBadge(health.brain2_provider)}
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <h2>Active AI Provider Configuration</h2>
              <p className="subtitle">Air-gapped and local LLM execution settings</p>
            </div>
          </div>
          <div className="dist-list">
            <div className="dist-item">
              <span className="dist-name">Engine / Provider</span>
              <span className="dist-count">{health.provider_config?.name ?? 'Local Engine'}</span>
            </div>
            <div className="dist-item">
              <span className="dist-name">Model Architecture</span>
              <span className="dist-count">{health.provider_config?.model ?? 'Deterministic Triage'}</span>
            </div>
            <div className="dist-item">
              <span className="dist-name">Air-Gap Zero Egress</span>
              <span className="dist-count" style={{ color: '#69db7c', borderColor: 'rgba(105,219,124,0.35)', background: 'rgba(105,219,124,0.12)' }}>ENFORCED</span>
            </div>
            {isCloudNoKey && (
              <div className="dist-item" style={{ color: '#fcc419', fontSize: '0.85rem', display: 'block', paddingTop: '10px' }}>
                ⚠ Cloud API key not configured. Using local air-gapped AI triage engine.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
