# Full Tender Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring the MedQC platform from partial implementation to demonstrable tender-level coverage for frontpage generation, settlement list generation, QC rules, ICD coding, DRG/DIP grouping, payment monitoring, and comprehensive DRG/DIP analysis.

**Architecture:** Treat the tender clauses as acceptance contracts, not UI descriptions. Build a clause-to-code coverage matrix first, then close the missing production paths behind stable APIs, deterministic tests, and demo scripts. Keep formal writes separated from draft/simulation flows.

**Tech Stack:** Vue 3, TypeScript, Ant Design Vue, Python FastAPI, local ICD datasets, DRG/DIP grouping services, pytest, Vitest, npm quality gates.

---

## Scope And Non-Negotiables

- Do not write generated drafts into formal case frontpage, settlement, DRG, or DIP result tables unless the existing business flow explicitly requires it.
- Keep all AI extraction, pre-grouping, and payment simulation results marked as draft/simulation until reviewed.
- Do not expose raw fields such as `medical_text`, `documents`, `bundle`, `record_content`, `internal_data`, `prompt`, `raw_response`, `embedding`, or `vector`.
- Do not introduce `.vue.ts` mirror files.
- Do not make broad `any` changes in shared TypeScript types.
- Keep frontend API changes backward compatible.

---

## Milestone 0: Baseline Branch, Inventory, And Acceptance Matrix

### Task 0.1: Create Clause Coverage Matrix

**Files:**

- Create: `docs/acceptance/tender-coverage/coverage-matrix.md`
- Create: `docs/acceptance/tender-coverage/coverage-matrix.json`

**Steps:**

1. Write a row for each clause: `3.1.1`, `3.3.1`, `3.4.1`, `3.4.3`, `3.5.1`, `4.1.2`, `6.1.1`, `6.2.1`, `6.2.2`, `6.2.3`, `6.3.1`.
2. For each row record: `status`, `backend_files`, `frontend_files`, `data_sources`, `tests`, `demo_entry`, `gaps`, `owner`.
3. Mark current status as `implemented`, `partial`, or `missing`.
4. Commit only the matrix files.

**Checks:**

- `npm run check:encoding`

### Task 0.2: Add Static Evidence Script

**Files:**

- Create: `scripts/acceptance/collect_tender_evidence.py`
- Create: `tests/unit/test_tender_evidence_script.py`

**Steps:**

1. Write a script that reads `coverage-matrix.json`.
2. Validate that every referenced file exists.
3. Validate that every clause has at least one acceptance test or a documented gap.
4. Output `docs/acceptance/tender-coverage/evidence-report.json`.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_tender_evidence_script.py -q`

---

## Milestone 1: 3.1.1 首页 + 医保结算清单自动生成

### Task 1.1: Define Full Field Contract

**Files:**

- Create: `backend/app/schemas/frontpage_generation_contract.py`
- Modify: `backend/app/services/frontpage_extraction_service.py`
- Modify: `backend/app/services/settlement_assembly_service.py`
- Test: `tests/unit/test_frontpage_generation_contract.py`

**Steps:**

1. Define all required extraction fields: patient basics, hospitalization, diagnoses, procedures, other medical info, staff, fees.
2. Include procedure detail fields: operation date, level, operator name/code, assistant I/II, incision healing, anesthesia method, anesthesiologist name/code.
3. Include other medical fields: injury/poison external cause name/code, pathology name/code, allergy, ABO/Rh, ventilator time, ICU type/entry/exit/transfer, coma before/after admission.
4. Write tests asserting every tender field has a contract key and settlement/frontpage mapping target.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_frontpage_generation_contract.py -q`

### Task 1.2: Replace Demo-Only Auto Generate Path

**Files:**

- Modify: `backend/app/routers/frontpage.py`
- Modify: `backend/app/services/frontpage_report_generation_service.py`
- Test: `tests/unit/test_frontpage_auto_generate.py`

**Steps:**

1. Remove or correct the stale comment saying `/auto-generate-draft` only returns demo JSON.
2. Route `visit_id` generation through real document loading where available.
3. If documents are unavailable, return a structured `requires_data` response instead of pretending success.
4. Keep `medical_text` and direct `documents` paths working.
5. Add tests for `medical_text`, `documents`, `visit_id with documents`, and `visit_id without documents`.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_frontpage_auto_generate.py -q`

### Task 1.3: Add Procedure Detail Extraction

**Files:**

- Modify: `backend/app/services/frontpage_extraction_service.py`
- Test: `tests/unit/test_frontpage_procedure_detail_extraction.py`

**Steps:**

1. Extend extraction prompt/parser for procedure detail fields.
2. Normalize surgeon and anesthesiologist names/codes into stable keys.
3. Preserve confidence/evidence snippets for each extracted field.
4. Add fixtures containing operation date, surgeon, assistants, incision healing, anesthesia method.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_frontpage_procedure_detail_extraction.py -q`

