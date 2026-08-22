import React, { useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Upload as UploadIcon, Shield, Activity, AlertTriangle, LayoutDashboard, Server, Settings } from 'lucide-react';
import './Layout.css';
import { getSystemHealth } from '../api/system';
import { DEMO_TENANT_ID } from '../api/client';

export const Layout: React.FC = () => {
  const [sysHealthy, setSysHealthy] = useState(true);

  useEffect(() => {
    getSystemHealth().then(res => {
      if (res.api !== 'Healthy' || res.database !== 'Healthy') setSysHealthy(false);
    }).catch(() => setSysHealthy(false));
  }, []);

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2><Shield size={24} /> SentinelOps</h2>
        </div>
        
        <nav className="sidebar-nav">
          <NavLink to="/" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <LayoutDashboard size={20} /> Overview
          </NavLink>
          <NavLink to="/upload" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <UploadIcon size={20} /> Upload & Analyze
          </NavLink>
          <NavLink to="/incidents" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <Activity size={20} /> Incidents
          </NavLink>
          <NavLink to="/alerts" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <AlertTriangle size={20} /> Alerts
          </NavLink>
          <NavLink to="/environment" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <Settings size={20} /> Environment
          </NavLink>
          <NavLink to="/system" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <Server size={20} /> System
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <div className="tenant-badge">DEMO TENANT: {DEMO_TENANT_ID}</div>
          <p>Privacy-aware SOC intelligence</p>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="system-status">
            System {sysHealthy ? 'Healthy' : 'Degraded'}
            <div className="status-dot" style={{ backgroundColor: sysHealthy ? 'var(--status-low)' : 'var(--status-critical)' }}></div>
          </div>
        </header>
        <div className="content-area">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
