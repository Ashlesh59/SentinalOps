class Brain1Metrics:
    def __init__(self):
        self.alerts_newly_processed = 0
        self.duplicates_detected = 0
        self.signals_created = 0
        self.signals_updated = 0
        self.candidate_queries = 0
        self.candidate_pairs = 0
        self.pairs_scored = 0
        self.edges_created = 0
        self.incidents_created = 0
        self.incident_memberships_added = 0
        self.db_query_count = 0
        self.run_duration_ms = 0.0
        self.max_candidate_set_size = 0
        self.candidate_set_truncated = False
        self.candidate_rows_available = 0
        self.candidate_rows_evaluated = 0