### Task 1.4: Add Field Coverage Report In UI

**Files:**

- Modify: `src/views/workstation-v4/components/FrontpageWorkspace.vue`
- Modify: `src/views/workstation-v4/components/SettlementWorkspace.vue`
- Modify: `src/types/frontpage.ts`
- Test: `src/views/workstation-v4/__tests__/frontpage-field-coverage.spec.ts`

**Steps:**

1. Display extraction status per group: completed, missing, needs review.
2. Show source/evidence for critical fields without exposing full raw medical text.
3. Keep official save buttons gated behind review.

**Checks:**

- `npm run test:unit -- frontpage-field-coverage`

---

## Milestone 2: 3.3.1 + 3.4.1 质控规则与 ICD 编码规范内涵质控

**3.4.1 scope clarification:**

- `3.4.1` is ICD coding connotation QC, not general medical-record writing connotation QC.
- It validates ICD coding rules, national/insurance version mapping, diagnosis/procedure code combinations, pathology-code/fee consistency, additional-code requirements, and downstream frontpage/settlement/DRG-DIP coding logic.
- It must not be accepted by checking whether progress notes, ward-round notes, chief complaint, present illness, or other narrative documents are well written. Those belong to document/formal QC or clinical completeness checks.

### Task 2.1: Build Rule Coverage Registry

**Files:**

- Create: `backend/app/services/qc_rule_coverage.py`
- Modify: `backend/app/services/frontpage_formal_qc.py`
- Modify: `backend/app/services/settlement_formal_qc.py`
- Test: `tests/unit/test_qc_rule_coverage.py`

**Steps:**

1. Register every formal QC rule with `standard_source`, `field`, `category`, `severity`, `applies_to`.
2. Support `NHC_FRONT_PAGE` and `INSURANCE_SETTLEMENT`.
3. Generate coverage summary for completeness, format, logic, consistency.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_qc_rule_coverage.py -q`

### Task 2.2: Wire ICD Coding Connotation QC Into Formal Review

**Files:**

- Modify: `backend/app/services/coding_qc_service.py`
- Modify: `backend/app/routers/frontpage_qc.py`
- Test: `tests/unit/test_coding_connotation_qc.py`

**Steps:**

1. Add deterministic ICD coding rule checks for tumor pathology code, pathology fee consistency, appendicitis/peritonitis merge, coronary stent additional codes, diagnosis/procedure mismatch, and national/insurance version mapping mismatch.
2. Keep LLM semantic review as optional enhancement, not the only evidence.
3. Return issues in the same shape as formal QC issues.
4. Add tests for each tender example and assert that the tests inspect coding inputs and coding outputs rather than narrative medical-record writing quality.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_coding_connotation_qc.py -q`

---

## Milestone 3: 3.4.3 诊断及手术操作完整性校验

### Task 3.1: Build Diagnosis And Procedure Timeline Model

**Files:**

- Create: `backend/app/services/clinical_timeline_service.py`
- Create: `backend/app/schemas/clinical_timeline.py`
- Test: `tests/unit/test_clinical_timeline_service.py`

**Steps:**

1. Consume assembled medical-record bundle by `visit_id`.
2. Extract diagnosis mentions with date, source document, confidence, status.
3. Extract procedure mentions/orders/operation records with date, source, execution status.
4. Return timeline grouped by diagnosis and procedure.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_clinical_timeline_service.py -q`

### Task 3.2: Add Completeness Validation API

**Files:**

- Create: `backend/app/routers/clinical_completeness.py`
- Modify: `backend/app/main.py`
- Test: `tests/unit/test_clinical_completeness_router.py`

**Steps:**

1. Add `GET /api/v1/clinical-completeness/{visit_id}`.
2. Compare timeline evidence against draft frontpage diagnosis/procedure fields.
3. Return missing diagnosis, missing procedure, conflicting date, unexecuted procedure warnings.
4. Never mutate formal frontpage data.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_clinical_completeness_router.py -q`

### Task 3.3: Add Demo Panel In Case Detail

**Files:**

- Modify: `src/views/workstation-v4/components/CaseDetailView.vue`
- Create: `src/views/workstation-v4/components/ClinicalCompletenessPanel.vue`
- Test: `src/views/workstation-v4/__tests__/clinical-completeness-panel.spec.ts`

**Steps:**

