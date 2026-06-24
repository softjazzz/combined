# P2-QA-02 Final Capacity Commitment Report

## Run Information

| Field | Value |
| --- | --- |
| Scenario | medqc-release-capacity-mix |
| Scenario Description | Core MedQC mix covering health, sync read/write, preflight and qc analyze paths. |
| Base URL | http://127.0.0.1:50878 |
| Auth Token Provided | No |
| Concurrency Ladder | 1, 2, 3 |
| Step Duration | 3s |
| Thresholds | P95 <= 300 ms, Error Rate <= 5.00% |
| Safety Factor | 0.8 |

## Step Results

| Step | VUs | QPS | P95 (ms) | Error Rate | Result | Violations |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 11.00 | 246.12 | 0.00% | PASS | - |
| 2 | 2 | 22.67 | 242.18 | 0.00% | PASS | - |
| 3 | 3 | 33.67 | 233.97 | 0.00% | PASS | - |

## Final Commitment

| Field | Value |
| --- | --- |
| Stable VUs | 3 |
| Stable QPS | 33.67 |
| Capacity Commitment QPS | 26 |
| Final Status | pass |
| Selected From | 3 |

## Applicable Conditions

- Base URL, auth token, build version and request mix must remain unchanged from this run.
- The same threshold policy must be applied: P95 and error rate must both stay within bounds.
- Use the same step duration and evaluate only the last stable step that passes all thresholds.
- Real environment results take precedence over mock or local runs for final sign-off.

## Failure Conditions

- 本次阶梯未出现阈值失效，但容量承诺仍只对已验证的最高稳定档位有效。

## Evidence

| Item | Path |
| --- | --- |
| Summary JSON | docs\deployment\P2-QA-02-capacity-commitment-2026-03-26\capacity-final-2026-03-26T07-45-18-589Z\capacity-final-summary.json |
| Markdown Report | docs\deployment\P2-QA-02-capacity-commitment-2026-03-26\capacity-final-2026-03-26T07-45-18-589Z\capacity-final-report.md |
| Step Reports | docs\deployment\P2-QA-02-capacity-commitment-2026-03-26\capacity-final-2026-03-26T07-45-18-589Z\steps\step-01-vus-1\perf-baseline-2026-03-26T07-45-18-592Z.json<br>docs\deployment\P2-QA-02-capacity-commitment-2026-03-26\capacity-final-2026-03-26T07-45-18-589Z\steps\step-02-vus-2\perf-baseline-2026-03-26T07-45-21-736Z.json<br>docs\deployment\P2-QA-02-capacity-commitment-2026-03-26\capacity-final-2026-03-26T07-45-18-589Z\steps\step-03-vus-3\perf-baseline-2026-03-26T07-45-24-871Z.json |
