# Settlement Frontpage Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a production-safe fallback path that generates a settlement draft from frontpage extraction when settlement table data is missing, without breaking existing settlement and QC flows.

**Architecture:** Keep the current primary path (`medical_insurance_settlement` table) unchanged. Add a secondary assembly path that builds a settlement draft from `frontpage + CDM SQL` and returns it via a new API endpoint. Add a separate QC endpoint for generated drafts so QC does not depend on persistence in settlement tables.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Axios, Vitest, Pytest

---

### Task 1: Freeze Field Contract and Naming

**Files:**
- Create: `docs/plans/settlement-generated-draft-contract.md`
- Modify: `docs/plans/2026-03-13-settlement-frontpage-fallback-implementation.md`
- Test: N/A (documentation task)

**Step 1: Write a failing contract checklist**

```markdown
- [ ] `receiving_institution_name` is used everywhere (no `receiving_institution` output key)
- [ ] `therapy_type` is used everywhere (no `treatment_type` output key)
- [ ] coma fields use settlement flat keys:
  - `coma_timebefadm_d/h/min`
  - `coma_timeaftadm_d/h/min`
```

**Step 2: Run a quick grep to verify current mismatch**

Run:
```bash
rg -n "receiving_institution|receiving_institution_name|treatment_type|therapy_type|coma_" apps/medqc-web/backend/app apps/medqc-web/src/views/workstation-v2
```
Expected: mixed keys found (FAIL checklist).

**Step 3: Write minimal contract doc**

```markdown
## Generated Settlement Draft Contract (v1)
source: generated_from_frontpage
is_draft: true
required output keys: [exact SettlementSheet fields]
```

**Step 4: Re-run grep and annotate gaps**

Run:
```bash
rg -n "receiving_institution|treatment_type" apps/medqc-web/backend/app apps/medqc-web/src/views/workstation-v2
```
Expected: gaps remain but are documented with explicit remediation tasks.

**Step 5: Commit**

```bash
git add docs/plans/settlement-generated-draft-contract.md docs/plans/2026-03-13-settlement-frontpage-fallback-implementation.md
git commit -m "docs: define generated settlement draft field contract"
```

### Task 2: Add Backend Assembly Service Tests First

**Files:**
- Create: `apps/medqc-web/backend/tests/unit/test_settlement_assembly_service.py`
- Create: `apps/medqc-web/backend/app/services/settlement_assembly_service.py`
- Test: `apps/medqc-web/backend/tests/unit/test_settlement_assembly_service.py`

**Step 1: Write the failing test**

```python
def test_assemble_generated_settlement_maps_required_sheet_fields():
    svc = SettlementAssemblyService()
    draft = {"basic_info": {"patient_name": "A"}, "hospitalization": {"admission_datetime": "2026-01-01 08:00:00"}}
    sql = {"mr": {"inpat_type": "1", "therapy_type": "1", "planned_transder_to": "XX Hospital"}}
    out = svc._assemble_from_sources(draft, sql)
    assert out["patient_name"] == "A"
    assert out["inpat_type"] == "1"
    assert out["therapy_type"] == "1"
    assert out["receiving_institution_name"] == "XX Hospital"
    assert out["is_draft"] is True
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd apps/medqc-web/backend
pytest tests/unit/test_settlement_assembly_service.py::test_assemble_generated_settlement_maps_required_sheet_fields -v
```
Expected: FAIL (`SettlementAssemblyService` not found).

**Step 3: Write minimal implementation**

```python
class SettlementAssemblyService:
    def _assemble_from_sources(self, draft: dict, sql: dict) -> dict:
        mr = (sql or {}).get("mr") or {}
        basic = (draft or {}).get("basic_info") or {}
        return {
            "patient_name": basic.get("patient_name") or "",
            "inpat_type": mr.get("inpat_type") or "",
            "therapy_type": mr.get("therapy_type") or "",
            "receiving_institution_name": mr.get("planned_transder_to") or "",
            "is_draft": True,
            "data_source": "generated_from_frontpage",
        }
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd apps/medqc-web/backend
pytest tests/unit/test_settlement_assembly_service.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/medqc-web/backend/tests/unit/test_settlement_assembly_service.py apps/medqc-web/backend/app/services/settlement_assembly_service.py
git commit -m "test+feat: add settlement assembly service with base mapping"
```

### Task 3: Implement Full Backend Field Mapping and Fallback Loading