1. Add a tab or side panel named `诊疗完整性`.
2. Show diagnosis timeline and procedure execution verification.
3. Provide one-click suggestions to draft only, not formal tables.

**Checks:**

- `npm run test:unit -- clinical-completeness-panel`

---

## Milestone 4: 3.5.1 智能编码

### Task 4.1: Harden ICD Search Contract

**Files:**

- Modify: `backend/app/routers/icd_search.py`
- Modify: `backend/app/services/local_icd_service.py`
- Test: `tests/unit/test_icd_search_contract.py`

**Steps:**

1. Add explicit response schema for clinical version, insurance version, mapping, match type, confidence.
2. Add tests for ICD-10 diagnosis, ICD-9-CM-3 procedure, clinical-to-insurance mapping, insurance-to-clinical mapping.
3. Ensure no raw table rows or internal paths are returned.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_icd_search_contract.py -q`

### Task 4.2: Add Coding Suggestion Acceptance Fixtures

**Files:**

- Create: `tests/fixtures/icd_coding_cases.json`
- Test: `tests/unit/test_record_coding_suggestions.py`

**Steps:**

1. Add examples for common diagnosis and operation names.
2. Add current-record coding suggestion examples.
3. Assert stable top candidate and version mapping.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_record_coding_suggestions.py -q`

---

## Milestone 5: 4.1.2 病案问题概览

### Task 5.1: Lock Existing Overview Acceptance

**Files:**

- Modify: `tests/unit/test_notifications_overview_router.py`
- Modify: `src/views/workstation-v4/composables/useNotifications.ts`
- Test: `src/views/workstation-v4/__tests__/notifications-overview.spec.ts`

**Steps:**

1. Add tests for same-day aggregation by type, severity, department, record.
2. Add tests for overview click and read linkage.
3. Keep fallback local aggregation, but mark backend failure clearly in UI.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_notifications_overview_router.py -q`
- `npm run test:unit -- notifications-overview`

---

## Milestone 6: 6.1.1 自动化入组

### Task 6.1: Add Admission Note Event Trigger

**Files:**

- Create: `backend/app/services/pre_grouping_event_service.py`
- Create: `backend/app/routers/pre_grouping.py`
- Test: `tests/unit/test_pre_grouping_event_service.py`

**Steps:**

1. Create service method `on_admission_note_completed(visit_id, document_id)`.
2. Load the latest admission note and relevant structured fields.
3. Run extraction using the existing pre-group extraction service.
4. Store a simulation result with version and timestamp.
5. Do not write formal DRG/DIP result tables.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_pre_grouping_event_service.py -q`

### Task 6.2: Add Change Tracking And Re-Grouping

**Files:**

- Modify: `backend/app/services/pre_grouping_event_service.py`
- Create: `backend/app/services/pre_grouping_diff_service.py`
- Test: `tests/unit/test_pre_grouping_diff_service.py`

**Steps:**

1. Hash the relevant medical-record inputs.
2. If diagnosis, procedure, age, LOS, or cost changes, create a new simulation version.
3. Return previous result, current result, and changed fields.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_pre_grouping_diff_service.py -q`

### Task 6.3: Reflect Auto Updates In 事前分析 UI

**Files:**

- Modify: `src/views/workstation-v4/frontpage/components/PreAnalysisView.vue`
- Modify: `src/api/drg.ts`
- Test: `src/views/workstation-v4/frontpage/__tests__/pre-analysis-auto-update.spec.ts`

**Steps:**

1. Show latest simulation version.
2. Show changed fields since previous grouping.
3. Keep manual `执行抽取` for demos and re-run.

**Checks:**

- `npm run test:unit -- pre-analysis-auto-update`

---

## Milestone 7: 6.2.1 DRG/DIP 预入组及修正建议

### Task 7.1: Replace DIP Mock Service With Generated Local Data Source

**Files:**

- Modify: `backend/app/services/dip_grouping_service.py`
- Create: `backend/app/data/luzhou_dip_groups.json`
- Modify: `scripts/generate_luzhou_dip_data.py`
- Test: `tests/unit/test_luzhou_dip_grouping_service.py`

**Steps:**

1. Generate JSON from `docs/0602/泸市医保函〔2025〕3号附件-泸州市DIP核心和综合组.xlsx`.
2. Load JSON at runtime, not Excel.
3. Match by main diagnosis, procedure, disease property, grassroots disease flag, and score.
4. Return `dip_code`, `dip_name`, `score`, `disease_property`, `grassroots_disease_flag`, `grouping_path`.

**Checks:**

- `py -3.10 scripts/generate_luzhou_dip_data.py`
- `py -3.10 -m pytest tests/unit/test_luzhou_dip_grouping_service.py -q`

### Task 7.2: Add DRG Weight Runtime Source

**Files:**

- Modify: `scripts/generate_drg_weight_data.py`
- Create: `backend/app/data/drg_weights.json`
- Modify: `backend/app/services/drg_grouping_service.py`
- Test: `tests/unit/test_drg_weight_lookup.py`

**Steps:**

1. Generate JSON from `docs/2024年度三级公立医院绩效监测DRG权重和低风险组列表(2).xlsx`.
2. Use generated JSON for weight, low-risk group flag, and payment simulation.
3. Keep external DRG API call optional; if it fails, degrade using local weight lookup.

**Checks:**

- `py -3.10 scripts/generate_drg_weight_data.py`
- `py -3.10 -m pytest tests/unit/test_drg_weight_lookup.py -q`

### Task 7.3: Implement Correction Suggestions

**Files:**

- Create: `backend/app/services/grouping_correction_service.py`
- Modify: `backend/app/routers/pre_grouping.py`
- Test: `tests/unit/test_grouping_correction_service.py`

**Steps:**

1. For non-grouped cases, suggest missing main diagnosis/procedure code candidates.
2. For grouped cases, compare alternative diagnosis/procedure candidates and flag better grouping options.
3. Return suggestions with reason, evidence, and safety warning.
4. Do not auto-write codes.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_grouping_correction_service.py -q`

