import React, { useEffect, useState } from 'react';
import { getPipelineStatus, type PipelineStatus } from '../api/system';
import { CheckCircle2, Loader2, Circle, Zap, Clock, ShieldCheck } from 'lucide-react';
import './LiveAnalysis.css';

interface LiveAnalysisProps {
  isTriggering?: boolean;
  onFinished?: () => void;
}

export const LiveAnalysis: React.FC<LiveAnalysisProps> = ({ isTriggering, onFinished }) => {
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [polling, setPolling] = useState(false);

  const fetchStatus = async () => {
    try {
      const data = await getPipelineStatus();
      setPipeline(data);
      if (data.status === 'RUNNING') {
        setPolling(true);
      } else {
        setPolling(false);
        if (data.status === 'COMPLETED' && onFinished) {
          onFinished();
        }
      }
    } catch (e) {
      console.error('Failed to fetch live pipeline status', e);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, [isTriggering]);

  useEffect(() => {
    let interval: any;
    if (polling || isTriggering) {
      interval = setInterval(() => {
        fetchStatus();
      }, 250);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [polling, isTriggering]);

  if (!pipeline || (pipeline.status === 'IDLE' && !isTriggering)) {
    return null;
  }

  const isRunning = pipeline.status === 'RUNNING' || isTriggering;
  const isCompleted = pipeline.status === 'COMPLETED' && !isTriggering;

  return (
    <div className={`live-analysis-card ${isRunning ? 'live-active' : ''} ${isCompleted ? 'live-done' : ''}`}>
      <div className="la-header">
        <div className="la-title-group">
          <div className="la-live-badge">
            <span className={`la-pulse-dot ${isRunning ? 'pulse' : 'steady'}`}></span>
            <strong>LIVE ANALYSIS</strong>
          </div>
          <span className="la-subtitle">Real-time backend pipeline state</span>
        </div>
        <div className="la-timer">
          <Clock size={13} />
          <span><strong>{pipeline.total_duration_ms > 0 ? `${pipeline.total_duration_ms}ms` : '< 100ms'}</strong></span>
        </div>
      </div>

      <div className="la-stages-list">
        {pipeline.stages.map((stage) => {
          const isStageDone = stage.status === 'completed';
          const isStageRunning = stage.status === 'running';

          return (
            <div 
              key={stage.id} 
              className={`la-stage-item ${isStageDone ? 'stage-done' : ''} ${isStageRunning ? 'stage-running' : ''}`}
            >
              <div className="la-stage-left">
                <div className="la-icon-box">
                  {isStageDone ? (
                    <CheckCircle2 size={16} className="la-icon-done" />
                  ) : isStageRunning ? (
                    <Loader2 size={16} className="la-icon-spin" />
                  ) : (
                    <Circle size={14} className="la-icon-pending" />
                  )}
                </div>
                <span className="la-stage-label">{stage.label}</span>
              </div>
              <div className="la-stage-right">
                {stage.duration_ms !== undefined && stage.duration_ms > 0 && (
                  <span className="la-stage-ms">{stage.duration_ms}ms</span>
                )}
                {isStageRunning && (
                  <span className="la-running-tag">PROCESSING</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {isCompleted && (
        <div className="la-completion-strip">
          <div className="la-comp-left">
            <ShieldCheck size={16} />
            <span>Pipeline Executed Successfully</span>
          </div>
          <div className="la-comp-speed">
            <Zap size={14} />
            <strong>{pipeline.total_duration_ms}ms total</strong>
          </div>
        </div>
      )}
    </div>
  );
};
