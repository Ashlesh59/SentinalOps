import React, { useEffect, useState } from 'react';
import { getSystemHealth, type SystemHealth } from '../api/system';
import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react';
import './Overview.css';

function statusBadge(val: string) {
  if (!val) return null;
  const lower = val.toLowerCase();
  if (lower === 'healthy') return <span className="sys-badge sys-ok"><CheckCircle size={13} /> {val}</span>;
  if (lower.includes('degraded') || lower.includes('unavailable'))
    return <span className="sys-badge sys-degraded"><AlertTriangle size={13} /> {val}</span>;
  return <span className="sys-badge sys-unknown"><XCircle size={13} /> {val}</span>;
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

  // Determine overall status label
  const brain2Degraded = health.brain2_provider?.toLowerCase().includes('degraded')
    || health.brain2_provider?.toLowerCase().includes('no api key');
  const coreHealthy =
    health.api?.toLowerCase() === 'healthy' &&
    health.database?.toLowerCase() === 'healthy' &&
    health.brain1?.toLowerCase() === 'healthy' &&
    health.privacy_gateway?.toLowerCase() === 'healthy';

  const overallLabel = coreHealthy
    ? brain2Degraded ? 'CORE HEALTHY — Brain 2 Degraded' : 'SYSTEM HEALTHY'
    : 'SYSTEM DEGRADED';

  const overallClass = coreHealthy
    ? brain2Degraded ? 'sys-status-warn' : 'sys-status-ok'
    : 'sys-status-fail';

  return (
    <div className="overview-page">
      <div className="page-header">
        <div>
          <h1>System Health</h1>
          <div className={`sys-overall-badge ${overallClass}`}>{overallLabel}</div>
        </div>
      </div>

      <div className="panel">
        <h2>Operational Status</h2>
        <div className="dist-list">
          <div className="dist-item">
            <span>Backend API</span>
            {statusBadge(health.api)}
          </div>
          <div className="dist-item">
            <span>PostgreSQL</span>
            {statusBadge(health.database)}
          </div>
          <div className="dist-item">
            <span>Brain 1 — Deterministic Correlation</span>
            {statusBadge(health.brain1)}
          </div>
          <div className="dist-item">
            <span>Privacy Gateway</span>
            {statusBadge(health.privacy_gateway)}
          </div>
          <div className="dist-item">
            <span>Brain 2 Provider</span>
            {statusBadge(health.brain2_provider)}
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Configured AI Provider</h2>
        <div className="dist-list">
          <div className="dist-item">
            <span>Provider</span>
            <span className="dist-count">{health.provider_config?.name ?? 'Unknown'}</span>
          </div>
          <div className="dist-item">
            <span>Model</span>
            <span className="dist-count">{health.provider_config?.model ?? 'Unknown'}</span>
          </div>
          {brain2Degraded && (
            <div className="dist-item" style={{ color: '#fcc419', fontSize: '0.82rem', display: 'block', paddingTop: '8px' }}>
              ⚠ No API key configured. Brain 2 is unavailable for live AI investigation. Brain 1 and Privacy Gateway remain fully operational.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