---

## Milestone 8: 6.2.2 分组器本地化适配

### Task 8.1: Connect Config To Runtime Groupers

**Files:**

- Modify: `backend/app/services/drg_config_store.py`
- Modify: `backend/app/services/dip_grouping_service.py`
- Modify: `backend/app/services/drg_grouping_service.py`
- Test: `tests/unit/test_grouping_config_runtime.py`

**Steps:**

1. Load published config version into DRG/DIP grouping calls.
2. Apply region, base rate, hospital coefficient, region coefficient, high/low thresholds.
3. Include `config_version_id` in grouping result.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_grouping_config_runtime.py -q`

### Task 8.2: Strengthen Consistency Check

**Files:**

- Modify: `backend/app/services/drg_config_store.py`
- Modify: `src/views/drg/GrouperConfig.vue`
- Test: `tests/unit/test_drg_config_consistency_real_samples.py`

**Steps:**

1. Require comparison samples to include expected DRG/DIP group.
2. Calculate exact match rate and mismatch reasons.
3. Show sample count, failed count, and mismatch table in UI.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_drg_config_consistency_real_samples.py -q`

---

## Milestone 9: 6.2.3 医保付费监测

### Task 9.1: Add Payment Simulation Backend

**Files:**

- Create: `backend/app/services/payment_monitoring_service.py`
- Create: `backend/app/routers/payment_monitoring.py`
- Test: `tests/unit/test_payment_monitoring_service.py`

**Steps:**

1. Accept grouped case results and local payment standard.
2. Calculate expected payment, actual cost, profit/loss, payment rate.
3. Classify base group, high-cost group, low-cost group, and risk level.
4. Return cost control hints.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_payment_monitoring_service.py -q`

### Task 9.2: Connect 付费监测 UI To Backend

**Files:**

- Modify: `src/views/workstation-v4/frontpage/components/PaymentMonitoringView.vue`
- Modify: `src/api/drg.ts`
- Test: `src/views/workstation-v4/frontpage/__tests__/payment-monitoring.spec.ts`

**Steps:**

1. Replace mock-only path with backend data when available.
2. Keep clear degraded state when backend data is missing.
3. Show profit/loss, payment rate, high/low group monitoring, and fee control hints.

**Checks:**

- `npm run test:unit -- payment-monitoring`

---

## Milestone 10: 6.3.1 DRG/DIP 综合分析

### Task 10.1: Fix Dimension Contract Mismatch

**Files:**

- Modify: `backend/app/routers/drg_analysis.py`
- Modify: `backend/app/services/drg/analysis_service.py`
- Modify: `src/views/workstation-v4/frontpage/components/PostEventAnalysisView.vue`
- Test: `tests/unit/test_drg_analysis_dimensions.py`

**Steps:**

1. Support `hospital`, `department`, `ward`, `attending_group`, `person`, `diagnosis_group`, `drg`.
2. Keep `doctor` as backward-compatible alias for `person`.
3. Add tests for every required level.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_drg_analysis_dimensions.py -q`

### Task 10.2: Strengthen Analysis Data Source

**Files:**

- Modify: `backend/app/services/drg/analysis_service.py`
- Create: `tests/fixtures/drg_analysis_realistic_cases.json`
- Test: `tests/unit/test_drg_analysis_metrics.py`

