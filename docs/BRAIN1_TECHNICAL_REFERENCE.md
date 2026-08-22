# Brain 1 Technical Reference

## Architecture & Call Flow
Brain 1 implements a deterministic incident correlation pipeline. The primary entry point is `run_correlation` in `src/brain1/engine.py`, triggered via the API (`POST /api/v1/correlation/run`).

**Call Flow**:
1. **Fetch Alerts**: Loads all `NormalizedAlertModel` records for a given `tenant_id`, ordered by timestamp and ID.
2. **Deduplication**: Calculates exact fingerprints (`generate_dedup_fingerprint`) and suppresses duplicates.
3. **Aggregation**: Groups alerts into `AggregatedSignalModel` windows.
4. **Candidate Search**: Narrows down pairs of signals that share entities.
5. **Correlation Scoring**: Scores candidate pairs. If score >= threshold, creates a `CorrelationEdgeModel`.
6. **Incident Matching**: Checks if signals should join active incidents or form a new `IncidentModel`.

## Files Structure
- `engine.py`: Main execution pipeline.
- `aggregation.py`: Logic for grouping alerts into signals.
- `correlation.py`: Pairwise scoring and candidate selection.
- `entities.py`: Extraction of atomic indicators (IPs, Hashes, etc.).
- `incident.py`: Logic for determining incident membership and keys.
- `fingerprinting.py`: Exact duplicate fingerprinting.

## Duplicate Logic
Implemented in `engine.py` (Phase 4 design).
- Generates a fingerprint.
- If fingerprint exists in the map, sets `duplicate_of_alert_id`, `dedup_fingerprint`, and `dedup_fingerprint_version` ("exact-v1").
- Suppresses the duplicate from further analytical flow.

## Aggregation
Implemented in `aggregation.py`.
- **Rule**: `agg-v1`
- **Window**: 60 minutes (`RULE_WINDOW_MINUTES = 60`).
- **Key Generation**: Concatenates tenant, alert type, user, host, src_ip, domain, process, and file_hash.
- **Behavior**: Consecutive alerts matching the key within 60 minutes extend the signal's `last_seen` and increment `occurrence_count`. Severity is promoted to "CRITICAL" if any constituent alert is "HIGH" or "CRITICAL".

## Entity Extraction
Implemented in `entities.py` (`extract_entities`).
- Extracts `USERS`, `DEVICES`, `IPS`, `DOMAINS`, `PROCESSES`, and `HASHES`.
- Deduplicates using sets.
- Defines `GENERIC_USERS` (e.g., `SYSTEM`, `LOCAL SERVICE`) which are ignored in some correlation logics.

## Candidate Selection
Implemented in `correlation.py` (`find_candidates`).
- Time Window: Restricts candidate pairs to those within a 7200 seconds (2 hours) delta of `first_seen`.
- Intersection: Only considers pairs sharing strong entities: `DEVICES`, `HASHES`, `USERS` (excluding generic), and `IPS`.

## Correlation Scoring
Implemented in `correlation.py` (`score_pair`).
- Threshold: 50 (`CORRELATION_THRESHOLD`). Rule: `corr-v1`.
- Scoring rules:
  - Shared Hash: +50
  - Shared Device: +40
  - Shared User (non-generic): +25
  - Shared IP: +15
  - Time Proximity <= 5 mins: +15
  - Time Proximity <= 60 mins: +5

## Incident Membership
Implemented in `incident.py` (`match_incident`).
- **Criteria**: A signal can join an incident if it shares at least one "anchor" entity (Device, Hash, non-generic User) with the incident AND forms a qualifying edge (>=50 score) with at least one existing member.
- **Tie-breakers**:
  1. Max pairwise edge score
  2. Anchor overlap count
  3. Earliest `first_seen`
  4. Immutable `incident_key` comparison

## Database Schema
Models defined in `src/db/models.py`:
- `RawEventModel`: Initial ingestion.
- `NormalizedAlertModel`: Contains dedup tracking fields.
- `AggregatedSignalModel`: Windows of alerts, stores JSON array of entities.
- `AggregatedSignalAlertModel`: Junction for Signal <-> Alert.
- `CorrelationEdgeModel`: Connects two signals with score and reasons.
- `IncidentModel`: High-level security incident, holds `anchor_entities`.
- `IncidentSignalModel`: Junction for Incident <-> Signal.

## API Endpoints
- `POST /api/v1/events`: Ingest raw events.
- `POST /api/v1/correlation/run`: Execute the pipeline for a tenant.
- `GET /api/v1/incidents`: Retrieve incidents for a tenant.

## Tests
Defined in `tests/test_correlation.py`.
- Uses `fixtures/ground_truth_p4.json`.
- Scenarios tested: A (real attack), B (exact duplicate), C (repeated burst), D (unrelated), E (benign admin), F (cross-tenant), G (shared IP), H (late arrival).

## Performance Bottlenecks & Scale Limits
- **Memory Limits**: The engine loads *all* alerts (`.all()`) and *all* incidents for a tenant into memory simultaneously. This will crash for high-volume tenants.
- **Time Complexity**: Candidate search uses O(N^2) loops over the signals in memory.
- **Database Overhead**: Nested loop queries inside `engine.py` (e.g. `_upsert_link`) lead to N+1 query problems.

## Security Risks
- Cross-tenant data leakage if API inputs or DB queries ever drop the `tenant_id` filter (though tested against in scenario F).
- Missing API pagination creates a potential Denial of Service (DoS) when requesting large volumes of incidents.

## Configuration & Indexes
- Configurations are hardcoded constants (e.g., `CORRELATION_THRESHOLD = 50`, `RULE_WINDOW_MINUTES = 60`).
- Basic indexes exist on `tenant_id` and `dedup_fingerprint`. Lacks composite indexes (e.g. `tenant_id` + `timestamp`), which will slow down the pipeline fetching phase.

## Research Questions
- How to implement a streaming or sliding-window approach instead of bulk-loading alerts?
- How to handle incident closure and archiving (no lifecycle rules exist yet)?
- How to transition from hardcoded rule thresholds to dynamic or machine-learning based models?
