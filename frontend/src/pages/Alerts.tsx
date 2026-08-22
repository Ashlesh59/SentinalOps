import React, { useEffect, useState } from 'react';
import { getAlerts, type Alert } from '../api/alerts';
import { AlertTriangle } from 'lucide-react';
import './Incidents.css'; // Reuse table styles

export const Alerts: React.FC = () => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAlerts().then(data => {
      setAlerts(data);
    }).catch(e => {
      console.error(e);
    }).finally(() => {
      setLoading(false);
    });
  }, []);

  if (loading) return <div>Loading alerts...</div>;

  return (
    <div className="incidents-page">
      <div className="page-header">
        <h1>Normalized Alerts</h1>
      </div>

      {alerts.length === 0 ? (
        <div className="empty-state">
          <AlertTriangle size={48} />
          <p>No alerts found.</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Severity</th>
                <th>Source</th>
                <th>Category</th>
                <th>Alert Type</th>
                <th>User</th>
                <th>Host</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map(a => (
                <tr key={a.id}>
                  <td>{new Date(a.timestamp).toLocaleString()}</td>
                  <td><span className={`sev-badge sev-${a.severity.toLowerCase()}`}>{a.severity}</span></td>
                  <td>{a.source_product}</td>
                  <td>{a.category_name}</td>
                  <td>{a.alert_type}</td>
                  <td>{a.user || '-'}</td>
                  <td>{a.host || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
