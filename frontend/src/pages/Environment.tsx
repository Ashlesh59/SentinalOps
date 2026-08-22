import React from 'react';
import { DEMO_TENANT_ID } from '../api/client';
import './Overview.css';

export const Environment: React.FC = () => {
  return (
    <div className="overview-page">
      <div className="page-header">
        <h1>Environment</h1>
      </div>

      <div className="panel">
        <h2>Tenant Security Context</h2>
        <p className="subtitle">Tenant: {DEMO_TENANT_ID}</p>
        
        <div className="dist-list">
          <div className="dist-item">
            <span>Known Service Accounts</span>
            <span className="dist-count" style={{color: 'var(--text-muted)'}}>Not configured</span>
          </div>
          <div className="dist-item">
            <span>Known NAT/VPN Gateways</span>
            <span className="dist-count" style={{color: 'var(--text-muted)'}}>Not configured</span>
          </div>
          <div className="dist-item">
            <span>Critical Assets</span>
            <span className="dist-count" style={{color: 'var(--text-muted)'}}>Not configured</span>
          </div>
          <div className="dist-item">
            <span>Current Correlation Policy</span>
            <span className="dist-count">corr-v2</span>
          </div>
        </div>
      </div>
    </div>
  );
};
