# Backend Refactor Notes

This directory introduces a modular backend under `app/` while preserving the legacy `main_api.py` during the transition. Most endpoints have now been migrated to the modular app.

## New Entry

- `app/main.py`: application factory and router composition
- `app/core/settings.py`: centralized config via pydantic-settings (requires env `JWT_SECRET`)
- `app/core/logging.py`: basic structured request logging
- `app/routers/system.py`: health endpoint `/api/v1/health`
- `app/routers/proxy.py`: placeholder for LLM proxy with safe validation
- `app/routers/{auth,records,qc,qc_sichuan,medical_documents,tools,ingest,semantic_rules,llm_info,qc_llm_configs,system,debug}.py`
- `app/services/*`: extracted services (QC, Sichuan QC, records ingest) and cores (settings/http/security/supabase)

## Run (new app)

```powershell
$env:JWT_SECRET="dev-secret"
.\start_dev_backend.ps1 -Port 8001
```

如需临时启用热重载：

```powershell
$env:JWT_SECRET="dev-secret"
.\start_dev_backend.ps1 -Port 8001 -Reload
```

## Migration Plan

1. Move CORS/env/jwt settings to `core/settings.py` (done)
2. Split routers incrementally from `main_api.py` into `app/routers/*` (Completed for major modules)
3. Extract services and external clients into `app/services/*` and `app/core/http.py`
4. Remove sensitive defaults; require env for secrets and outbound allowlists
5. Replace legacy entry after route parity is reached

### Strategy
- Short-term: legacy `main_api` is still included for safety; all major endpoints have been migrated to the modular app.
- Next: remove legacy include after verification and tests.
- Safety: kept identical paths and response models; add tests around migrated routes.

### Status
- Auth: migrated (`app/routers/auth.py`)
- Records: list/get/create/update/delete/batch/export/statistics/upload/duplicate in `app/routers/records.py`
- Medical documents: docs list/update/delete, per-doc and batch QC in `app/routers/medical_documents.py`
- QC general: analyze/batch/result/progress/rules CRUD/history/PoC rules in `app/routers/qc.py`
- QC Sichuan: `app/routers/qc_sichuan.py` (single/multi-document responses match legacy)
  - Env: `SICHUAN_API_ENDPOINT`, `SICHUAN_API_KEY`, `SICHUAN_MODEL`, `SICHUAN_TIMEOUT_SECONDS`
  - Outbound allowlist via `OUTBOUND_ALLOWLIST` in `app/core/http.py`
- File parsing: public + auth in `app/routers/tools.py` (PDF/text)
- LLM ingest: `POST /api/medical-records` in `app/routers/ingest.py`
- LLM info: providers/models in `app/routers/llm_info.py`
- LLM configs: CRUD/test in `app/routers/qc_llm_configs.py`
- Semantic rules: list/get/execute/batch/custom/stats/validate in `app/routers/semantic_rules.py`
- Debug: pdf-env in `app/routers/debug.py`
