import React, { useState, useEffect } from 'react';
import { Upload as UploadIcon, FileJson, FileText, CheckCircle, XCircle, Loader2, AlertTriangle } from 'lucide-react';
const API_BASE = 'http://localhost:8000/api/v1';
import './Upload.css';

interface ImportJob {
    id: string;
    filename: string;
    format: string;
    status: string;
    records_received: number;
    records_parsed: number;
    parse_failed: number;
    raw_records_stored: number;
    normalized: number;
    normalization_failed: number;
    unsupported: number;
    error_message: string | null;
}

export const Upload: React.FC = () => {
    const [file, setFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [jobId, setJobId] = useState<string | null>(null);
    const [job, setJob] = useState<ImportJob | null>(null);
    const [error, setError] = useState<string | null>(null);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            setFile(e.target.files[0]);
            setJobId(null);
            setJob(null);
            setError(null);
        }
    };

    const handleUpload = async () => {
        if (!file) return;
        setUploading(true);
        setError(null);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('tenant_id', 'tenant-test');

        try {
            const res = await fetch(`${API_BASE}/imports`, {
                method: 'POST',
                body: formData,
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || 'Upload failed');
            }
            const data = await res.json();
            setJobId(data.import_id);
        } catch (err: any) {
            console.error('Upload failed:', err);
            setError(err instanceof Error ? err.message : 'Upload failed');
            setUploading(false);
        }
    };

    useEffect(() => {
        let interval: ReturnType<typeof setInterval>;
        
        const fetchStatus = async () => {
            if (!jobId) return;
            try {
                const res = await fetch(`${API_BASE}/imports/${jobId}`);
                if (res.ok) {
                    const data = await res.json();
                    setJob(data);
                    if (data.status === 'COMPLETED' || data.status === 'FAILED' || data.status === 'PARTIAL') {
                        clearInterval(interval);
                    }
                }
            } catch (err) {
                console.error("Failed to fetch job status", err);
            }
        };

        if (jobId) {
            fetchStatus();
            interval = setInterval(fetchStatus, 1000);
        }

        return () => {
            if (interval) clearInterval(interval);
        };
    }, [jobId]);

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'COMPLETED': return <CheckCircle className="status-icon success" />;
            case 'PARTIAL': return <AlertTriangle className="status-icon warning" />;
            case 'FAILED': return <XCircle className="status-icon error" />;
            default: return <Loader2 className="status-icon spinning" />;
        }
    };

    return (
        <div className="upload-page">
            <header className="page-header">
                <h1>Upload & Analyze</h1>
                <p>Ingest security data from CSV, JSON, or JSONL files.</p>
            </header>

            <div className="upload-container">
                <div className="upload-zone">
                    <UploadIcon size={48} className="upload-icon-large" />
                    <h3>Select a file to upload</h3>
                    <p className="upload-hint">Supported formats: .csv, .json, .jsonl (Max 50MB)</p>
                    
                    <input 
                        type="file" 
                        id="file-upload" 
                        className="file-input" 
                        accept=".csv,.json,.jsonl,.ndjson" 
                        onChange={handleFileChange} 
                    />
                    <label htmlFor="file-upload" className="btn btn-secondary">Browse Files</label>
                    
                    {file && (
                        <div className="selected-file">
                            {file.name.endsWith('.csv') ? <FileText size={20}/> : <FileJson size={20}/>}
                            <span>{file.name}</span>
                            <span className="file-size">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
                        </div>
                    )}
                    
                    <button 
                        className="btn btn-primary upload-btn" 
                        disabled={!file || uploading || !!jobId}
                        onClick={handleUpload}
                    >
                        {uploading ? 'Uploading...' : 'Start Upload'}
                    </button>
                    
                    {error && <div className="upload-error">{error}</div>}
                </div>

                {jobId && (
                    <div className="job-status-panel">
                        <div className="job-header">
                            <h3>Analysis Trace</h3>
                            {job && getStatusIcon(job.status)}
                        </div>
                        
                        {!job ? (
                            <p className="loading-text">Initializing import job...</p>
                        ) : (
                            <div className="job-metrics">
                                <div className="metric-row">
                                    <span className="metric-label">Status</span>
                                    <span className={`status-badge ${job.status.toLowerCase()}`}>{job.status}</span>
                                </div>
                                <div className="metric-row">
                                    <span className="metric-label">Detected Format</span>
                                    <span className="metric-value font-mono">{job.format}</span>
                                </div>
                                
                                <div className="metric-grid">
                                    <div className="metric-card">
                                        <h4>Records Received</h4>
                                        <div className="metric-number">{job.records_received}</div>
                                    </div>
                                    <div className="metric-card">
                                        <h4>Raw Stored</h4>
                                        <div className="metric-number">{job.raw_records_stored}</div>
                                    </div>
                                    <div className="metric-card">
                                        <h4>Normalized</h4>
                                        <div className="metric-number success-text">{job.normalized}</div>
                                    </div>
                                    <div className="metric-card">
                                        <h4>Failed</h4>
                                        <div className="metric-number error-text">{job.parse_failed + job.normalization_failed}</div>
                                    </div>
                                </div>
                                
                                {job.error_message && (
                                    <div className="job-error-msg">
                                        <strong>Error:</strong> {job.error_message}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