**Files:**
- Modify: `apps/medqc-web/backend/app/services/settlement_assembly_service.py`
- Modify: `apps/medqc-web/backend/app/services/frontpage_extraction_service.py`
- Test: `apps/medqc-web/backend/tests/unit/test_settlement_assembly_service.py`

**Step 1: Write the failing tests**

```python
def test_assemble_fills_sheet_field_defaults_when_missing():
    out = SettlementAssemblyService()._assemble_from_sources({}, {})
    assert out["insurance_no"] == ""
    assert out["special_personnel_type"] == ""
    assert out["insured_place"] == ""

def test_assemble_maps_coma_flat_fields():
    draft = {"other_medical_info": {"brain_injury_coma_in": {"before": {"days": 1, "hours": 2, "minutes": 3}}}}
    out = SettlementAssemblyService()._assemble_from_sources(draft, {})
    assert out["coma_timebefadm_d"] == "1"
```

**Step 2: Run tests to verify fail**

Run:
```bash
cd apps/medqc-web/backend
pytest tests/unit/test_settlement_assembly_service.py -v
```
Expected: FAIL for missing keys and mapping.

**Step 3: Write minimal implementation**

```python
SHEET_FIELDS = {"insurance_no": "", "special_personnel_type": "", "insured_place": "", ...}
# merge order: defaults <- frontpage draft map <- SQL map <- system-generated fields
```

Add explicit source marker:

```python
result["is_draft"] = True
result["data_source"] = "generated_from_frontpage"
result["declaration_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
```

**Step 4: Run tests to verify pass**

Run:
```bash
cd apps/medqc-web/backend
pytest tests/unit/test_settlement_assembly_service.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/medqc-web/backend/app/services/settlement_assembly_service.py apps/medqc-web/backend/tests/unit/test_settlement_assembly_service.py
git commit -m "feat: complete settlement generated-draft field mapping"
```

### Task 4: Add Generate API Endpoint (Do Not Persist to Settlement Table)

**Files:**
- Modify: `apps/medqc-web/backend/app/routers/settlement.py`
- Modify: `apps/medqc-web/backend/app/services/settlement_assembly_service.py`
- Test: `apps/medqc-web/backend/tests/unit/test_settlement_generate_api.py`

**Step 1: Write the failing test**

```python
def test_generate_settlement_returns_200_with_draft_flags(client):
    resp = client.post("/api/medical-records/settlement/p001/v001/generate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_draft"] is True
    assert data["data_source"] == "generated_from_frontpage"
```

**Step 2: Run test to verify fail**

Run:
```bash
cd apps/medqc-web/backend
pytest tests/unit/test_settlement_generate_api.py::test_generate_settlement_returns_200_with_draft_flags -v
```
Expected: FAIL with 404 or route missing.

**Step 3: Write minimal implementation**

```python
@router.post("/settlement/{patient_id}/{visit_id}/generate")
async def generate_settlement_from_frontpage(patient_id: str, visit_id: str):
    svc = get_settlement_assembly_service()
    return svc.generate(patient_id=patient_id, visit_id=visit_id)
```

**Step 4: Run tests to verify pass**

Run:
```bash
cd apps/medqc-web/backend
pytest tests/unit/test_settlement_generate_api.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/medqc-web/backend/app/routers/settlement.py apps/medqc-web/backend/app/services/settlement_assembly_service.py apps/medqc-web/backend/tests/unit/test_settlement_generate_api.py
git commit -m "feat: add settlement generate endpoint from frontpage fallback"
```

### Task 5: Add Draft QC Endpoint (Fix QC Chain Break)

**Files:**
- Modify: `apps/medqc-web/backend/app/routers/settlement.py`
- Modify: `apps/medqc-web/backend/app/services/settlement_assembly_service.py`
- Modify: `apps/medqc-web/backend/app/services/settlement_formal_qc.py` (only if key alias compatibility is required)
- Test: `apps/medqc-web/backend/tests/unit/test_settlement_generate_qc_api.py`

**Step 1: Write the failing test**

```python
def test_generate_qc_works_without_settlement_table_row(client):
    resp = client.post("/api/medical-records/settlement/p001/v001/generate/qc")
    assert resp.status_code == 200
    body = resp.json()
    assert "summary" in body and "results" in body
```

**Step 2: Run test to verify fail**

Run:
```bash
cd apps/medqc-web/backend
pytest tests/unit/test_settlement_generate_qc_api.py -v
```
Expected: FAIL route not found.

**Step 3: Write minimal implementation**

