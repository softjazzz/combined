# P2-QA-02 Final Capacity Commitment Report

## Run Information

| Field | Value |
| --- | --- |
| Scenario | medqc-release-capacity-mix |
| Scenario Description | Core MedQC mix covering health, sync read/write, preflight and qc analyze paths. |
| Base URL | http://127.0.0.1:64957 |
| Auth Token Provided | No |
| Concurrency Ladder | 1, 2, 3 |
| Step Duration | 3s |
| Thresholds | P95 <= 300 ms, Error Rate <= 5.00% |
| Safety Factor | 0.8 |

## Step Results

| Step | VUs | QPS | P95 (ms) | Error Rate | Result | Violations |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 9.00 | 248.63 | 0.00% | PASS | - |
| 2 | 2 | 24.00 | 246.38 | 0.00% | PASS | - |
| 3 | 3 | 26.33 | 245.56 | 0.00% | PASS | - |

## Final Commitment

| Field | Value |
| --- | --- |
| Stable VUs | 3 |
| Stable QPS | 26.33 |
| Capacity Commitment QPS | 21 |
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
| Summary JSON | D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\reports\perf\capacity-final-2026-03-26T07-46-32-763Z\capacity-final-summary.json |
| Markdown Report | D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\reports\perf\capacity-final-2026-03-26T07-46-32-763Z\capacity-final-report.md |
| Step Reports | D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\reports\perf\capacity-final-2026-03-26T07-46-32-763Z\steps\step-01-vus-1\perf-baseline-2026-03-26T07-46-32-767Z.json<br>D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\reports\perf\capacity-final-2026-03-26T07-46-32-763Z\steps\step-02-vus-2\perf-baseline-2026-03-26T07-46-35-828Z.json<br>D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\reports\perf\capacity-final-2026-03-26T07-46-32-763Z\steps\step-03-vus-3\perf-baseline-2026-03-26T07-46-38-987Z.json |
