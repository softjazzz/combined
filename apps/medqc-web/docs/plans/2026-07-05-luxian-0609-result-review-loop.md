# LX0609 Result Review Loop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a manual LX0609 result review loop that produces auditable review suggestions without changing original QC results.

**Architecture:** Add a backend review service that reads an existing Sichuan workspace batch job, runs deterministic rule verifiers first, optionally runs an LLM verifier on flagged items, and writes the report into the job `summary.review_report`. The frontend adds a manual “复核本次结果” action in the task center and result drawer, renders the saved report, and includes it in the existing HTML export.

**Tech Stack:** FastAPI, Python service layer, existing `CustomQCWorkspaceService` batch job storage, Vue 3 + TypeScript, Vitest, pytest.

---

## Testing Seams

- Backend highest seam: `POST /api/v1/qc/sichuan/workspace/batch-jobs/{job_id}/review`.
- Backend unit seam: a new pure service `review_luxian_0609_batch_job(job)` that returns a `review_report` dict.
- Frontend highest seam: `CustomerSampleValidationView.vue` task center and `SemanticRulesBatchResultDrawer.vue` result drawer.
- Export seam: existing `CustomQCWorkspaceService.export_batch_job_html(job=job)` output string.

These seams avoid new database tables and avoid testing private UI implementation details.

---

### Task 1: Define Review Report Types And Pure Service Skeleton

**Files:**

- Create: `backend/app/services/luxian_0609_result_review_service.py`
- Test: `backend/tests/unit/test_luxian_0609_result_review_service.py`

**Step 1: Write the failing service tests**

Add tests for:

```python
def test_review_service_rejects_non_luxian_job():
    report = review_luxian_0609_batch_job(_job(rule_set_id="sc_qc_v1"))
    assert report["review_status"] == "skipped"
    assert report["scope"] == "unsupported"


def test_review_service_flags_consultation_without_strong_evidence():
    report = review_luxian_0609_batch_job(
        _job(
            rule_set_id="luxian_0609_qc_v1",
            items=[
                {
                    "rule_id": "LX0609-020",
                    "rule_name": "会诊记录：有会诊记录单无请会诊执行记录",
                    "record_id": "2329756",
                    "status": "uncertain",
                    "findings": "病程未记录会诊执行情况。",
                    "evidence_items": [
                        {
                            "source_document": "日常病程记录",
                            "quote": "患者一般情况可，继续目前治疗。",
                        }
                    ],
                }
            ],
        )
    )
    assert report["summary"]["p1"] == 1
    assert report["findings"][0]["suggested_status"] == "not_applicable"
    assert report["findings"][0]["risk_type"] == "applicability_gate"
```

**Step 2: Run test to verify it fails**

Run:

```powershell
cd D:\LLM\LX888\apps\medqc-web\backend
python -m pytest tests/unit/test_luxian_0609_result_review_service.py -q --confcutdir=tests/unit
```

Expected: FAIL because the service file/function does not exist.

**Step 3: Implement minimal report shape**

Create `ReviewSeverity`, `ReviewRiskType` string constants and:

```python
def review_luxian_0609_batch_job(job: dict[str, Any]) -> dict[str, Any]:
    if not _is_luxian_0609_job(job):
        return {
            "review_status": "skipped",
            "scope": "unsupported",
            "summary": {"total_findings": 0, "p0": 0, "p1": 0, "p2": 0},
            "findings": [],
        }
    findings = _run_rule_verifier(job)
    return _build_report(findings)
```

**Step 4: Run test to verify it passes**

Run the same pytest command.

Expected: PASS.

**Step 5: Commit checkpoint**

Commit only after coordinator/user approval:

```powershell
git add backend/app/services/luxian_0609_result_review_service.py backend/tests/unit/test_luxian_0609_result_review_service.py
git commit -m "新增泸县0609结果复核服务骨架"
```

---

### Task 2: Implement Deterministic Rule Verifier

**Files:**

- Modify: `backend/app/services/luxian_0609_result_review_service.py`
- Test: `backend/tests/unit/test_luxian_0609_result_review_service.py`

**Step 1: Add failing tests for verifier rules**

Add cases for:

- `LX0609-020/023` without consultation strong evidence -> P1 applicability gate, suggested `not_applicable`.
- `non_compliant` with positive conclusion words like `符合/未超过/已记录/未违反` -> P0 status contradiction.
- `data_gap` with defect level `轻微缺陷/严重缺陷` -> P1 data gap display risk.
- Evidence containing internal terms `LLM/证据模板/映射执行规则/raw_response/evidence` -> P2 presentation risk.
- Evidence quote shorter than configured threshold and no source document -> P2 evidence quality risk.
- Transfusion rules `LX0609-041/044/049` without transfusion strong fact -> P1 applicability gate.
- Chemo rule `LX0609-026` without chemo order or chemo record -> P1 applicability gate.
- Surgery MDT rule `LX0609-040` without level-4 surgery evidence -> P1 applicability gate.

Example:

```python
def test_review_service_flags_data_gap_defect_badge():
    report = review_luxian_0609_batch_job(_job(
        rule_set_id="luxian_0609_qc_v1",
        items=[{
            "rule_id": "LX0609-013",
            "status": "data_gap",
            "defect_level": "轻微缺陷",
            "findings": "缺少病理报告时间。",
        }],
    ))
    finding = report["findings"][0]
    assert finding["risk_type"] == "data_gap_display"
    assert finding["severity"] == "P1"
    assert "数据不足" in finding["customer_message"]
```

**Step 2: Run tests to verify failures**

Run:

```powershell
cd D:\LLM\LX888\apps\medqc-web\backend
python -m pytest tests/unit/test_luxian_0609_result_review_service.py -q --confcutdir=tests/unit
```

Expected: FAIL for missing verifier logic.

**Step 3: Implement verifier helpers**

Add helpers:

```python
def _has_consultation_strong_fact(item: dict[str, Any]) -> bool
def _has_transfusion_strong_fact(item: dict[str, Any]) -> bool
def _has_chemo_strong_fact(item: dict[str, Any]) -> bool
def _has_level_4_surgery_fact(item: dict[str, Any]) -> bool
def _has_status_contradiction(item: dict[str, Any]) -> Optional[dict[str, Any]]
def _has_data_gap_display_risk(item: dict[str, Any]) -> Optional[dict[str, Any]]
def _has_internal_terms(item: dict[str, Any]) -> Optional[dict[str, Any]]
def _has_weak_evidence(item: dict[str, Any]) -> Optional[dict[str, Any]]
```

Keep these deterministic and local. Do not call LLM here.

**Step 4: Verify tests pass**

Run:

```powershell
cd D:\LLM\LX888\apps\medqc-web\backend
python -m pytest tests/unit/test_luxian_0609_result_review_service.py -q --confcutdir=tests/unit
```

Expected: PASS.

**Step 5: Commit checkpoint**

Commit only after approval:

```powershell
git add backend/app/services/luxian_0609_result_review_service.py backend/tests/unit/test_luxian_0609_result_review_service.py
git commit -m "实现泸县0609规则化结果复核"
```

---

### Task 3: Add LLM Verifier Adapter With Strict Input Boundary

**Files:**

- Modify: `backend/app/services/luxian_0609_result_review_service.py`
- Test: `backend/tests/unit/test_luxian_0609_result_review_service.py`

**Step 1: Write failing tests for LLM input sanitization**

Add a fake LLM verifier callable and assert:

- It is called only for findings already flagged by rule verifier.
- Payload includes result summary and evidence snippets.
- Payload excludes `prompt`, `raw_response`, `embedding`, `medical_text`, `record_content`, `documents`, `bundle`, `llm_raw_output`.
- LLM output never mutates the original result item.

Example:

```python
def test_llm_verifier_receives_only_sanitized_review_context():
    captured = []
    report = review_luxian_0609_batch_job(
        _job_with_sensitive_fields(),
        llm_verifier=lambda payloads: captured.extend(payloads) or [],
    )
    dumped = json.dumps(captured, ensure_ascii=False)
    assert "raw_response" not in dumped
    assert "medical_text" not in dumped
    assert "documents" not in dumped
```

**Step 2: Run test to verify failure**

Run:

```powershell
cd D:\LLM\LX888\apps\medqc-web\backend
python -m pytest tests/unit/test_luxian_0609_result_review_service.py -q --confcutdir=tests/unit
```

Expected: FAIL because no LLM adapter exists.

**Step 3: Implement optional LLM verifier hook**

Implement:

```python
def review_luxian_0609_batch_job(
    job: dict[str, Any],
    *,
    llm_verifier: Optional[Callable[[list[dict[str, Any]]], list[dict[str, Any]]]] = None,
) -> dict[str, Any]:
    ...
```

First version can keep production LLM disabled behind explicit injection or config. The service should still return a complete report using rule verifier only.

**Step 4: Verify tests pass**

Run the same pytest command.

Expected: PASS.

**Step 5: Commit checkpoint**

Commit only after approval:

```powershell
git add backend/app/services/luxian_0609_result_review_service.py backend/tests/unit/test_luxian_0609_result_review_service.py
git commit -m "接入泸县0609复核LLM输入边界"
```

---

### Task 4: Add Backend Review API And Persist To Job Summary

**Files:**

- Modify: `backend/app/routers/qc_sichuan.py`
- Modify: `backend/app/services/custom_qc_workspace_service.py`
- Create or modify: `backend/tests/unit/test_qc_sichuan_result_review.py`

**Step 1: Write failing router/service tests**

Add tests that:

- Completed LX0609 job can be reviewed.
- Non-LX0609 job returns a clear unsupported response.
- The generated report is written into `summary.review_report`.
- A second review overwrites or refreshes `reviewed_at` without duplicating unrelated summary fields.
- Unauthorized user cannot review another user's job.

Example expected API shape:

```json
{
  "success": true,
  "data": {
    "job_id": "job-1",
    "review_report": {
      "review_status": "completed",
      "summary": { "total_findings": 2, "p0": 1, "p1": 1, "p2": 0 }
    }
  }
}
```

**Step 2: Run test to verify failure**

Run:

```powershell
cd D:\LLM\LX888\apps\medqc-web\backend
python -m pytest tests/unit/test_qc_sichuan_result_review.py -q --confcutdir=tests/unit
```

Expected: FAIL because route does not exist.

**Step 3: Add workspace persistence method**

Add a narrow method:

```python
def update_batch_job_review_report(
    self,
    *,
    job_id: str,
    created_by: str,
    review_report: dict[str, Any],
) -> Optional[dict[str, Any]]:
    ...
```

It should update only `summary.review_report` and return the updated job.

**Step 4: Add router endpoint**

Add in `qc_sichuan.py`:

```python
@router.post("/workspace/batch-jobs/{job_id}/review")
async def review_workspace_batch_job(...):
    job = workspace.get_batch_job(...)
    if not _is_workspace_batch_job(job): raise 404
    review_report = review_luxian_0609_batch_job(job)
    updated = workspace.update_batch_job_review_report(...)
    return success_response(data={"job_id": job_id, "review_report": review_report, "job": _workspace_batch_response_item(updated)})
```

Do not change original QC result status.

**Step 5: Run backend tests**

Run:

```powershell
cd D:\LLM\LX888\apps\medqc-web\backend
python -m pytest tests/unit/test_qc_sichuan_result_review.py tests/unit/test_qc_sichuan_batch_throughput.py tests/unit/test_luxian_0609_mainline_services.py -q --confcutdir=tests/unit
```

Expected: PASS.

**Step 6: Commit checkpoint**

Commit only after approval:

```powershell
git add backend/app/routers/qc_sichuan.py backend/app/services/custom_qc_workspace_service.py backend/app/services/luxian_0609_result_review_service.py backend/tests/unit/test_qc_sichuan_result_review.py backend/tests/unit/test_luxian_0609_result_review_service.py
git commit -m "新增泸县0609任务结果复核接口"
```

---

### Task 5: Extend Frontend Types And API Client

**Files:**

- Modify: `src/views/workstation-v4/semantic-rules/types.ts`
- Modify: `src/services/sichuan-rule-workspace-service.ts`
- Test: existing frontend tests will consume these types in later tasks.

**Step 1: Add review report types**

Add types:

```ts
export type Luxian0609ReviewSeverity = 'P0' | 'P1' | 'P2'
export type Luxian0609ReviewRiskType =
  | 'applicability_gate'
  | 'status_contradiction'
  | 'data_gap_display'
  | 'evidence_quality'
  | 'presentation'
  | 'multi_record_readability'

export interface Luxian0609ReviewFinding {
  rule_id: string
  rule_name?: string
  record_id?: string
  original_status?: string
  suggested_status?: string
  severity: Luxian0609ReviewSeverity
  risk_type: Luxian0609ReviewRiskType
  reason: string
  customer_message: string
  requires_human_review: boolean
  auto_applied: false
}

export interface Luxian0609ReviewReport {
  review_status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  reviewed_at?: string
  scope?: string
  summary: { total_findings: number; p0: number; p1: number; p2: number }
  findings: Luxian0609ReviewFinding[]
}
```