**Steps:**

1. Use realistic grouped data fixtures for KPI calculation.
2. Assert DRG/DIP group count, CMI, cost index, time index, low-risk mortality, average LOS, average cost, insurance profit/loss.
3. Assert profit/loss by department, diagnosis group, and doctor.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_drg_analysis_metrics.py -q`

### Task 10.3: Verify Exports

**Files:**

- Modify: `backend/app/services/drg/analysis_service.py`
- Test: `tests/unit/test_drg_analysis_exports.py`

**Steps:**

1. Assert Excel export contains KPI sheet, level sheets, profitability sheet.
2. Assert PDF export returns non-empty PDF bytes.
3. Assert DOCX export returns non-empty DOCX bytes.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_drg_analysis_exports.py -q`

---

## Milestone 11: UI Integration And Demo Readiness

### Task 11.1: Add Demonstration Routes And Demo Dataset

**Files:**

- Create: `docs/acceptance/tender-coverage/demo-script.md`
- Create: `tests/fixtures/tender_demo_cases.json`
- Modify: `backend/app/services/demo_case_loader.py`

**Steps:**

1. Prepare one demo case for homepage generation.
2. Prepare one demo case for coding connotation QC.
3. Prepare one demo case for diagnosis/procedure completeness.
4. Prepare one demo case for DRG/DIP grouping and payment monitoring.
5. Document exact clicks and expected screen result.

**Checks:**

- `py -3.10 -m pytest tests/unit/test_demo_case_loader.py -q`

### Task 11.2: Add Acceptance Dashboard

**Files:**

- Create: `src/views/workstation-v4/components/TenderAcceptanceDashboard.vue`
- Modify: `src/router/index.ts`
- Test: `src/views/workstation-v4/__tests__/tender-acceptance-dashboard.spec.ts`

**Steps:**

1. Show each tender clause and status.
2. Link to the relevant feature page.
3. Link to generated evidence report.
4. Keep it internal-only or development-only if needed.

**Checks:**

- `npm run test:unit -- tender-acceptance-dashboard`

---

## Milestone 12: End-To-End Quality Gates

### Task 12.1: Backend Full Acceptance Run

**Files:**

- Modify: `scripts/acceptance/collect_tender_evidence.py`
- Create: `scripts/acceptance/run_tender_acceptance.py`

**Steps:**

1. Run all tender-related backend tests.
2. Generate evidence report.
3. Fail if any clause is `missing` or has no test/demo evidence.

**Checks:**

- `py -3.10 scripts/acceptance/run_tender_acceptance.py`

### Task 12.2: Frontend Quality Gates

**Files:**

- No new files unless tests expose gaps.

**Steps:**

1. Run encoding check.
2. Run lint.
3. Run type-check.
4. Run unit tests.

**Checks:**

- `npm run check:encoding`
- `npm run lint`
- `npm run type-check`
- `npm run test:unit`

### Task 12.3: Final Acceptance Report

**Files:**

- Create: `docs/acceptance/tender-coverage/final-acceptance-report.md`

**Steps:**

1. Summarize every clause with evidence links.
2. Include screenshots or demo paths for screenshot-required clauses.
3. List known limitations honestly.
4. Mark whether the system is ready for tender demo.

**Checks:**

- `npm run check:encoding`

---

## Suggested Execution Order

1. Milestone 0 first, because it prevents scope drift.
2. Milestone 7 next, because DIP is currently the most explicit Mock gap.
3. Milestone 1 next, because homepage/settlement generation is the largest tender claim.
4. Milestone 3 next, because diagnosis/procedure completeness requires a new productized workflow.
5. Milestones 2, 4, 5 can run in parallel after the matrix is stable.
6. Milestones 8, 9, 10 should run after grouping data sources are stable.
7. Milestones 11 and 12 finish demo readiness and acceptance.

## Commit Strategy

- Commit after each task or small milestone.
- Use Chinese commit messages.
- Stage only files touched by the task.
- Before each commit run at least:
  - `npm run check:encoding`
  - target backend/frontend tests for the task

## Definition Of Done

- Every tender clause has a green row in `coverage-matrix.md`.
- Every clause has backend evidence, frontend/demo evidence, and at least one automated test or documented manual demo.
- No critical path depends on frontend mock data by default.
- DIP grouping no longer uses the hardcoded mock prefix table.
- `/auto-generate-draft` no longer claims demo-only behavior.
- DRG/DIP exports produce Excel, PDF, and DOCX.
- Full checks pass:
  - `npm run check:encoding`
  - `npm run lint`
  - `npm run type-check`
  - `npm run test:unit`
