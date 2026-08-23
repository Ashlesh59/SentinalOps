import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload as UploadIcon,
  FileJson,
  FileText,
  CheckCircle,
  XCircle,
  Loader2,
  AlertTriangle,
  ArrowRight,
  Play,
  Shield,
  Layers,
  Cpu,
  Database,
} from 'lucide-react';
import './Upload.css';

const API_BASE = 'http://localhost:8000/api/v1';
const TENANT_ID = 'tenant-test';

interface ImportJob {
  id: string;
  filename: string;
  format: string;
  status: string;
  records_received: number | null;
  records_parsed: number | null;
  parse_failed: number | null;
  raw_records_stored: number | null;
  normalized: number | null;
  normalization_failed: number | null;
  unsupported: number | null;
  error_message: string | null;
}

interface Incident {
  incident_id: string;
  title: string;
  severity: string;
}

// Stage definition for the pipeline trace
interface Stage {
  id: string;
  label: string;
  icon: React.ReactNode;
  getValue: (job: ImportJob) => string | null;
  isComplete: (job: ImportJob) => boolean;
  isRunning: (job: ImportJob) => boolean;
  isFailed: (job: ImportJob) => boolean;
  isUnavailable?: (job: ImportJob) => boolean;
}

const PIPELINE_STAGES: Stage[] = [
  {
    id: 'received',
    label: 'FILE RECEIVED',
    icon: <UploadIcon size={14} />,
    getValue: (job) => job.filename ? `${job.filename}  ·  ${job.format || 'Detecting...'}` : null,
    isComplete: (job) => job.records_received !== null,
    isRunning: (job) => job.status === 'PROCESSING' && job.records_received === null,
    isFailed: (job) => job.status === 'FAILED' && job.records_received === null,
  },
  {
    id: 'parsing',
    label: 'PARSING',
    icon: <FileText size={14} />,
    getValue: (job) => job.records_received !== null
      ? `${job.records_parsed ?? 0} parsed  ·  ${job.parse_failed ?? 0} failed`
      : null,
    isComplete: (job) => job.records_parsed !== null,
    isRunning: (job) => job.status === 'PROCESSING' && job.records_parsed === null,
    isFailed: (job) => (job.parse_failed ?? 0) > 0 && (job.normalized ?? 0) === 0,
  },
  {
    id: 'raw',
    label: 'RAW EVIDENCE',
    icon: <Database size={14} />,
    getValue: (job) => job.raw_records_stored !== null
      ? `${job.raw_records_stored} events stored`
      : null,
    isComplete: (job) => job.raw_records_stored !== null,
    isRunning: (job) => job.status === 'PROCESSING' && job.records_parsed !== null && job.raw_records_stored === null,
    isFailed: () => false,
  },
  {
    id: 'normalization',
    label: 'NORMALIZATION',
    icon: <Layers size={14} />,
    getValue: (job) => job.normalized !== null
      ? `${job.normalized} normalized  ·  ${job.normalization_failed ?? 0} failed  ·  ${job.unsupported ?? 0} unsupported`
      : null,
    isComplete: (job) => (job.status === 'COMPLETED' || job.status === 'PARTIAL') && job.normalized !== null,
    isRunning: (job) => job.status === 'PROCESSING',
    isFailed: (job) => job.status === 'FAILED',
  },
  {
    id: 'brain1',
    label: 'BRAIN 1 — DETERMINISTIC CORRELATION',
    icon: <Layers size={14} />,
    getValue: () => null,
    isComplete: (job) => job.status === 'COMPLETED' || job.status === 'PARTIAL',
    isRunning: (job) => job.status === 'PROCESSING',
    isFailed: (job) => job.status === 'FAILED',
  },
];

