import React, { useEffect, useState } from 'react';
import { getSystemHealth, type SystemHealth } from '../api/system';
import './Overview.css';

export const System: React.FC = () => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSystemHealth().then(data => {
      setHealth(data);
    }).catch(e => {
      console.error(e);
    }).finally(() => {
      setLoading(false);
    });
  }, []);

  if (loading) return <div>Loading system health...</div>;
  if (!health) return <div>Error loading system health.</div>;

  return (
    <div className="overview-page">
      <div className="page-header">
        <h1>System Health</h1>
      </div>

      <div className="panel">
        <h2>Operational Status</h2>
        
        <div className="dist-list">
          <div className="dist-item">
            <span>Backend API</span>
            <span className="dist-count">{health.api}</span>
          </div>
          <div className="dist-item">
            <span>PostgreSQL</span>
            <span className="dist-count">{health.database}</span>
          </div>
          <div className="dist-item">
            <span>Brain 1 (Deterministic Engine)</span>
            <span className="dist-count">{health.brain1}</span>
          </div>
          <div className="dist-item">
            <span>Privacy Gateway</span>
            <span className="dist-count">{health.privacy_gateway}</span>
          </div>
          <div className="dist-item">
            <span>Brain 2 Provider</span>
            <span className="dist-count">{health.brain2_provider}</span>
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Configuration</h2>
        <div className="dist-list">
          <div className="dist-item">
            <span>Configured AI Provider</span>
            <span className="dist-count">{health.provider_config.name}</span>
          </div>
          <div className="dist-item">
            <span>Configured Model</span>
            <span className="dist-count">{health.provider_config.model}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