Extend `SichuanBatchJob.summary` typing to include `review_report?: Luxian0609ReviewReport`.

**Step 2: Add API method**

In `sichuan-rule-workspace-service.ts`, add:

```ts
reviewBatchJob(jobId: string): Promise<ApiResponse<{ job_id: string; review_report: Luxian0609ReviewReport; job?: SichuanBatchJob }>>
```

**Step 3: Run type check for touched API/types**

Run:

```powershell
npm run type-check
```

Expected: PASS.

**Step 4: Commit checkpoint**

Commit only after approval:

```powershell
git add src/views/workstation-v4/semantic-rules/types.ts src/services/sichuan-rule-workspace-service.ts
git commit -m "补充泸县0609复核前端类型和接口"
```

---

### Task 6: Add Task Center Review Action And Summary

**Files:**

- Modify: `src/views/workstation-v4/CustomerSampleValidationView.vue`
- Test: `tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts`

**Step 1: Write failing frontend tests**

Add tests:

- Completed LX0609 task card shows `复核本次结果`.
- Clicking it calls API review method.
- After API resolves, task card shows `复核发现：高风险 X，中风险 Y，低风险 Z`.
- Non-LX0609 task does not show review button.
- Running task does not show review button.

Example test intent:

```ts
it('完成的 LX0609 任务可手动复核并展示摘要', async () => {
  mockReviewBatchJob.mockResolvedValue({
    success: true,
    data: { job_id: 'job-1', review_report: reportFixture },
  })
  const wrapper = mountViewWithCompletedLuxianJob()
  await wrapper.find('button.review-current-result').trigger('click')
  expect(mockReviewBatchJob).toHaveBeenCalledWith('job-1')
  expect(wrapper.text()).toContain('复核发现')
  expect(wrapper.text()).toContain('高风险 1')
})
```

**Step 2: Run test to verify failure**

Run:

```powershell
npm run test:unit -- --pool=threads tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts
```

Expected: FAIL because UI action does not exist.

**Step 3: Implement task center UI**

Add a small review area in each completed LX0609 history task:

```text
复核：未执行
[复核本次结果]
```

After report:

```text
复核发现：高风险 1，中风险 3，低风险 2
[查看复核报告]
```

Keep it compact; do not introduce a new drawer.

**Step 4: Run test to verify pass**

Run the same Vitest command.

Expected: PASS.

**Step 5: Commit checkpoint**

Commit only after approval:

```powershell
git add src/views/workstation-v4/CustomerSampleValidationView.vue tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts
git commit -m "在客户样本验证任务中心接入结果复核"
```

---

### Task 7: Render Review Report In Result Drawer

**Files:**

- Modify: `src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue`
- Test: `tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts`

**Step 1: Write failing drawer tests**

Add tests:

- Drawer displays a `复核报告` section when `summary.review_report` exists.
- It renders high/mid/low risk labels instead of raw `P0/P1/P2`.
- It shows original status and suggested status.
- It does not show sensitive fields.
- It handles missing report without error.

**Step 2: Run test to verify failure**

Run:

```powershell
npm run test:unit -- --pool=threads tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts
```

Expected: FAIL because drawer does not render review report.

**Step 3: Implement drawer section**

Add a compact section near the result summary:

```text
复核报告
本次复核发现 6 项需要关注的问题：高风险 1，中风险 3，低风险 2。
```

Render findings grouped by severity:

```text
高风险：质控结论与证据可能不一致
- LX0609-003：状态 non_compliant，但结论提示未超时。
```

**Step 4: Run test to verify pass**

Run the same Vitest command.

Expected: PASS.

**Step 5: Commit checkpoint**

Commit only after approval:

```powershell
git add src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts
git commit -m "在结果抽屉展示泸县0609复核报告"
```

---

### Task 8: Include Review Report In HTML Export

**Files:**

- Modify: `backend/app/services/custom_qc_workspace_service.py`
- Test: `backend/tests/unit/test_qc_sichuan_batch_throughput.py` or create `backend/tests/unit/test_qc_batch_html_export_review_report.py`