export const Upload: React.FC = () => {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [sourceHint, setSourceHint] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [incident, setIncident] = useState<Incident | null>(null);
  const [demoRunning, setDemoRunning] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Stop polling when terminal state
  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  // Poll import status
  useEffect(() => {
    if (!jobId) return;

    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/imports/${jobId}?tenant_id=${TENANT_ID}`);
        if (res.ok) {
          const data: ImportJob = await res.json();
          setJob(data);
          if (data.status === 'COMPLETED' || data.status === 'FAILED' || data.status === 'PARTIAL') {
            stopPolling();
            setUploading(false);
            // Fetch latest incident after completion
            if (data.status === 'COMPLETED' || data.status === 'PARTIAL') {
              fetchLatestIncident();
            }
          }
        }
      } catch (err) {
        console.error('Failed to fetch job status', err);
      }
    };

    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 1200);
    return stopPolling;
  }, [jobId]);

  const fetchLatestIncident = async () => {
    try {
      const res = await fetch(`${API_BASE}/incidents?tenant_id=${TENANT_ID}`);
      if (res.ok) {
        const data: Incident[] = await res.json();
        if (data.length > 0) setIncident(data[0]);
      }
    } catch (e) {
      console.error('Could not fetch incidents', e);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setJobId(null);
      setJob(null);
      setError(null);
      setIncident(null);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files[0];
    if (dropped) {
      setFile(dropped);
      setJobId(null);
      setJob(null);
      setError(null);
      setIncident(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    setJob(null);
    setIncident(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('tenant_id', TENANT_ID);
    if (sourceHint) formData.append('source_hint', sourceHint);

    try {
      const res = await fetch(`${API_BASE}/imports`, { method: 'POST', body: formData });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Upload failed');
      }
      const data = await res.json();
      setJobId(data.import_id);
    } catch (err: any) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      setUploading(false);
    }
  };

  const handleRunDemo = async () => {
    setDemoRunning(true);
    setError(null);
    setJob(null);
    setJobId(null);
    setIncident(null);
    try {
      const res = await fetch(`${API_BASE}/demo/scenarios/attack-chain`, { method: 'POST' });
      if (!res.ok) throw new Error('Demo scenario failed');
      // Demo runs synchronously — fetch latest incident immediately
      await fetchLatestIncident();
    } catch (err: any) {
      setError(err instanceof Error ? err.message : 'Demo failed');
    } finally {
      setDemoRunning(false);
    }
  };

  const getFileIcon = () => {
    if (!file) return <UploadIcon size={14} />;
    return file.name.endsWith('.csv') ? <FileText size={14} /> : <FileJson size={14} />;
  };

  const overallStatus = job?.status ?? (jobId ? 'PROCESSING' : null);

  const getStageStatus = (stage: Stage): 'complete' | 'running' | 'failed' | 'unavailable' | 'pending' => {
    if (!job) return jobId ? 'running' : 'pending';
    if (stage.isFailed(job)) return 'failed';
    if (stage.isComplete(job)) return 'complete';
    if (stage.isRunning(job)) return 'running';
    return 'pending';
  };

  return (
    <div className="upload-page">
      <header className="page-header">
        <div>
          <h1>Upload &amp; Analyze</h1>
          <p className="page-subtitle">
            Analyze security telemetry through the real SentinelOps pipeline.
          </p>
        </div>
        <button
          className="demo-btn"
          onClick={handleRunDemo}
          disabled={demoRunning}
          id="btn-run-demo-upload"
        >
          <Play size={16} />
          {demoRunning ? 'Injecting Demo Telemetry...' : 'Run Demo Scenario (22 Events)'}
        </button>
      </header>

      <div className="upload-body">
        {/* Upload Zone */}
        <div
          className={`upload-zone ${file ? 'has-file' : ''}`}
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
        >
          <UploadIcon size={36} className="upload-icon-large" />
          <h3>Drop CSV / JSON / JSONL here</h3>
          <p className="upload-hint">Supported formats: .csv, .json, .jsonl — Max 50 MB</p>

          <input
            type="file"
            id="file-upload"
            className="file-input"
            accept=".csv,.json,.jsonl,.ndjson"
            onChange={handleFileChange}
          />
          <label htmlFor="file-upload" className="btn btn-secondary">
            Browse Files
          </label>

          {file && (
            <div className="selected-file">
              {getFileIcon()}
              <span className="sf-name">{file.name}</span>
              <span className="sf-size">{(file.size / 1024).toFixed(1)} KB</span>
            </div>
          )}

          {/* Source hint selector */}
          <div className="source-row">
            <label className="source-label">Source Type (optional):</label>
            <select
              className="source-select"
              value={sourceHint}
              onChange={(e) => setSourceHint(e.target.value)}
            >
              <option value="">AUTO</option>
              <option value="IAM">IAM</option>
              <option value="XDR">XDR</option>
              <option value="FIREWALL">FIREWALL</option>
              <option value="SENTINELOPS_CANONICAL">SENTINELOPS CANONICAL</option>
            </select>
          </div>

          <button
            className="btn btn-primary upload-btn"
            disabled={!file || uploading || !!jobId}
            onClick={handleUpload}
          >
            {uploading ? <><Loader2 size={16} className="spinning" /> Uploading...</> : 'UPLOAD & ANALYZE'}
          </button>

          {error && <div className="upload-error">{error}</div>}
        </div>

        {/* Live Analysis Pipeline */}
        {(jobId || demoRunning || incident) && (
          <div className="pipeline-trace-panel">
            <div className="pt-panel-header">
              <h2>
                {demoRunning && !incident ? (
                  <><Loader2 size={16} className="spinning" /> RUNNING DEMO SCENARIO</>
                ) : overallStatus === 'COMPLETED' || incident ? (
                  <><CheckCircle size={16} className="icon-success" /> ANALYSIS COMPLETE</>
                ) : overallStatus === 'PARTIAL' ? (
                  <><AlertTriangle size={16} className="icon-warning" /> ANALYSIS PARTIAL</>
                ) : overallStatus === 'FAILED' ? (
                  <><XCircle size={16} className="icon-error" /> ANALYSIS FAILED</>
                ) : (
                  <><Loader2 size={16} className="spinning" /> LIVE ANALYSIS PIPELINE</>
                )}
              </h2>
            </div>

            {/* Only show stage trace for file uploads (not demo shortcut) */}
            {jobId && (
              <div className="stage-list">
                {PIPELINE_STAGES.map((stage) => {
                  const status = getStageStatus(stage);
                  const value = job ? stage.getValue(job) : null;
                  return (
                    <div key={stage.id} className={`stage-row stage-${status}`}>
                      <div className="stage-status-icon">
                        {status === 'complete' && <CheckCircle size={16} className="icon-success" />}
                        {status === 'running' && <Loader2 size={16} className="spinning icon-running" />}
                        {status === 'failed' && <XCircle size={16} className="icon-error" />}
                        {status === 'pending' && <span className="stage-dot" />}
                      </div>
                      <div className="stage-info">
                        <span className="stage-label">{stage.label}</span>
                        {value && <span className="stage-val">{value}</span>}
                        {status === 'failed' && job?.error_message && (
                          <span className="stage-err">{job.error_message}</span>
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* Brain 2 — always shown as NOT RUN (explicit action required) */}
                <div className="stage-row stage-pending">
                  <div className="stage-status-icon">
                    <span className="stage-dot" />
                  </div>
                  <div className="stage-info">
                    <span className="stage-label"><Cpu size={14} /> BRAIN 2 — AI INVESTIGATION</span>
                    <span className="stage-val stage-advisory">
                      Not run automatically. Open incident → Investigation tab to trigger.
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Demo scenario: no job id, just show incident result */}
            {!jobId && demoRunning && (
              <div className="stage-list">
                <div className="stage-row stage-running">
                  <div className="stage-status-icon"><Loader2 size={16} className="spinning" /></div>
                  <div className="stage-info">
                    <span className="stage-label">Running attack chain through SentinelOps pipeline...</span>
                  </div>
                </div>
              </div>
            )}

            {/* Metrics summary after file import */}
            {job && (job.status === 'COMPLETED' || job.status === 'PARTIAL') && (
              <div className="import-metrics-summary">
                <div className="ims-row">
                  <span className="ims-label">Events Received</span>
                  <strong>{job.records_received ?? 0}</strong>
                </div>
                <div className="ims-row">
                  <span className="ims-label">Raw Stored</span>
                  <strong>{job.raw_records_stored ?? 0}</strong>
                </div>
                <div className="ims-row">
                  <span className="ims-label">Normalized</span>
                  <strong className="val-good">{job.normalized ?? 0}</strong>
                </div>
                {(job.normalization_failed ?? 0) > 0 && (
                  <div className="ims-row">
                    <span className="ims-label">Normalization Failed</span>
                    <strong className="val-warn">{job.normalization_failed}</strong>
                  </div>
                )}
                {(job.unsupported ?? 0) > 0 && (
                  <div className="ims-row">
                    <span className="ims-label">Unsupported Format</span>
                    <strong className="val-warn">{job.unsupported}</strong>
                  </div>
                )}
                <div className="ims-row">
                  <span className="ims-label">Brain 2</span>
                  <strong>NOT RUN — Explicit Action Required</strong>
                </div>
              </div>
            )}

            {/* Open Incident CTA */}
            {incident && (
              <div className="incident-cta">
                <div className="cta-info">
                  <Shield size={18} />
                  <div>
                    <div className="cta-title">Incident Ready</div>
                    <div className="cta-sub">
                      <span className={`sev-badge sev-${incident.severity.toLowerCase()}`}>{incident.severity}</span>
                      {' '}{incident.title}
                    </div>
                  </div>
                </div>
                <button
                  className="btn btn-primary cta-btn"
                  onClick={() => navigate(`/incidents/${incident.incident_id}`)}
                >
                  Open Incident <ArrowRight size={14} />
                </button>
              </div>
            )}
          </div>
        )}

        {/* HOW SENTINELOPS WORKS — Judge Mode */}
        {!jobId && !demoRunning && !incident && (
          <div className="judge-mode-panel">
            <h3>How SentinelOps Handles This Data</h3>
            <ol className="judge-steps">
              <li>Security telemetry enters SentinelOps through the verified ingestion pipeline.</li>
              <li>Original evidence is persisted as raw records before any transformation.</li>
              <li>Vendor data is normalized using source-specific normalizers (IAM, XDR, Firewall).</li>
              <li>
                <strong>Brain 1</strong> deterministically compresses and correlates related activity.
                Forensic evidence is preserved; duplicate detections are consolidated.
              </li>
              <li>An explainable incident is created with full correlation reasoning.</li>
              <li>
                <strong>Privacy Gateway</strong> prepares an AI-safe evidence package, tokenizing identifiers before any external provider receives them.
              </li>
              <li>
                <strong>Brain 2</strong> investigates the safe package and returns validated, evidence-grounded recommendations.
                This step requires explicit analyst action.
              </li>
              <li>Analyst receives a traceable investigation with Next Best Action, Missing Evidence, and Response Recommendations.</li>
            </ol>
            <p className="judge-note">
              Demo AI provider in use. Vendor-neutral architecture demonstrated with IAM, XDR, and Firewall telemetry.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