```python
@router.post("/settlement/{patient_id}/{visit_id}/generate/qc")
async def run_generated_settlement_qc(patient_id: str, visit_id: str):
    draft = get_settlement_assembly_service().generate(patient_id, visit_id)
    report = SettlementFormalQCEngine().check(draft)
    return {"summary": ..., "results": ..., "settlement": draft}
```

**Step 4: Run test to verify pass**

Run:
```bash
cd apps/medqc-web/backend
pytest tests/unit/test_settlement_generate_qc_api.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/medqc-web/backend/app/routers/settlement.py apps/medqc-web/backend/tests/unit/test_settlement_generate_qc_api.py
git commit -m "feat: add generated settlement qc endpoint"
```

### Task 6: Frontend Fallback Loader and Source State

**Files:**
- Modify: `apps/medqc-web/src/views/workstation-v2/WorkstationV4View.vue`
- Create: `apps/medqc-web/src/views/workstation-v2/services/settlement-loader.ts`
- Test: `apps/medqc-web/tests/unit/views/settlement-loader.spec.ts`

**Step 1: Write the failing test**

```ts
it("falls back to generate endpoint when settlement detail returns 404", async () => {
  // mock GET 404 then POST /generate 200
  // expect final data_source to be generated_from_frontpage
})
```

**Step 2: Run test to verify fail**

Run:
```bash
cd apps/medqc-web
npm run test:unit -- tests/unit/views/settlement-loader.spec.ts
```
Expected: FAIL helper not found.

**Step 3: Write minimal implementation**

```ts
export async function loadSettlementWithFallback(patientId: string, visitId: string) {
  try { return await axios.get(`/api/medical-records/settlement/${patientId}/${visitId}`) }
  catch (err: any) {
    if (err?.response?.status === 404) {
      return await axios.post(`/api/medical-records/settlement/${patientId}/${visitId}/generate`)
    }
    throw err
  }
}
```

**Step 4: Run test to verify pass**

Run:
```bash
cd apps/medqc-web
npm run test:unit -- tests/unit/views/settlement-loader.spec.ts
```
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/medqc-web/src/views/workstation-v2/services/settlement-loader.ts apps/medqc-web/src/views/workstation-v2/WorkstationV4View.vue apps/medqc-web/tests/unit/views/settlement-loader.spec.ts
git commit -m "feat: frontend settlement fallback loader with source tagging"
```

### Task 7: Frontend Draft UI Guardrails

**Files:**
- Modify: `apps/medqc-web/src/views/workstation-v2/WorkstationV4View.vue`
- Modify: `apps/medqc-web/src/views/workstation-v2/components/SettlementSheet.vue` (only if draft badge placement requires)
- Test: `apps/medqc-web/tests/unit/views/settlement-loader.spec.ts`

**Step 1: Write the failing test**

```ts
it("shows draft banner when data_source is generated_from_frontpage", async () => {
  // mount with settlementData.data_source = generated_from_frontpage
  // expect banner text contains "AI Draft"
})
```

**Step 2: Run test to verify fail**

Run:
```bash
cd apps/medqc-web
npm run test:unit -- tests/unit/views/settlement-loader.spec.ts
```
Expected: FAIL, no banner.

**Step 3: Write minimal implementation**

```vue
<a-alert v-if="settlementData?.data_source === 'generated_from_frontpage'" type="warning" message="AI Draft - manual review required" />
```

**Step 4: Run test to verify pass**

Run:
```bash
cd apps/medqc-web
npm run test:unit -- tests/unit/views/settlement-loader.spec.ts
```
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/medqc-web/src/views/workstation-v2/WorkstationV4View.vue apps/medqc-web/tests/unit/views/settlement-loader.spec.ts
git commit -m "feat: add draft warning banner for generated settlement"
```

### Task 8: Wire QC Button Routing by Data Source

**Files:**
- Modify: `apps/medqc-web/src/views/workstation-v2/WorkstationV4View.vue`
- Test: `apps/medqc-web/tests/unit/views/settlement-loader.spec.ts`

**Step 1: Write the failing test**

```ts
it("calls generated qc endpoint for generated drafts", async () => {
  // settlementData.data_source=generated_from_frontpage
  // click qc button -> POST /generate/qc
})
```

**Step 2: Run test to verify fail**

Run:
```bash
cd apps/medqc-web
npm run test:unit -- tests/unit/views/settlement-loader.spec.ts
```
Expected: FAIL, still calling legacy `/qc`.

**Step 3: Write minimal implementation**