**Step 1: Write failing HTML export tests**

Add tests:

- HTML export includes `复核报告` when `summary.review_report` exists.
- HTML export shows high/mid/low risk labels.
- HTML export includes finding reason and customer message.
- HTML export excludes `prompt/raw_response/embedding/medical_text/record_content/documents/bundle/llm_raw_output`.
- Existing HTML export still works without review report.

**Step 2: Run test to verify failure**

Run:

```powershell
cd D:\LLM\LX888\apps\medqc-web\backend
python -m pytest tests/unit/test_qc_batch_html_export_review_report.py -q --confcutdir=tests/unit
```

Expected: FAIL because export does not render review report.

**Step 3: Implement review report HTML section**

In `export_batch_job_html`, add after task summary:

```html
<section>
  <h2>复核报告</h2>
  <p>复核发现：高风险 1，中风险 3，低风险 2。</p>
  ...
</section>
```

Escape all user/content strings with the existing HTML escaping helper. If no helper exists, add a local `_html_escape(value)` in the service.

**Step 4: Run export tests**

Run:

```powershell
cd D:\LLM\LX888\apps\medqc-web\backend
python -m pytest tests/unit/test_qc_batch_html_export_review_report.py tests/unit/test_qc_sichuan_batch_throughput.py -q --confcutdir=tests/unit
```

Expected: PASS.

**Step 5: Commit checkpoint**

Commit only after approval:

```powershell
git add backend/app/services/custom_qc_workspace_service.py backend/tests/unit/test_qc_batch_html_export_review_report.py
git commit -m "HTML导出包含泸县0609复核报告"
```

---

### Task 9: End-To-End Verification And Browser Check

**Files:**

- No new files unless test fixtures need update.

**Step 1: Run backend focused tests**

Run:

```powershell
cd D:\LLM\LX888\apps\medqc-web\backend
python -m pytest tests/unit/test_luxian_0609_result_review_service.py tests/unit/test_qc_sichuan_result_review.py tests/unit/test_qc_sichuan_batch_throughput.py tests/unit/test_luxian_0609_mainline_services.py -q --confcutdir=tests/unit
```

Expected: PASS.

**Step 2: Run frontend focused tests**

Run:

```powershell
cd D:\LLM\LX888\apps\medqc-web
npm run test:unit -- --pool=threads tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts
```

Expected: PASS.

**Step 3: Run project checks**

Run:

```powershell
npm run type-check
npm run check:encoding
npx eslint src/views/workstation-v4/CustomerSampleValidationView.vue src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue src/services/sichuan-rule-workspace-service.ts tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts
git diff --check
```

Expected: PASS.

**Step 4: Browser verification**

Manual/browser flow:

1. Open `http://localhost:3000/workstation-v4/customer-sample-validation`.
2. Choose an LX0609 completed task in the task center.
3. Click `复核本次结果`.
4. Confirm the task center shows review summary.
5. Open `查看结果`.
6. Confirm the result drawer has embedded `复核报告`.
7. Export HTML and confirm the file contains the same review summary.
8. Confirm no full medical text or sensitive fields appear.

**Step 5: Final commit**

Commit only after approval:

```powershell
git status --short
git add backend/app/services/luxian_0609_result_review_service.py backend/app/routers/qc_sichuan.py backend/app/services/custom_qc_workspace_service.py backend/tests/unit/test_luxian_0609_result_review_service.py backend/tests/unit/test_qc_sichuan_result_review.py backend/tests/unit/test_qc_batch_html_export_review_report.py src/services/sichuan-rule-workspace-service.ts src/views/workstation-v4/semantic-rules/types.ts src/views/workstation-v4/CustomerSampleValidationView.vue src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts
git commit -m "新增泸县0609质控结果复核闭环"
```

---

## Implementation Notes

- Do not mutate original QC result status in the review service.
- Do not add database migrations in this version.
- Do not pass full medical record text to the LLM verifier.
- Do not expose `prompt`, `raw_response`, `embedding`, `medical_text`, `record_content`, `documents`, `bundle`, or `llm_raw_output` in API, UI, or HTML export.
- If LLM verifier fails, preserve rule verifier findings and mark `llm_review_status = failed`; do not fail the whole review endpoint.
- Keep review report customer-facing language separate from internal `P0/P1/P2`.
- Non-LX0609 jobs should remain unaffected.
