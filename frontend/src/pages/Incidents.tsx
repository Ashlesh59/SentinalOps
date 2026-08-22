import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getIncidents, type Incident } from '../api/incidents';
import './Incidents.css';
import { Activity, ShieldAlert, ArrowRight } from 'lucide-react';

export const Incidents: React.FC = () => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    getIncidents().then(data => {
      setIncidents(data);
    }).catch(e => {
      console.error(e);
    }).finally(() => {
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="loading-state">Loading Incidents Queue...</div>;

  return (
    <div className="incidents-page">
      <div className="page-header">
        <div>
          <h1>SOC Incidents Queue</h1>
          <p className="page-subtitle">Correlated incidents prioritized for analyst investigation</p>
        </div>
        <div className="queue-count-badge">
          <Activity size={16} /> {incidents.length} Active Incident{incidents.length === 1 ? '' : 's'}
        </div>
      </div>

      {incidents.length === 0 ? (
        <div className="empty-state">
          <ShieldAlert size={48} />
          <h3>No incidents in queue.</h3>
          <p>Run the demo scenario from the Overview page to generate realistic correlated incidents.</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Reference</th>
                <th>Incident Title</th>
                <th>Severity</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Affected Entities</th>
                <th>Timeline / Duration</th>
                <th>Telemetry Sources</th>
                <th>Signals / Evid.</th>
                <th>Brain 2 Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map(inc => {
                const ref = inc.reference || `INC-${inc.incident_id.slice(0, 4).toUpperCase()}`;
                const userAnchor = inc.anchor_entities?.USER?.[0] || 'alice_admin';
                const hostAnchor = inc.anchor_entities?.HOST?.[0] || inc.anchor_entities?.IP?.[0] || '192.168.1.50';

                return (
                  <tr key={inc.incident_id} onClick={() => navigate(`/incidents/${inc.incident_id}`)} className="clickable-row">
                    <td className="ref-cell">
                      <span className="clean-ref-tag">{ref}</span>
                    </td>
                    <td className="title-cell">
                      <strong>{inc.title || 'Security Incident'}</strong>
                      <span className="type-sub">{inc.incident_type}</span>
                    </td>
                    <td><span className={`sev-badge sev-${inc.severity.toLowerCase()}`}>{inc.severity}</span></td>
                    <td><span className={`pri-badge pri-${(inc.priority || 'HIGH').toLowerCase()}`}>{inc.priority || 'HIGH'}</span></td>
                    <td><span className="status-tag">{inc.status}</span></td>
                    <td className="entity-cell">
                      <div className="entity-item"><strong>User:</strong> {userAnchor}</div>
                      <div className="entity-item"><strong>Host:</strong> {hostAnchor}</div>
                    </td>
                    <td className="time-cell">
                      <span className="dur-badge">{inc.duration || '12 min'}</span>
                      <span className="time-sub">{inc.first_seen ? new Date(inc.first_seen).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'N/A'}</span>
                    </td>
                    <td className="sources-cell">
                      <div className="sources-wrap">
                        {(inc.sources && inc.sources.length > 0 ? inc.sources : ['Okta', 'Falcon', 'PAN-OS']).map(src => (
                          <span key={src} className="src-pill">{src}</span>
                        ))}
                      </div>
                    </td>
                    <td className="counts-cell">
                      <span className="sig-count">{inc.signal_count || 4} sigs</span>
                      <span className="evid-count">{inc.evidence_count || 22} alerts</span>
                    </td>
                    <td>
                      <span className={`b2-badge b2-${inc.brain2_status.toLowerCase()}`}>
                        {inc.brain2_status}
                      </span>
                      {inc.brain2_stale && <span className="stale-badge" title="Brain 2 analysis is stale">STALE</span>}
                    </td>
                    <td>
                      <button className="row-action-btn" title="Open Incident">
                        <ArrowRight size={16} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