```ts
const qcUrl = settlementData.value?.data_source === "generated_from_frontpage"
  ? `/api/medical-records/settlement/${pid}/${vid}/generate/qc`
  : `/api/medical-records/settlement/${pid}/${vid}/qc`
await axios.post(qcUrl)
```

**Step 4: Run test to verify pass**

Run:
```bash
cd apps/medqc-web
npm run test:unit -- tests/unit/views/settlement-loader.spec.ts
```
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/medqc-web/src/views/workstation-v2/WorkstationV4View.vue apps/medqc-web/tests/unit/views/settlement-loader.spec.ts
git commit -m "feat: route settlement qc by data source"
```

### Task 9: ETL Phase-2 Preparation Patch (Optional, Non-Blocking)

**Files:**
- Modify: `apps/medqc-web/backend/app/services/etl_sync.py`
- Modify: `apps/medqc-web/backend/app/services/etl_config.py`
- Test: `apps/medqc-web/backend/tests/unit/test_etl_settlement_tables_config.py`

**Step 1: Write the failing test**

```python
def test_sync_tables_include_settlement_tables():
    from app.services.etl_sync import SYNC_TABLES
    names = {t["name"] for t in SYNC_TABLES}
    assert "medical_insurance_settlement" in names
    assert "medical_insurance_settlement_cost" in names
```

**Step 2: Run test to verify fail**

Run:
```bash
cd apps/medqc-web/backend
pytest tests/unit/test_etl_settlement_tables_config.py -v
```
Expected: FAIL.

**Step 3: Write minimal implementation**

```python
SYNC_TABLES += [
  {"name": "medical_insurance_settlement", "procedure": "web.medical_insurance_settlement", ...},
  {"name": "medical_insurance_settlement_cost", "procedure": "web.medical_insurance_settlement_cost", ...},
]
```

**Step 4: Run test to verify pass**

Run:
```bash
cd apps/medqc-web/backend
pytest tests/unit/test_etl_settlement_tables_config.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/medqc-web/backend/app/services/etl_sync.py apps/medqc-web/backend/tests/unit/test_etl_settlement_tables_config.py
git commit -m "feat: add settlement tables to etl sync config"
```

### Task 10: End-to-End Verification and Release Checklist

**Files:**
- Create: `docs/plans/settlement-fallback-verification-checklist.md`
- Modify: `apps/medqc-web/backend/tests/unit/test_settlement_generate_api.py`
- Modify: `apps/medqc-web/tests/unit/views/settlement-loader.spec.ts`
- Test: backend and frontend commands below

**Step 1: Write failing smoke checks**

```markdown
- [ ] Existing settlement record still renders legacy path
- [ ] Missing settlement triggers generated fallback
- [ ] Generated draft shows warning banner
- [ ] Generated draft QC endpoint returns report
```

**Step 2: Run backend tests**

Run:
```bash
cd apps/medqc-web/backend
pytest tests/unit/test_settlement_assembly_service.py tests/unit/test_settlement_generate_api.py tests/unit/test_settlement_generate_qc_api.py -v
```
Expected: all PASS.

**Step 3: Run frontend tests**

Run:
```bash
cd apps/medqc-web
npm run test:unit -- tests/unit/views/settlement-loader.spec.ts
```
Expected: PASS.

**Step 4: Run build/type gate**

Run:
```bash
cd apps/medqc-web
npm run build
```
Expected: PASS.

**Step 5: Commit**

```bash
git add docs/plans/settlement-fallback-verification-checklist.md apps/medqc-web/backend/tests/unit/test_settlement_generate_api.py apps/medqc-web/tests/unit/views/settlement-loader.spec.ts
git commit -m "chore: add settlement fallback verification checklist"
```

---

## Revised Scope Decisions (Critical)

1. Do not block Phase 1 on ETL.
2. Do not rely on frontpage draft server cache; generate from current source pipeline on demand.
3. Keep generated settlement as transient draft payload (no write to `medical_insurance_settlement` in Phase 1).
4. Add a dedicated generated-draft QC endpoint.
5. Use exact ETL table name `medical_insurance_settlement_cost` (not `settlement_cost`) in code/config.

## Acceptance Criteria

1. Settlement tab returns rendered data for both cases:
   - Existing settlement row present.
   - Settlement row missing but frontpage+CDM available.
2. Generated payload contains `data_source=generated_from_frontpage` and `is_draft=true`.
3. QC can run for generated drafts without settlement table rows.
4. Existing settlement `/qc` behavior remains unchanged.
5. Tests for mapping, generate API, generate QC API, and frontend fallback all pass.
