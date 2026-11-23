# MedQC P2 Release Runbook

## Goals
- Fixed build artifact deployment (no `pnpm dev`/`vite preview` in production).
- Atomic release switch with rollback.
- Fail-fast startup for critical dependencies.
- Minimal observability and release-gate traceability.

## Runtime Layout
- `/opt/medqc/releases/<release_id>`: immutable release payload
- `/opt/medqc/current`: symlink to active release
- `/opt/medqc/shared/backend.env`: backend production env/secrets
- `/opt/medqc/shared/frontend.env`: frontend runtime env

## One-Time Setup
```bash
cd /path/to/health-qc-monorepo/scripts
chmod +x install-services.sh
./install-services.sh
```

## Deploy New Release
```bash
cd /path/to/health-qc-monorepo/scripts
chmod +x deploy_medqc_release.sh
./deploy_medqc_release.sh 20260326-rc1
```

What this script does:
- Build frontend artifact (`apps/medqc-web/dist`).
- Package backend source + create release venv.
- Copy runtime scripts (`run_backend_prod.sh`, `run_frontend_prod.sh`).
- Switch `/opt/medqc/current` atomically.
- Restart `medqc-backend` and `medqc-frontend`.
- Probe `/api/v1/health` and `/api/v1/ready`.

## Rollback
```bash
cd /path/to/health-qc-monorepo/scripts
chmod +x rollback_medqc_release.sh
./rollback_medqc_release.sh <release_id>
```

## Observability Endpoints
- `GET /api/v1/health`
- `GET /api/v1/ready`
- `GET /api/v1/metrics`
- `GET /api/v1/metrics/prometheus` (Prometheus text exposition)

## Prometheus Scrape Config (Example)
```yaml
scrape_configs:
  - job_name: medqc-backend
    scrape_interval: 30s
    metrics_path: /api/v1/metrics/prometheus
    static_configs:
      - targets:
          - medqc-backend.internal:8001
```

Notes:
- `job` label comes from Prometheus scrape target/job config.
- `env` label is emitted by MedQC metric payload.
- Keep metric labels low-cardinality; do not add user/patient/request IDs as labels.

## Grafana Dashboards (P2-OBS-02)
- Core overview: `apps/medqc-web/ops/grafana/medqc-core-overview-dashboard.json`
- Sync deep-dive: `apps/medqc-web/ops/grafana/medqc-sync-deep-dive-dashboard.json`

Import steps:
1. In Grafana, open `Dashboards -> New -> Import`.
2. Upload each JSON file above.
3. Bind datasource variable `DS_PROMETHEUS` to your Prometheus datasource.
4. Save dashboard and set default variables `job=medqc-backend`, `env=production` (or your env).

## Metric Semantics (Core)
- `medqc_runtime_requests_per_second_1m` (gauge, req/s): rolling 1-minute QPS.
- `medqc_runtime_request_latency_p95_ms` (gauge, ms): request latency P95.
- `medqc_runtime_request_error_rate` (gauge, ratio 0..1): HTTP error ratio (`status>=400`).
- `medqc_runtime_status_bucket_total{code_class="5xx"}` (counter): 5xx bucket count.
- `medqc_sync_window_success_runs_total` (gauge, count): successful sync runs in rolling window.
- `medqc_sync_window_failed_runs_total` (gauge, count): failed sync runs in rolling window.
- `medqc_sync_failure_rate` (gauge, ratio 0..1): failed/total in rolling window.
- `medqc_sync_last_success_lag_seconds` (gauge, s): seconds since last successful sync.
- `medqc_sync_backlog_estimate` (gauge, count): backlog proxy metric derived from failed sync runs in rolling window.
  - This is an inferred indicator when no dedicated queue system exists.

## Minimal Alert Suggestions
- High 5xx ratio: `>5%` for 10m.
- High P95 latency: `>2000ms` for 10m.
- High sync failure rate: `>20%` for 15m.
- Sync lag high: `last_success_lag_seconds > 1800` for 15m.
- Backlog pressure: `medqc_sync_backlog_estimate > 20` for 15m (tune by baseline).

Recommended checks:
- readiness must be `200` before traffic switch.
- monitor `runtime.error_rate` and `runtime.avg_latency_ms`.
- monitor `qc.avg_api_time` trend for quality-control path saturation.
- scrape `medqc_runtime_request_latency_p95_ms` and `medqc_runtime_requests_per_second_1m`.
- scrape `medqc_sync_failure_rate` and `medqc_sync_last_success_lag_seconds`.

