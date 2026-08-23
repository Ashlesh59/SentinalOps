import time
from typing import Dict, Any, Optional

class PipelineTracker:
    def __init__(self):
        self.pipeline_id: Optional[str] = None
        self.status: str = "IDLE"  # IDLE, RUNNING, COMPLETED, FAILED
        self.pipeline_type: str = "DEMO_ATTACK_CHAIN"
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.current_stage: str = "IDLE"
        self.stage_timings: Dict[str, float] = {}
        self.stage_durations: Dict[str, float] = {}
        self.metrics: Dict[str, Any] = {
            "raw_events": 0,
            "normalized_alerts": 0,
            "analytical_signals": 0,
            "correlated_incidents": 0,
        }

    def start_pipeline(self, pipeline_type: str = "DEMO_ATTACK_CHAIN"):
        self.pipeline_type = pipeline_type
        self.status = "RUNNING"
        self.start_time = time.perf_counter()
        self.end_time = 0.0
        self.stage_timings = {}
        self.stage_durations = {}
        self.current_stage = "RECEIVING_TELEMETRY"
        self.stage_timings["RECEIVING_TELEMETRY"] = time.perf_counter()

    def advance_stage(self, from_stage: str, to_stage: str):
        now = time.perf_counter()
        if from_stage in self.stage_timings:
            duration_ms = (now - self.stage_timings[from_stage]) * 1000.0
            self.stage_durations[from_stage] = round(duration_ms, 1)
        self.current_stage = to_stage
        self.stage_timings[to_stage] = now

    def complete_pipeline(self, metrics: Optional[Dict[str, Any]] = None):
        now = time.perf_counter()
        if self.current_stage in self.stage_timings:
            duration_ms = (now - self.stage_timings[self.current_stage]) * 1000.0
            self.stage_durations[self.current_stage] = round(duration_ms, 1)
        
        self.status = "COMPLETED"
        self.current_stage = "COMPLETE"
        self.end_time = now
        if metrics:
            self.metrics.update(metrics)

    def fail_pipeline(self, error_message: str):
        self.status = "FAILED"
        self.current_stage = "FAILED"
        self.end_time = time.perf_counter()

    def get_status(self) -> Dict[str, Any]:
        stages_definition = [
            {"id": "RECEIVING_TELEMETRY", "label": "Receiving Security Telemetry"},
            {"id": "NORMALIZING_EVIDENCE", "label": "Normalizing Evidence"},
            {"id": "BRAIN1_CORRELATION", "label": "Brain 1 Correlation"},
            {"id": "PRIVACY_PREPARATION", "label": "Privacy Preparation"},
            {"id": "BRAIN2_INVESTIGATION", "label": "Brain 2 Investigation"},
            {"id": "COMPLETE", "label": "Complete"},
        ]

        stage_order = [s["id"] for s in stages_definition]
        current_idx = stage_order.index(self.current_stage) if self.current_stage in stage_order else (len(stage_order) - 1 if self.status == "COMPLETED" else -1)

        processed_stages = []
        for idx, s in enumerate(stages_definition):
            s_id = s["id"]
            if self.status == "IDLE":
                stage_status = "idle"
            elif self.status == "COMPLETED":
                stage_status = "completed"
            elif self.status == "FAILED":
                if idx < current_idx:
                    stage_status = "completed"
                elif idx == current_idx:
                    stage_status = "failed"
                else:
                    stage_status = "pending"
            else: # RUNNING
                if idx < current_idx:
                    stage_status = "completed"
                elif idx == current_idx:
                    stage_status = "running"
                else:
                    stage_status = "pending"

            duration = self.stage_durations.get(s_id)
            processed_stages.append({
                "id": s_id,
                "label": s["label"],
                "status": stage_status,
                "duration_ms": duration
            })

        total_ms = 0.0
        if self.start_time > 0:
            end = self.end_time if self.end_time > 0 else time.perf_counter()
            total_ms = round((end - self.start_time) * 1000.0, 1)

        return {
            "status": self.status,
            "pipeline_type": self.pipeline_type,
            "current_stage": self.current_stage,
            "total_duration_ms": total_ms,
            "stages": processed_stages,
            "metrics": self.metrics
        }

pipeline_tracker = PipelineTracker()
