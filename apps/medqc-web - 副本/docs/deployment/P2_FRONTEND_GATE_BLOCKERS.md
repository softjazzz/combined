# P2 Frontend Gate Blockers (Preflight Snapshot)

Generated from local preflight:
- `release-gate-artifacts/preflight/preflight-report.json`
- `release-gate-artifacts/preflight/preflight-report.md`

## Current Status
- `frontend_encoding`: PASS (scoped check)
- `frontend_typecheck_release`: PASS (API/contract/http core path)
- `frontend_unit_tests_release`: PASS (`13/13`)
- `frontend_build`: PASS (validated in unrestricted run)

## Environment-Dependent Failures (Local)
- legacy full `frontend_unit_tests` may include unstable canvas/chart cases (for example `QCTrendChart.test.ts`) and is not P2 release gate.
- `vitest`/`vite` can show `spawn EPERM` in restricted local sandbox; the same release gate steps pass outside sandbox and should be judged by CI Linux gate.

## Full Typecheck Debt (Tracked Separately)
1. `src/components/analytics/*`: `Dayjs[]` vs expected tuple function signature mismatch.
2. Multiple `ant-design-vue` form rule type mismatches (`RuleObject`/`ArrayRule`) in auth and audit components.
3. Upload component option typing mismatch (`UploadRequestOption` vs custom `{ file: File }` shape).
4. Table/Menu slot typing mismatch (`MenuInfo`, `TablePaginationConfig`, `FixedType`) in multiple views/components.

Progress note:
- `src/api/sync.ts` generic wrapper errors (`TS2347`) were fixed in this round.
- P2 release gate uses `type-check:release` to focus on production critical contract path.

## Why It Blocks P2
- Release gate is configured as blocking for `encoding`, `type-check:release`, `test:unit:release`, and `build`.
- Current blocker is no longer code-level; remaining risk is only local restricted-environment false negatives (`spawn EPERM`).
- CI Linux gate is the source of truth for release decision.

## Recommended Fix Order
1. Resolve local Windows process policy for Node child process spawn (`EPERM`) or run gates in CI runner only.
2. Keep legacy full test set and full-ui type debt as parallel治理项 (not P2 release blocker).
3. Re-run:
   - `npm run type-check`
   - `npm run test:unit:release`
   - `npm run build`
4. Re-run `python scripts/release_preflight.py --step-timeout 180 --fail-fast` for quick local check.