Example scheduled check:
```bash
cd /path/to/health-qc-monorepo/scripts
chmod +x monitor_medqc_slo.sh
./monitor_medqc_slo.sh
```

Threshold env vars (optional):
- `MAX_ERROR_RATE` (default `0.05`)
- `MAX_AVG_LATENCY_MS` (default `800`)
- `MAX_P95_LATENCY_MS` (default `1500`)
- `MAX_QC_AVG_API_TIME` (default `5`)
- Drill mode:
  - `SLO_DRILL_MODE=off|tighten|simulate_failure` (default `off`)
  - `SLO_DRILL_FAIL_REASON` (only for `simulate_failure`)
  - `DRILL_MAX_ERROR_RATE/DRILL_MAX_AVG_LATENCY_MS/DRILL_MAX_P95_LATENCY_MS/DRILL_MAX_QC_AVG_API_TIME` (only for `tighten`)

Alert rule template:
- `scripts/medqc_prometheus_alert_rules.yml`
- covers: backend down, 5xx rate, p95 latency, sync failure rate, sync lag

## OpenTelemetry (P2-OBS-01)
Backend now supports optional OpenTelemetry traces with fail-open bootstrap:
- disabled by default (`OTEL_ENABLED=false`)
- exporter misconfiguration/unreachable endpoint must not block service startup
- response shell `trace_id` and `X-Trace-ID` keep existing semantics

Local enable example:
```bash
cd /path/to/health-qc-monorepo/apps/medqc-web/backend

export OTEL_ENABLED=true
export OTEL_SERVICE_NAME=medqc-backend-local
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318/v1/traces
export OTEL_TRACES_SAMPLER=parentbased_always_on
export OTEL_TRACES_SAMPLER_ARG=1.0

uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Sampling options:
- `OTEL_TRACES_SAMPLER=parentbased_always_on` (default)
- `OTEL_TRACES_SAMPLER=always_on`
- `OTEL_TRACES_SAMPLER=always_off`
- `OTEL_TRACES_SAMPLER=traceidratio` + `OTEL_TRACES_SAMPLER_ARG=0.1`

## Alert Drill Procedure
Goal: run non-destructive alert drills with deterministic `PASS/FAIL` output from monitor script.

Trigger:
```bash
cd /path/to/health-qc-monorepo/scripts

# Scenario A: force a simulated failure (no data mutation)
SLO_DRILL_MODE=simulate_failure \
SLO_DRILL_FAIL_REASON="drill:simulated failure for alert pipeline" \
./monitor_medqc_slo.sh || true

# Scenario B: tighten thresholds to increase chance of FAIL on live metrics
SLO_DRILL_MODE=tighten \
DRILL_MAX_ERROR_RATE=0.0001 \
DRILL_MAX_AVG_LATENCY_MS=50 \
DRILL_MAX_P95_LATENCY_MS=100 \
DRILL_MAX_QC_AVG_API_TIME=0.5 \
./monitor_medqc_slo.sh || true
```

Observe:
- Script output must contain `RESULT=FAIL` and explicit `reason=...`.
- In monitoring stack, confirm related alert transitions (`pending`/`firing`) and notification delivery.
- Record drill time window and observed alert name/severity in release notes.

Recover:
```bash
cd /path/to/health-qc-monorepo/scripts
unset SLO_DRILL_MODE SLO_DRILL_FAIL_REASON
unset DRILL_MAX_ERROR_RATE DRILL_MAX_AVG_LATENCY_MS DRILL_MAX_P95_LATENCY_MS DRILL_MAX_QC_AVG_API_TIME
./monitor_medqc_slo.sh
```
- Verify output returns to `RESULT=PASS`.
- Close temporary drill event/ticket and attach evidence (script logs + alert timeline screenshot).

## CI Gate
- Use `.github/workflows/release-gate-medqc.yml` as blocking gate.
- Required results:
  - frontend gates = success
  - backend gates = success
  - release gate report artifact generated
- Backend gate now includes:
  - `scripts/check_alert_rules.py` (Prometheus alert rules integrity)
  - `tests/unit/test_observability_contract.py` (`/metrics` + `/metrics/prometheus` contract)

Frontend type-check scope in P2 gate:
- `type-check:release` (`tsconfig.release.json`)
- covers API/contract/http critical path first; full UI type debt is tracked separately.

Frontend unit-test scope in P2 gate:
- `test:unit:release` (`vitest.release.config.mjs`)
- covers API envelope/auth token/核心契约测试; legacy unstable UI test set is tracked separately.

## Performance Capacity Finalization

### Scope
- Core interface probe: `GET /api/v1/health`
- Sync read path: `GET /api/v1/sync/status`
- Sync readiness path: `POST /api/v1/sync/preflight`
- Sync write path: `POST /api/v1/sync/trigger`
- QC path: `POST /api/v1/qc/analyze/{record_id}`

### Finalization Command
Use the finalizer wrapper, not the single-step baseline, when you need the real capacity commitment:
```bash
cd /path/to/health-qc-monorepo/apps/medqc-web
npm run perf:finalize -- \
  --base-url=http://127.0.0.1:8001 \
  --auth-token=$AUTH_TOKEN \
  --concurrency-ladder=5,10,15,20 \
  --step-duration=2m \
  --max-p95-ms=500 \
  --max-error-rate=0.01
```

What this command does:
- runs the same MedQC request mix in ordered concurrency steps
- stops at the first failed step unless `--continue-on-fail` is set
- picks the last stable step that satisfies both thresholds
- applies a `0.8` safety factor to derive `capacity_commitment_qps`
- writes `capacity-final-summary.json` and `capacity-final-report.md` under `apps/medqc-web/reports/perf/<run-id>/`
- preserves each step's baseline report under `apps/medqc-web/reports/perf/<run-id>/steps/`

### Mock / Smoke Mode
For a fast local smoke run, use mock mode:
```bash
cd /path/to/health-qc-monorepo/apps/medqc-web
npm run perf:finalize:mock -- --concurrency-ladder=3,6,9 --step-duration=30s
```

This is only a process check. It is not a final release commitment unless the base URL points to the real target environment and the auth token matches the release role.

### Final Commitment Rule
Capacity commitment is the stable throughput you can promise after applying a safety margin.

Decision rule:
1. Execute the same request mix against the target environment.
2. Increase concurrency using the configured ladder.
3. For each step, require `P95 <= threshold` and `error_rate <= threshold`.
4. Choose the last step that passes both checks.
5. Compute `capacity_commitment_qps = floor(stable_qps * 0.8)`.

Interpretation rules:
- If `P95` misses target, that step is not part of the final commitment.
- If error rate rises, use the last clean step before the regression.
- If all steps pass, the last tested step is still only a validated ceiling, not a theoretical maximum.
- If mock/local and real environment differ materially, only the real environment can be used for sign-off.

### Output Fields
- Scenario name and request mix
- Concurrency ladder
- Step duration
- Thresholds
- Step-level QPS / P95 / error rate
- `stable_vus`
- `stable_qps`
- `capacity_commitment_qps`
- `applicable_conditions`
- `failure_conditions`

### Evidence
- Script command line used
- `apps/medqc-web/reports/perf/<run-id>/capacity-final-summary.json`
- `apps/medqc-web/reports/perf/<run-id>/capacity-final-report.md`
- Step reports under `apps/medqc-web/reports/perf/<run-id>/steps/`
- Reference template: `docs/deployment/perf-baseline-template.md`

## Local Preflight (Before Manual Release)
```bash
cd /path/to/health-qc-monorepo
python scripts/release_preflight.py --step-timeout 180 --fail-fast
```

Notes:
- preflight now prints step-level live progress (`START/END`) to avoid silent hangs.
- each step has a hard timeout (default `300s`, override via `--step-timeout`).
- for backend-only gate debug: `python apps/medqc-web/backend/scripts/release_gate_runner.py --gate-timeout 180 --fail-fast`.
- standalone alert rule check: `python apps/medqc-web/backend/scripts/check_alert_rules.py`.

Outputs:
- `release-gate-artifacts/preflight/preflight-report.json`
- `release-gate-artifacts/preflight/preflight-report.md`

If preflight frontend gates fail, see:
- `docs/deployment/P2_FRONTEND_GATE_BLOCKERS.md`

## Architecture Governance (P2-ARCH-03)
- ADR: `docs/architecture/ADR-2026-03-26-modular-boundaries.md`
- Ownership matrix: `docs/architecture/module_ownership_matrix.yaml`
- Scope:
  - defines owner roles for `auth/sync/drg/records`
  - defines dependency allow/deny rules
  - aligns release gate mandatory checks with architecture constraints
