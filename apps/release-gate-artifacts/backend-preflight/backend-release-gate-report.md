# Backend Release Gate Report

- total gates: 6
- passed gates: 6
- failed gates: 0
- all passed: True

## Gate Details
- auth_guard: PASS (0.07s)
  metrics: {"required_checks": 7, "passed_checks": 7, "coverage_ratio": 1.0}
- secret_hygiene: PASS (0.08s)
  metrics: {"findings": 0}
- migration_roundtrip: PASS (3.85s)
  metrics: {"head_count": 1, "head": "20260315_000002"}
- pytest_contract: PASS (16.98s)
  metrics: {"passed": 21, "failed": 0, "skipped": 0}
- pytest_security_consistency: PASS (9.21s)
  metrics: {"passed": 30, "failed": 0, "skipped": 0}
- pytest_integration_smoke: PASS (7.13s)
  metrics: {"passed": 2, "failed": 0, "skipped": 0}

## Raw Outputs
### auth_guard
```text
D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\main.py: OK -> dependencies=[Depends(enforce_default_auth)]
D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\routers\system_config.py: OK -> dependencies=[Depends(require_admin)]
D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\routers\system_config.py: OK -> _reject_legacy_write_endpoint("/api/system/db/config")
D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\routers\system_config.py: OK -> _reject_legacy_write_endpoint("/api/system/sync/trigger")
D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\routers\medical_records.py: OK -> dependencies=[Depends(require_roles(
D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\routers\drg.py: OK -> dependencies=[Depends(require_roles(
D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\routers\settlement.py: OK -> dependencies=[Depends(require_roles(
Auth guard checks passed.
```
### secret_hygiene
```text
Secret hygiene check passed.
```
### migration_roundtrip
```text
Alembic head: 20260315_000002
Upgrade SQL generation passed.
Downgrade SQL generation passed.
Migration roundtrip check passed.
```
### pytest_contract
```text
Database initialized: D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\data\demo_feedbacks.db
============================= test session starts =============================
platform win32 -- Python 3.10.11, pytest-7.4.3, pluggy-1.6.0
rootdir: D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend
configfile: pytest.ini
plugins: anyio-3.7.1, devtools-0.12.2, asyncio-0.21.1, mock-3.12.0, timeout-2.4.0
asyncio: mode=strict
collected 21 items

tests\unit\test_auth_sync_contract.py   views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.
tests\unit\test_sync_router.py   views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.

============================== warnings summary ===============================
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
  C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.5/migration/
    warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning)

app\models\demo.py:10
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\models\demo.py:10: MovedIn20Warning: The ``declarative_base()`` function is now available as sqlalchemy.orm.declarative_base(). (deprecated since: 2.0) (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
    Base = declarative_base()

app\main.py:295
tests/unit/test_auth_sync_contract.py::test_refresh_contract_accepts_json_and_returns_stable_shape
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\main.py:295: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\fastapi\applications.py:4547
tests/unit/test_auth_sync_contract.py::test_refresh_contract_accepts_json_and_returns_stable_shape
  C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\fastapi\applications.py:4547: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 21 passed, 11 warnings in 2.84s =======================
2026-03-26 11:14:13 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 11:14:13 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 11:14:13 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:13 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:14 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:14 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:14 - app.access - INFO - [b7d22cdf-d6e2-47a7-95e6-22b030607890] - Request started
2026-03-26 11:14:14 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 11:14:14 - app.access - INFO - [b7d22cdf-d6e2-47a7-95e6-22b030607890] - Request completed
2026-03-26 11:14:14 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 11:14:14 - app.access - INFO - [2c7cb031-b360-42df-8400-5343c51c68c5] - Request started
2026-03-26 11:14:14 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=admin@medqc.com
2026-03-26 11:14:14 - app.access - INFO - [2c7cb031-b360-42df-8400-5343c51c68c5] - Request completed
2026-03-26 11:14:14 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 11:14:14 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:14 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:14 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:14 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:14 - app.access - INFO - [585153a1-3dc8-4550-8a5d-1d19f8146a6e] - Request started
2026-03-26 11:14:14 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 11:14:14 - app.access - INFO - [585153a1-3dc8-4550-8a5d-1d19f8146a6e] - Request completed
2026-03-26 11:14:14 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 11:14:14 - app.access - INFO - [deaaf13c-c2bc-427f-b00e-dc48daf6e4fb] - Request started
2026-03-26 11:14:14 - app.access - INFO - [deaaf13c-c2bc-427f-b00e-dc48daf6e4fb] - Request completed
2026-03-26 11:14:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 11:14:14 - app.access - INFO - [f13b9d07-7890-47a5-b43e-9906673ea678] - Request started
2026-03-26 11:14:14 - app.access - INFO - [f13b9d07-7890-47a5-b43e-9906673ea678] - Request completed
2026-03-26 11:14:14 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 11:14:14 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:14 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:14 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:14 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:14 - app.access - INFO - [468371c8-497a-4847-9d77-7ef3f7819f5e] - Request started
2026-03-26 11:14:14 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=doctor@medqc.com
2026-03-26 11:14:14 - app.access - INFO - [468371c8-497a-4847-9d77-7ef3f7819f5e] - Request completed
2026-03-26 11:14:14 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 11:14:14 - app.access - INFO - [dbd16e8f-1f0c-4a19-bca0-e002d36dc9a0] - Request started
2026-03-26 11:14:14 - app.main - WARNING - [dbd16e8f-1f0c-4a19-bca0-e002d36dc9a0] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 11:14:14 - app.access - WARNING - [dbd16e8f-1f0c-4a19-bca0-e002d36dc9a0] - Request completed
2026-03-26 11:14:14 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 11:14:14 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:14 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:14 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:14 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:14 - app.access - INFO - [38b33073-b871-475c-8163-a415a4752a7e] - Request started
2026-03-26 11:14:15 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 11:14:15 - app.access - INFO - [38b33073-b871-475c-8163-a415a4752a7e] - Request completed
2026-03-26 11:14:15 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 11:14:15 - app.access - INFO - [f452b3f4-7638-4471-927a-4fc80c7018b5] - Request started
2026-03-26 11:14:15 - app.routers.qc_sichuan - INFO - [no-trace-id] - Loaded 179 Sichuan rules from JSON file
2026-03-26 11:14:15 - app.access - INFO - [f452b3f4-7638-4471-927a-4fc80c7018b5] - Request completed
2026-03-26 11:14:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/qc/sichuan/rules "HTTP/1.1 200 OK"
2026-03-26 11:14:15 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:15 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:15 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:15 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:15 - app.access - INFO - [46747087-a8ea-4a59-ae5a-480785a36dac] - Request started
2026-03-26 11:14:15 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 11:14:15 - app.access - INFO - [46747087-a8ea-4a59-ae5a-480785a36dac] - Request completed
2026-03-26 11:14:15 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 11:14:15 - app.access - INFO - [e088118c-b8c8-4fa8-a7f6-72f7c4d6e97b] - Request started
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251110_041209.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251109_233517.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_234838.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_070941.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_065547.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_065421.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_062819.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_053504.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_021345.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_015054.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_014934.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_013113.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_005230.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\fe17a51e-5db0-4d37-ab6d-ac41cecca752_sequential_batch_20251112_130619.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\f41ab06d-0f77-4f0f-ad27-e9c08fea5756_sequential_batch_20251112_143049.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\f158d3cf-7fa9-4059-82e6-01e478d60399_sequential_batch_20251112_142617.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\e6cd1e70-88ac-4df9-a164-1326d35a6874_sequential_batch_20251110_064046.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\daf44f72-0baa-453b-bf32-b9355bd3bd01_sequential_batch_20251112_011112.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\defbcbd9-94e9-4723-b6df-dbf0b21ea4f7_sequential_batch_20251112_233633.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\c79d0012-c564-4d1c-bd4c-cf5aebe1fd92_sequential_batch_20251112_132237.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\aliyun_lx030_model_report_20251113_083256.json: 'list' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\a9c69ec9-9675-40ed-b203-5d830842a11c_sequential_batch_20251112_013953.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\aliyun_lx030_model_report_20251113_082322.json: 'list' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\a2bbfbe5-48de-4da8-bb47-e0cc59424775_sequential_batch_20251112_233854.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\9d5ec2a7-dc69-40dc-86ac-2c1e52f9aafd_sequential_batch_20251112_031338.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\89bb0a9d-14b9-48bc-8f67-f04f89fbb9c5_sequential_batch_20251112_031203.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\81d4a41f-bd3d-457d-aea6-1c32a412312e_sequential_batch_20251111_120900.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\818fe627-f5ad-4101-b06d-8a2addf10a71_sequential_batch_20251111_134659.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6fd14104-4d02-4b52-bc3d-a012cf4ede90_sequential_batch_20251112_232848.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6de19991-4266-4aa4-8bef-ee3001fb3ddc_sequential_batch_20251113_000427.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6154a09c-c692-4cfd-83a7-eb2773a9ad8b_sequential_batch_20251112_141218.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\5a2b1859-a0a8-436b-a4a0-af30eb6db6dc_sequential_batch_20251111_235912.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\57c72978-223b-4e01-b6ff-180e802c1718_sequential_batch_20251112_130944.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4eb1f192-80d8-48fa-8393-0c91b788d0d9_sequential_batch_20251111_235832.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4798fb59-6450-4f11-94c3-848d2702cf6c_sequential_batch_20251112_151503.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4596298c-eca7-4ca2-89ce-30ce5ae2898d_sequential_batch_20251111_012838.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\36f11425-d816-4f8a-b624-dced1ac4c164_sequential_batch_20251112_060145.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\2c59b9ef-9b2f-4ef8-b671-d0840df86da8_sequential_batch_20251112_231936.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\1e2886a3-253f-4008-b4c7-da32548e5826_sequential_batch_20251111_121107.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\1ca2602c-56e6-4310-b686-19a73531a8a9_sequential_batch_20251112_232958.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\13c4efdd-6bff-4ff7-aa51-2bc906aad435_sequential_batch_20251112_232048.json: 'NoneType' object has no attribute 'get'
2026-03-26 11:14:15 - app.access - INFO - [e088118c-b8c8-4fa8-a7f6-72f7c4d6e97b] - Request completed
2026-03-26 11:14:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/qc/sichuan/results/history?page=1&page_size=10 "HTTP/1.1 200 OK"
2026-03-26 11:14:15 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:15 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:15 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:15 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:15 - app.access - INFO - [6b64f95a-345c-48f3-a310-10f9782df6a7] - Request started
2026-03-26 11:14:15 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 11:14:15 - app.access - INFO - [6b64f95a-345c-48f3-a310-10f9782df6a7] - Request completed
2026-03-26 11:14:15 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 11:14:15 - app.access - INFO - [1cdac4ad-2b14-4624-84cc-1459a0f1c1ae] - Request started
2026-03-26 11:14:15 - app.access - INFO - [1cdac4ad-2b14-4624-84cc-1459a0f1c1ae] - Request completed
2026-03-26 11:14:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 200 OK"
2026-03-26 11:14:15 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:15 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:15 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:15 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:15 - app.access - INFO - [f1b65b80-ea78-4ec5-b9bc-86001db6c191] - Request started
2026-03-26 11:14:15 - app.access - INFO - [f1b65b80-ea78-4ec5-b9bc-86001db6c191] - Request completed
2026-03-26 11:14:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 200 OK"
2026-03-26 11:14:15 - app.access - INFO - [a8678b9f-e469-428a-a8c3-a71e7741f05a] - Request started
2026-03-26 11:14:15 - app.access - INFO - [a8678b9f-e469-428a-a8c3-a71e7741f05a] - Request completed
2026-03-26 11:14:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 200 OK"
2026-03-26 11:14:15 - app.access - INFO - [bc0b3bb9-bdce-4071-8a17-eaed0c72ecb8] - Request started
2026-03-26 11:14:15 - app.main - WARNING - [bc0b3bb9-bdce-4071-8a17-eaed0c72ecb8] - HTTP Exception: 403 - 数据同步读取权限不足（仅 admin / qc_manager 可访问）
2026-03-26 11:14:15 - app.access - WARNING - [bc0b3bb9-bdce-4071-8a17-eaed0c72ecb8] - Request completed
2026-03-26 11:14:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 403 Forbidden"
2026-03-26 11:14:15 - app.access - INFO - [6666498d-b4b7-44af-80bf-de25263d9a90] - Request started
2026-03-26 11:14:15 - app.main - WARNING - [6666498d-b4b7-44af-80bf-de25263d9a90] - HTTP Exception: 401 - Authentication required
2026-03-26 11:14:15 - app.access - WARNING - [6666498d-b4b7-44af-80bf-de25263d9a90] - Request completed
2026-03-26 11:14:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 401 Unauthorized"
2026-03-26 11:14:15 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:15 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:15 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:15 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:15 - app.access - INFO - [3ee622ce-91b6-4d65-b090-cfc2775e13ee] - Request started
2026-03-26 11:14:15 - app.main - WARNING - [3ee622ce-91b6-4d65-b090-cfc2775e13ee] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 11:14:15 - app.access - WARNING - [3ee622ce-91b6-4d65-b090-cfc2775e13ee] - Request completed
2026-03-26 11:14:15 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 11:14:15 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:15 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:15 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:15 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:15 - app.access - INFO - [17816729-27ae-4b7b-8762-4fcd735f31c0] - Request started
2026-03-26 11:14:15 - app.main - WARNING - [17816729-27ae-4b7b-8762-4fcd735f31c0] - Validation Error: [{'type': 'greater_than_equal', 'loc': ('body', 'lookback_minutes'), 'msg': 'Input should be greater than or equal to 0', 'input': -1, 'ctx': {'ge': 0}, 'url': 'https://errors.pydantic.dev/2.5/v/greater_than_equal'}]
2026-03-26 11:14:15 - app.access - WARNING - [17816729-27ae-4b7b-8762-4fcd735f31c0] - Request completed
2026-03-26 11:14:15 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/mongo "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 11:14:15 - app.access - INFO - [da151761-9f55-4cc7-848a-2d853923d6a1] - Request started
2026-03-26 11:14:15 - app.access - INFO - [da151761-9f55-4cc7-848a-2d853923d6a1] - Request completed
2026-03-26 11:14:15 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/mongo "HTTP/1.1 200 OK"
2026-03-26 11:14:15 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:15 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:15 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:15 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:15 - app.access - INFO - [85852118-565c-4457-abb1-4eb8d988760c] - Request started
2026-03-26 11:14:15 - app.access - INFO - [85852118-565c-4457-abb1-4eb8d988760c] - Request completed
2026-03-26 11:14:15 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 11:14:15 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:15 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:15 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:15 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:15 - app.access - INFO - [279bae95-7db5-49a4-87de-499269929a9e] - Request started
2026-03-26 11:14:16 - app.access - INFO - [279bae95-7db5-49a4-87de-499269929a9e] - Request completed
2026-03-26 11:14:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/test-connection/all "HTTP/1.1 200 OK"
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:16 - app.access - INFO - [bfc34398-a4ba-45a9-82e5-f0c9177f20a3] - Request started
2026-03-26 11:14:16 - app.access - INFO - [bfc34398-a4ba-45a9-82e5-f0c9177f20a3] - Request completed
2026-03-26 11:14:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/preflight "HTTP/1.1 200 OK"
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:16 - app.access - INFO - [245f4888-01c6-4e8c-8454-b5a7e4c3d815] - Request started
2026-03-26 11:14:16 - app.access - INFO - [245f4888-01c6-4e8c-8454-b5a7e4c3d815] - Request completed
2026-03-26 11:14:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/preflight "HTTP/1.1 200 OK"
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:16 - app.access - INFO - [e407008b-d20f-4514-b4b1-5554e8dd1cf1] - Request started
2026-03-26 11:14:16 - app.access - INFO - [e407008b-d20f-4514-b4b1-5554e8dd1cf1] - Request completed
2026-03-26 11:14:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:16 - app.access - INFO - [f3e8438e-5318-4a7e-b9f9-3e5a3442329f] - Request started
2026-03-26 11:14:16 - app.routers.sync - INFO - [no-trace-id] - sync.trigger operator=sync@test.local source=mongo tier=tier1 status=success total_records=2
2026-03-26 11:14:16 - app.access - INFO - [f3e8438e-5318-4a7e-b9f9-3e5a3442329f] - Request completed
2026-03-26 11:14:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:16 - app.access - INFO - [f5d1d5c8-36b1-4fd2-bab6-188837d64b60] - Request started
2026-03-26 11:14:16 - app.access - INFO - [f5d1d5c8-36b1-4fd2-bab6-188837d64b60] - Request completed
2026-03-26 11:14:16 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/runs?source=mongo&tier=tier2&limit=20 "HTTP/1.1 200 OK"
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:16 - app.access - INFO - [702b7486-1cc1-4666-8da5-17fbd081f6e7] - Request started
2026-03-26 11:14:16 - app.access - INFO - [702b7486-1cc1-4666-8da5-17fbd081f6e7] - Request completed
2026-03-26 11:14:16 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/templates "HTTP/1.1 200 OK"
2026-03-26 11:14:16 - app.access - INFO - [74fabf54-84a3-476f-872c-89f8b7fc3521] - Request started
2026-03-26 11:14:16 - app.main - WARNING - [74fabf54-84a3-476f-872c-89f8b7fc3521] - HTTP Exception: 403 - 数据同步读取权限不足（仅 admin / qc_manager 可访问）
2026-03-26 11:14:16 - app.access - WARNING - [74fabf54-84a3-476f-872c-89f8b7fc3521] - Request completed
2026-03-26 11:14:16 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/templates "HTTP/1.1 403 Forbidden"
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:16 - app.access - INFO - [6a928899-3315-4c23-ac80-851e24abbde9] - Request started
2026-03-26 11:14:16 - app.access - INFO - [6a928899-3315-4c23-ac80-851e24abbde9] - Request completed
2026-03-26 11:14:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 200 OK"
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:16 - app.access - INFO - [75e45851-cae9-4a08-a111-d247d8c5e462] - Request started
2026-03-26 11:14:16 - app.main - WARNING - [75e45851-cae9-4a08-a111-d247d8c5e462] - HTTP Exception: 422 - 该模板必须选择科室
2026-03-26 11:14:16 - app.access - WARNING - [75e45851-cae9-4a08-a111-d247d8c5e462] - Request completed
2026-03-26 11:14:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 11:14:16 - app.access - INFO - [0dfb83b0-83e4-4639-b3a7-613930a2e71a] - Request started
2026-03-26 11:14:16 - app.main - WARNING - [0dfb83b0-83e4-4639-b3a7-613930a2e71a] - HTTP Exception: 422 - 科室列表不允许同时包含 * 和具体科室
2026-03-26 11:14:16 - app.access - WARNING - [0dfb83b0-83e4-4639-b3a7-613930a2e71a] - Request completed
2026-03-26 11:14:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:16 - app.access - INFO - [f1b1efbd-b1e7-4eaa-8bba-6d020d7354e9] - Request started
2026-03-26 11:14:16 - app.access - INFO - [f1b1efbd-b1e7-4eaa-8bba-6d020d7354e9] - Request completed
2026-03-26 11:14:16 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/departments "HTTP/1.1 200 OK"
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:16 - app.access - INFO - [af200ecb-7a31-4d57-9001-3e9d6c74d92c] - Request started
2026-03-26 11:14:16 - app.main - WARNING - [af200ecb-7a31-4d57-9001-3e9d6c74d92c] - HTTP Exception: 422 - mongo_uri 未配置
2026-03-26 11:14:16 - app.access - WARNING - [af200ecb-7a31-4d57-9001-3e9d6c74d92c] - Request completed
2026-03-26 11:14:16 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/departments "HTTP/1.1 422 Unprocessable Entity"
```
### pytest_security_consistency
```text
Database initialized: D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\data\demo_feedbacks.db
============================= test session starts =============================
platform win32 -- Python 3.10.11, pytest-7.4.3, pluggy-1.6.0
rootdir: D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend
configfile: pytest.ini
plugins: anyio-3.7.1, devtools-0.12.2, asyncio-0.21.1, mock-3.12.0, timeout-2.4.0
asyncio: mode=strict
collected 30 items

tests\unit\test_security_hardening.py   views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.
tests\unit\test_sync_consistency.py ......
tests\unit\test_system_api.py   views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.

============================== warnings summary ===============================
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
  C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.5/migration/
    warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning)

app\models\demo.py:10
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\models\demo.py:10: MovedIn20Warning: The ``declarative_base()`` function is now available as sqlalchemy.orm.declarative_base(). (deprecated since: 2.0) (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
    Base = declarative_base()

app\main.py:295
tests/unit/test_security_hardening.py::test_high_risk_endpoints_require_auth
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\main.py:295: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\fastapi\applications.py:4547
tests/unit/test_security_hardening.py::test_high_risk_endpoints_require_auth
  C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\fastapi\applications.py:4547: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 30 passed, 11 warnings in 3.29s =======================
2026-03-26 11:14:21 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 11:14:22 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 11:14:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:22 - app.access - INFO - [8f962261-d5c5-4f12-adb5-4caa1881d025] - Request started
2026-03-26 11:14:22 - app.main - WARNING - [8f962261-d5c5-4f12-adb5-4caa1881d025] - HTTP Exception: 401 - Authentication required
2026-03-26 11:14:22 - app.access - WARNING - [8f962261-d5c5-4f12-adb5-4caa1881d025] - Request completed
2026-03-26 11:14:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/list "HTTP/1.1 401 Unauthorized"
2026-03-26 11:14:22 - app.access - INFO - [824dbb3f-2676-434d-876a-50e63a7a1a76] - Request started
2026-03-26 11:14:22 - app.main - WARNING - [824dbb3f-2676-434d-876a-50e63a7a1a76] - HTTP Exception: 401 - Authentication required
2026-03-26 11:14:22 - app.access - WARNING - [824dbb3f-2676-434d-876a-50e63a7a1a76] - Request completed
2026-03-26 11:14:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/drg/config/current "HTTP/1.1 401 Unauthorized"
2026-03-26 11:14:22 - app.access - INFO - [36a000ae-95ad-47a0-bedb-ead779d225e7] - Request started
2026-03-26 11:14:22 - app.main - WARNING - [36a000ae-95ad-47a0-bedb-ead779d225e7] - HTTP Exception: 401 - Authentication required
2026-03-26 11:14:22 - app.access - WARNING - [36a000ae-95ad-47a0-bedb-ead779d225e7] - Request completed
2026-03-26 11:14:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/settlement/list "HTTP/1.1 401 Unauthorized"
2026-03-26 11:14:22 - app.access - INFO - [11e58210-22aa-44f6-a698-bd8bd8744d2b] - Request started
2026-03-26 11:14:22 - app.main - WARNING - [11e58210-22aa-44f6-a698-bd8bd8744d2b] - HTTP Exception: 401 - Authentication required
2026-03-26 11:14:22 - app.access - WARNING - [11e58210-22aa-44f6-a698-bd8bd8744d2b] - Request completed
2026-03-26 11:14:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 401 Unauthorized"
2026-03-26 11:14:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:22 - app.access - INFO - [55039b46-09a5-4123-b78e-db8f27107ea9] - Request started
2026-03-26 11:14:22 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=doctor@medqc.com
2026-03-26 11:14:22 - app.access - INFO - [55039b46-09a5-4123-b78e-db8f27107ea9] - Request completed
2026-03-26 11:14:22 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 11:14:22 - app.access - INFO - [b25757ac-0fba-4afe-842b-02bdb893affa] - Request started
2026-03-26 11:14:22 - app.main - WARNING - [b25757ac-0fba-4afe-842b-02bdb893affa] - HTTP Exception: 403 - 此操作需要系统管理员权限
2026-03-26 11:14:22 - app.access - WARNING - [b25757ac-0fba-4afe-842b-02bdb893affa] - Request completed
2026-03-26 11:14:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 403 Forbidden"
2026-03-26 11:14:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:22 - app.access - INFO - [75db902e-ad66-4f4d-8875-24c3c7491641] - Request started
2026-03-26 11:14:23 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 11:14:23 - app.access - INFO - [75db902e-ad66-4f4d-8875-24c3c7491641] - Request completed
2026-03-26 11:14:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 11:14:23 - app.access - INFO - [62ef5dce-c69e-4072-b95b-bef490274e51] - Request started
2026-03-26 11:14:23 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=admin@medqc.com
2026-03-26 11:14:23 - app.access - INFO - [62ef5dce-c69e-4072-b95b-bef490274e51] - Request completed
2026-03-26 11:14:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 11:14:23 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:23 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:23 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:23 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:23 - app.access - INFO - [3924575b-3ed0-4945-967e-2619ca4cedba] - Request started
2026-03-26 11:14:23 - app.access - INFO - [3924575b-3ed0-4945-967e-2619ca4cedba] - Request completed
2026-03-26 11:14:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 11:14:23 - app.access - INFO - [e3294ffb-bc99-4976-b12f-22e753a35a91] - Request started
2026-03-26 11:14:23 - app.routers.auth - INFO - [no-trace-id] - auth.forgot_password.issued email=reset-d4ee5670@medqc.com
2026-03-26 11:14:23 - app.access - INFO - [e3294ffb-bc99-4976-b12f-22e753a35a91] - Request completed
2026-03-26 11:14:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/forgot-password "HTTP/1.1 200 OK"
2026-03-26 11:14:23 - app.access - INFO - [afb375c2-c080-4138-8fea-be58242da270] - Request started
2026-03-26 11:14:23 - app.routers.auth - INFO - [no-trace-id] - auth.reset_password.success email=reset-d4ee5670@medqc.com
2026-03-26 11:14:23 - app.access - INFO - [afb375c2-c080-4138-8fea-be58242da270] - Request completed
2026-03-26 11:14:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/reset-password "HTTP/1.1 200 OK"
2026-03-26 11:14:23 - app.access - INFO - [8714077e-ca79-4214-8cb7-8be7e489879a] - Request started
2026-03-26 11:14:23 - app.main - WARNING - [8714077e-ca79-4214-8cb7-8be7e489879a] - HTTP Exception: 401 - 重置令牌已使用或失效
2026-03-26 11:14:23 - app.access - WARNING - [8714077e-ca79-4214-8cb7-8be7e489879a] - Request completed
2026-03-26 11:14:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/reset-password "HTTP/1.1 401 Unauthorized"
2026-03-26 11:14:23 - app.access - INFO - [ef38a7ba-f07b-4333-b824-eef08c139ef6] - Request started
2026-03-26 11:14:23 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=reset-d4ee5670@medqc.com
2026-03-26 11:14:23 - app.access - INFO - [ef38a7ba-f07b-4333-b824-eef08c139ef6] - Request completed
2026-03-26 11:14:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 11:14:23 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:23 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:23 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [9f38315a-a2c7-47ed-99f0-e96b715accef] - Request started
2026-03-26 11:14:24 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 11:14:24 - app.access - INFO - [9f38315a-a2c7-47ed-99f0-e96b715accef] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [768b87f2-557b-4804-8bab-72bf2441e90e] - Request started
2026-03-26 11:14:24 - app.main - WARNING - [768b87f2-557b-4804-8bab-72bf2441e90e] - HTTP Exception: 410 - Legacy write endpoint retired: /api/system/db/config. Please use /api/v1/sync/*
2026-03-26 11:14:24 - app.access - WARNING - [768b87f2-557b-4804-8bab-72bf2441e90e] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/system/db/config "HTTP/1.1 410 Gone"
2026-03-26 11:14:24 - app.access - INFO - [730fcc69-b9c5-42c8-84f5-d09e64f13bb0] - Request started
2026-03-26 11:14:24 - app.main - WARNING - [730fcc69-b9c5-42c8-84f5-d09e64f13bb0] - HTTP Exception: 410 - Legacy write endpoint retired: /api/system/sync/trigger. Please use /api/v1/sync/*
2026-03-26 11:14:24 - app.access - WARNING - [730fcc69-b9c5-42c8-84f5-d09e64f13bb0] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/system/sync/trigger "HTTP/1.1 410 Gone"
2026-03-26 11:14:24 - app.services.etl_sync - INFO - [no-trace-id] - 同步 病案首页 (web.mr)...
2026-03-26 11:14:24 - app.services.etl_sync - INFO - [no-trace-id] -   \u2705 病案首页: 1 条
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [3724fd7b-3998-4aed-a87d-158d4e153aab] - Request started
2026-03-26 11:14:24 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 11:14:24 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 11:14:24 - app.access - INFO - [3724fd7b-3998-4aed-a87d-158d4e153aab] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [a31ca584-8175-4b0b-993e-67d4e61ffa69] - Request started
2026-03-26 11:14:24 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 11:14:24 - app.access - INFO - [a31ca584-8175-4b0b-993e-67d4e61ffa69] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [0afcd9d8-9089-42ab-9208-f9ffe6ed874c] - Request started
2026-03-26 11:14:24 - app.access - INFO - [0afcd9d8-9089-42ab-9208-f9ffe6ed874c] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [3e9e46f9-a4bd-4da3-9754-870a0aded4b1] - Request started
2026-03-26 11:14:24 - app.access - WARNING - [3e9e46f9-a4bd-4da3-9754-870a0aded4b1] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: OPTIONS http://testserver/api/v1/health "HTTP/1.1 405 Method Not Allowed"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [32dc5997-aad8-47c4-b45e-385070d28469] - Request started
2026-03-26 11:14:24 - app.access - INFO - [32dc5997-aad8-47c4-b45e-385070d28469] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [2c6190df-9983-4b11-9790-9ce132f2628b] - Request started
2026-03-26 11:14:24 - app.access - INFO - [2c6190df-9983-4b11-9790-9ce132f2628b] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [f11a3cd0-2d01-4034-b26a-8f38603c704b] - Request started
2026-03-26 11:14:24 - app.access - INFO - [f11a3cd0-2d01-4034-b26a-8f38603c704b] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [0672d2d6-6d95-427c-9daf-1aa6dbeb9f8c] - Request started
2026-03-26 11:14:24 - app.access - INFO - [0672d2d6-6d95-427c-9daf-1aa6dbeb9f8c] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [0768e21b-cf03-4d9e-8820-7778fa4315f4] - Request started
2026-03-26 11:14:24 - app.access - INFO - [0768e21b-cf03-4d9e-8820-7778fa4315f4] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [a6e0614f-2705-4f2c-859d-4df4ecbbb9bf] - Request started
2026-03-26 11:14:24 - app.access - INFO - [a6e0614f-2705-4f2c-859d-4df4ecbbb9bf] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [3cfd449d-4640-49e8-a4ff-6c38e15660bb] - Request started
2026-03-26 11:14:24 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 11:14:24 - app.access - INFO - [3cfd449d-4640-49e8-a4ff-6c38e15660bb] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [6ab06aeb-803a-4693-bdcb-8bd66708748a] - Request started
2026-03-26 11:14:24 - app.access - WARNING - [6ab06aeb-803a-4693-bdcb-8bd66708748a] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/nonexistent "HTTP/1.1 404 Not Found"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [01679fb2-06c2-43e7-adda-ca88561875df] - Request started
2026-03-26 11:14:24 - app.access - WARNING - [01679fb2-06c2-43e7-adda-ca88561875df] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/health "HTTP/1.1 405 Method Not Allowed"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [aa3e3cee-d9ce-4787-a44c-ac8f8a09654a] - Request started
2026-03-26 11:14:24 - app.access - INFO - [6e0b16ee-d70e-4dc9-b8e5-9ad5b5b6838e] - Request started
2026-03-26 11:14:24 - app.access - INFO - [ab2ed5c3-3a69-4b67-904d-7321dd538a51] - Request started
2026-03-26 11:14:24 - app.access - INFO - [a9ec7c59-0284-4c69-9c0d-e18a0a7421f4] - Request started
2026-03-26 11:14:24 - app.access - INFO - [402d9b4b-0973-41c1-bd25-ae3efcce26f7] - Request started
2026-03-26 11:14:24 - app.access - INFO - [1b9f5544-7e57-4780-9b0a-4ea8320ffc78] - Request started
2026-03-26 11:14:24 - app.access - INFO - [2f39a583-33ea-4b65-b0fd-11c11785f48a] - Request started
2026-03-26 11:14:24 - app.access - INFO - [48ba1b2b-6146-4c37-a545-145b0e94fec0] - Request started
2026-03-26 11:14:24 - app.access - INFO - [aa3e3cee-d9ce-4787-a44c-ac8f8a09654a] - Request completed
2026-03-26 11:14:24 - app.access - INFO - [6aa71b54-65d8-4042-a08d-e932cfd7435f] - Request started
2026-03-26 11:14:24 - app.access - INFO - [45b3a7d2-cc65-4f78-a216-732f237d9e0c] - Request started
2026-03-26 11:14:24 - app.access - INFO - [6e0b16ee-d70e-4dc9-b8e5-9ad5b5b6838e] - Request completed
2026-03-26 11:14:24 - app.access - INFO - [ab2ed5c3-3a69-4b67-904d-7321dd538a51] - Request completed
2026-03-26 11:14:24 - app.access - INFO - [a9ec7c59-0284-4c69-9c0d-e18a0a7421f4] - Request completed
2026-03-26 11:14:24 - app.access - INFO - [402d9b4b-0973-41c1-bd25-ae3efcce26f7] - Request completed
2026-03-26 11:14:24 - app.access - INFO - [1b9f5544-7e57-4780-9b0a-4ea8320ffc78] - Request completed
2026-03-26 11:14:24 - app.access - INFO - [2f39a583-33ea-4b65-b0fd-11c11785f48a] - Request completed
2026-03-26 11:14:24 - app.access - INFO - [48ba1b2b-6146-4c37-a545-145b0e94fec0] - Request completed
2026-03-26 11:14:24 - app.access - INFO - [6aa71b54-65d8-4042-a08d-e932cfd7435f] - Request completed
2026-03-26 11:14:24 - app.access - INFO - [45b3a7d2-cc65-4f78-a216-732f237d9e0c] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [f7d4fcf0-b963-4b6d-8d48-f310361f55d1] - Request started
2026-03-26 11:14:24 - app.access - INFO - [f7d4fcf0-b963-4b6d-8d48-f310361f55d1] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [6c32d652-2d98-43cd-ab42-f5c1fdd830fb] - Request started
2026-03-26 11:14:24 - app.access - INFO - [6c32d652-2d98-43cd-ab42-f5c1fdd830fb] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [3c6f01bb-2978-4a4e-b931-24c567fdd6fe] - Request started
2026-03-26 11:14:24 - app.access - INFO - [3c6f01bb-2978-4a4e-b931-24c567fdd6fe] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [71cca999-eeb3-4e74-b61a-9a30738dba9d] - Request started
2026-03-26 11:14:24 - app.access - INFO - [71cca999-eeb3-4e74-b61a-9a30738dba9d] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health?test=1&test=2 "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 11:14:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 11:14:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 11:14:24 - app.access - INFO - [0e45ba7c-c804-4c80-930a-24dc7f93d42f] - Request started
2026-03-26 11:14:24 - app.access - INFO - [0e45ba7c-c804-4c80-930a-24dc7f93d42f] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [b0a5d1be-47c3-44e5-bbee-9c5490baf705] - Request started
2026-03-26 11:14:24 - app.access - INFO - [b0a5d1be-47c3-44e5-bbee-9c5490baf705] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [8a12ec72-11f6-47ed-b0ec-6031c2cad405] - Request started
2026-03-26 11:14:24 - app.access - INFO - [8a12ec72-11f6-47ed-b0ec-6031c2cad405] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [a0e6458d-0c56-4a2a-b93f-59314f041370] - Request started
2026-03-26 11:14:24 - app.access - INFO - [a0e6458d-0c56-4a2a-b93f-59314f041370] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [7e3ad92e-fcd4-448e-aa57-ae8149c5ef96] - Request started
2026-03-26 11:14:24 - app.access - INFO - [7e3ad92e-fcd4-448e-aa57-ae8149c5ef96] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [aeec5fb7-2ca7-4a54-88aa-f3ec037f273f] - Request started
2026-03-26 11:14:24 - app.access - INFO - [aeec5fb7-2ca7-4a54-88aa-f3ec037f273f] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [3635caef-78b1-433e-9d07-426e1907b2a6] - Request started
2026-03-26 11:14:24 - app.access - INFO - [3635caef-78b1-433e-9d07-426e1907b2a6] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [cad53b14-b980-4446-b8db-7cf267212d55] - Request started
2026-03-26 11:14:24 - app.access - INFO - [cad53b14-b980-4446-b8db-7cf267212d55] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [650e1e6d-8da1-4f59-9584-ece66ef9e462] - Request started
2026-03-26 11:14:24 - app.access - INFO - [650e1e6d-8da1-4f59-9584-ece66ef9e462] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [ce42718c-a8a2-4cbf-9d99-60c5ba0ca16c] - Request started
2026-03-26 11:14:24 - app.access - INFO - [ce42718c-a8a2-4cbf-9d99-60c5ba0ca16c] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [2fd71b0d-6318-40dd-a8b3-3a257f3fce49] - Request started
2026-03-26 11:14:24 - app.access - INFO - [2fd71b0d-6318-40dd-a8b3-3a257f3fce49] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [21cb3982-500f-463b-90a9-dc08e130eb43] - Request started
2026-03-26 11:14:24 - app.access - INFO - [21cb3982-500f-463b-90a9-dc08e130eb43] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [b3cecb21-f4af-4b3d-9294-c6cbac8d975a] - Request started
2026-03-26 11:14:24 - app.access - INFO - [b3cecb21-f4af-4b3d-9294-c6cbac8d975a] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [ff160727-87a8-4c94-bf9f-78e3e7ea684d] - Request started
2026-03-26 11:14:24 - app.access - INFO - [ff160727-87a8-4c94-bf9f-78e3e7ea684d] - Request completed
2026-03-26 11:14:24 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:24 - app.access - INFO - [0c27d8ad-e53b-49f3-8696-031fb80130ca] - Request started
2026-03-26 11:14:24 - app.access - INFO - [0c27d8ad-e53b-49f3-8696-031fb80130ca] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [c2467292-333c-4005-9bed-38f856eede1e] - Request started
2026-03-26 11:14:25 - app.access - INFO - [c2467292-333c-4005-9bed-38f856eede1e] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [b84fbbc3-ae87-463a-acbe-3d860d81c006] - Request started
2026-03-26 11:14:25 - app.access - INFO - [b84fbbc3-ae87-463a-acbe-3d860d81c006] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [39a087f9-f32d-410a-b17a-351cbcdbdb70] - Request started
2026-03-26 11:14:25 - app.access - INFO - [39a087f9-f32d-410a-b17a-351cbcdbdb70] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [451357e1-9c79-460c-b812-6b3bc4432098] - Request started
2026-03-26 11:14:25 - app.access - INFO - [451357e1-9c79-460c-b812-6b3bc4432098] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [e8d70aa6-b9da-44e3-9516-c6281b54de8f] - Request started
2026-03-26 11:14:25 - app.access - INFO - [e8d70aa6-b9da-44e3-9516-c6281b54de8f] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [40bfdcd0-1b89-4ca9-b12a-1b4cdad8c8ae] - Request started
2026-03-26 11:14:25 - app.access - INFO - [40bfdcd0-1b89-4ca9-b12a-1b4cdad8c8ae] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [cb1c3836-e40e-4ede-8ffd-610d0f484b15] - Request started
2026-03-26 11:14:25 - app.access - INFO - [cb1c3836-e40e-4ede-8ffd-610d0f484b15] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [15c867ef-825a-4300-92ae-1b13fbf5fc64] - Request started
2026-03-26 11:14:25 - app.access - INFO - [15c867ef-825a-4300-92ae-1b13fbf5fc64] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [10c2adcb-07ba-40e4-9d5b-922aa895b6bf] - Request started
2026-03-26 11:14:25 - app.access - INFO - [10c2adcb-07ba-40e4-9d5b-922aa895b6bf] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [c25a779a-35a5-49f2-8796-232b01290a19] - Request started
2026-03-26 11:14:25 - app.access - INFO - [c25a779a-35a5-49f2-8796-232b01290a19] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [a45f2ddd-dda4-41ab-b6de-53423186d20a] - Request started
2026-03-26 11:14:25 - app.access - INFO - [a45f2ddd-dda4-41ab-b6de-53423186d20a] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [4126c448-024c-4ede-906b-009ebe569460] - Request started
2026-03-26 11:14:25 - app.access - INFO - [4126c448-024c-4ede-906b-009ebe569460] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [ebaf9f01-3260-4326-becf-2fd112013721] - Request started
2026-03-26 11:14:25 - app.access - INFO - [ebaf9f01-3260-4326-becf-2fd112013721] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [3536aa0b-2202-4ed5-8a7a-b1878ac54714] - Request started
2026-03-26 11:14:25 - app.access - INFO - [3536aa0b-2202-4ed5-8a7a-b1878ac54714] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [d1420c3e-b996-4437-bb2a-12e7b6b86704] - Request started
2026-03-26 11:14:25 - app.access - INFO - [d1420c3e-b996-4437-bb2a-12e7b6b86704] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [7b011539-8278-4bd0-94d5-1240050c1744] - Request started
2026-03-26 11:14:25 - app.access - INFO - [7b011539-8278-4bd0-94d5-1240050c1744] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [0f7739ca-fef7-4df6-ad59-b94003ecb8d2] - Request started
2026-03-26 11:14:25 - app.access - INFO - [0f7739ca-fef7-4df6-ad59-b94003ecb8d2] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [72b42fe9-ab8d-4fab-9e09-aec12729e7d6] - Request started
2026-03-26 11:14:25 - app.access - INFO - [72b42fe9-ab8d-4fab-9e09-aec12729e7d6] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [373b2a7b-9a4a-4e2b-b0fc-af595a79598d] - Request started
2026-03-26 11:14:25 - app.access - INFO - [373b2a7b-9a4a-4e2b-b0fc-af595a79598d] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [9c53b2f8-c920-44d8-9da7-07d7d55cd21c] - Request started
2026-03-26 11:14:25 - app.access - INFO - [9c53b2f8-c920-44d8-9da7-07d7d55cd21c] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [3d14dbb1-f2c2-43f1-aaa3-10070f00abca] - Request started
2026-03-26 11:14:25 - app.access - INFO - [3d14dbb1-f2c2-43f1-aaa3-10070f00abca] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [ca6f0277-9fd7-4721-830f-d2a6883924d0] - Request started
2026-03-26 11:14:25 - app.access - INFO - [ca6f0277-9fd7-4721-830f-d2a6883924d0] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [c53b0d84-273e-4275-be3f-83013e4ec6c0] - Request started
2026-03-26 11:14:25 - app.access - INFO - [c53b0d84-273e-4275-be3f-83013e4ec6c0] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [0e3650aa-6c37-4275-9563-edf2802848d3] - Request started
2026-03-26 11:14:25 - app.access - INFO - [0e3650aa-6c37-4275-9563-edf2802848d3] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [8dfaeac6-3246-4147-9478-5589cef494bf] - Request started
2026-03-26 11:14:25 - app.access - INFO - [8dfaeac6-3246-4147-9478-5589cef494bf] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [efd051cc-f355-4163-8cb9-6f79c1459451] - Request started
2026-03-26 11:14:25 - app.access - INFO - [efd051cc-f355-4163-8cb9-6f79c1459451] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [f788df18-0add-4bff-bd73-b4e46c06c632] - Request started
2026-03-26 11:14:25 - app.access - INFO - [f788df18-0add-4bff-bd73-b4e46c06c632] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [33aed51f-16ad-4550-9771-c86819697930] - Request started
2026-03-26 11:14:25 - app.access - INFO - [33aed51f-16ad-4550-9771-c86819697930] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [fd1bf406-3d96-4f1f-b6b4-5d01abad9e2a] - Request started
2026-03-26 11:14:25 - app.access - INFO - [fd1bf406-3d96-4f1f-b6b4-5d01abad9e2a] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [c1bad7d3-9c3e-4f44-a777-ceff382d592f] - Request started
2026-03-26 11:14:25 - app.access - INFO - [c1bad7d3-9c3e-4f44-a777-ceff382d592f] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [0d82d8a4-4b93-4d8f-ac11-61ec8e86dde4] - Request started
2026-03-26 11:14:25 - app.access - INFO - [0d82d8a4-4b93-4d8f-ac11-61ec8e86dde4] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [95c7f490-4450-41fa-a688-c41c00d7b92a] - Request started
2026-03-26 11:14:25 - app.access - INFO - [95c7f490-4450-41fa-a688-c41c00d7b92a] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [5582760b-9dd8-450f-a204-eaadeeb7b404] - Request started
2026-03-26 11:14:25 - app.access - INFO - [5582760b-9dd8-450f-a204-eaadeeb7b404] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [cb14e0b6-d239-45a4-acda-2400c0b98c64] - Request started
2026-03-26 11:14:25 - app.access - INFO - [cb14e0b6-d239-45a4-acda-2400c0b98c64] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [fe0df4dd-f5a4-4298-8d6b-b4d2e6ec96ce] - Request started
2026-03-26 11:14:25 - app.access - INFO - [fe0df4dd-f5a4-4298-8d6b-b4d2e6ec96ce] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [c48c4bef-cc80-4f63-b0bc-ba18b4544c71] - Request started
2026-03-26 11:14:25 - app.access - INFO - [c48c4bef-cc80-4f63-b0bc-ba18b4544c71] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [87ed7a4e-8771-4df7-aaec-0531b6c7126c] - Request started
2026-03-26 11:14:25 - app.access - INFO - [87ed7a4e-8771-4df7-aaec-0531b6c7126c] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [ffb22065-661f-433a-b5c8-7b9bf02d6a47] - Request started
2026-03-26 11:14:25 - app.access - INFO - [ffb22065-661f-433a-b5c8-7b9bf02d6a47] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [26707ad6-f89c-4454-8ac8-f89f81ba7de6] - Request started
2026-03-26 11:14:25 - app.access - INFO - [26707ad6-f89c-4454-8ac8-f89f81ba7de6] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [d117d272-7f83-4b9f-ace5-2a35aa2ff92c] - Request started
2026-03-26 11:14:25 - app.access - INFO - [d117d272-7f83-4b9f-ace5-2a35aa2ff92c] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [7bd697d4-573e-4d7a-9867-c06c08788dae] - Request started
2026-03-26 11:14:25 - app.access - INFO - [7bd697d4-573e-4d7a-9867-c06c08788dae] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [73a3ea8f-8d45-40e8-a082-6d2c50ee1e8f] - Request started
2026-03-26 11:14:25 - app.access - INFO - [73a3ea8f-8d45-40e8-a082-6d2c50ee1e8f] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [e8ca317a-397f-4d71-9d89-3f0a31e668f9] - Request started
2026-03-26 11:14:25 - app.access - INFO - [e8ca317a-397f-4d71-9d89-3f0a31e668f9] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [10576f79-a2e7-420b-8a37-b5e76ebe3a2d] - Request started
2026-03-26 11:14:25 - app.access - INFO - [10576f79-a2e7-420b-8a37-b5e76ebe3a2d] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [cca1607e-db7b-4def-b368-74025294fd5a] - Request started
2026-03-26 11:14:25 - app.access - INFO - [cca1607e-db7b-4def-b368-74025294fd5a] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [2638a0cd-f787-40ec-9f62-fe89b6c28969] - Request started
2026-03-26 11:14:25 - app.access - INFO - [2638a0cd-f787-40ec-9f62-fe89b6c28969] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [71c056e4-4099-4f3e-b565-e9a233d4bc48] - Request started
2026-03-26 11:14:25 - app.access - INFO - [71c056e4-4099-4f3e-b565-e9a233d4bc48] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [4c52a6b9-cd12-4d22-9621-4d69b9a9d175] - Request started
2026-03-26 11:14:25 - app.access - INFO - [4c52a6b9-cd12-4d22-9621-4d69b9a9d175] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [5a1b44c3-ea6b-4f1b-baef-56dca973780f] - Request started
2026-03-26 11:14:25 - app.access - INFO - [5a1b44c3-ea6b-4f1b-baef-56dca973780f] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [e790cc0e-68c8-43b9-aa5c-6c89a6294680] - Request started
2026-03-26 11:14:25 - app.access - INFO - [e790cc0e-68c8-43b9-aa5c-6c89a6294680] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [b7d3786e-ee7b-4620-915f-47cabc762630] - Request started
2026-03-26 11:14:25 - app.access - INFO - [b7d3786e-ee7b-4620-915f-47cabc762630] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [615ecda5-9d65-49d6-bbda-b55c1354684a] - Request started
2026-03-26 11:14:25 - app.access - INFO - [615ecda5-9d65-49d6-bbda-b55c1354684a] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [249cc339-1f5f-4acf-b450-f0f17d5e4170] - Request started
2026-03-26 11:14:25 - app.access - INFO - [249cc339-1f5f-4acf-b450-f0f17d5e4170] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [3d164a25-d990-41f9-b384-5bd637334e26] - Request started
2026-03-26 11:14:25 - app.access - INFO - [3d164a25-d990-41f9-b384-5bd637334e26] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [f2f10781-c1d9-4452-9b98-e51d0f994728] - Request started
2026-03-26 11:14:25 - app.access - INFO - [f2f10781-c1d9-4452-9b98-e51d0f994728] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [ed5e060c-9297-4eb1-87d6-a4313e708e9b] - Request started
2026-03-26 11:14:25 - app.access - INFO - [ed5e060c-9297-4eb1-87d6-a4313e708e9b] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [457854cf-a7f3-46fe-b3f2-b2d38b55b0ed] - Request started
2026-03-26 11:14:25 - app.access - INFO - [457854cf-a7f3-46fe-b3f2-b2d38b55b0ed] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [fe01efc9-2a58-41f7-b748-c0f4da7db990] - Request started
2026-03-26 11:14:25 - app.access - INFO - [fe01efc9-2a58-41f7-b748-c0f4da7db990] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [dba50806-63ab-4802-91af-3a5113c3c55b] - Request started
2026-03-26 11:14:25 - app.access - INFO - [dba50806-63ab-4802-91af-3a5113c3c55b] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [3002735b-66f9-488d-a703-cb0f246cc4c5] - Request started
2026-03-26 11:14:25 - app.access - INFO - [3002735b-66f9-488d-a703-cb0f246cc4c5] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [71184721-0ede-4bbf-bbe8-2cdc2e2e7a6c] - Request started
2026-03-26 11:14:25 - app.access - INFO - [71184721-0ede-4bbf-bbe8-2cdc2e2e7a6c] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [13bd1050-b262-42ea-9a1d-af4a41fb9086] - Request started
2026-03-26 11:14:25 - app.access - INFO - [13bd1050-b262-42ea-9a1d-af4a41fb9086] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [8698ec4f-75be-444c-bcf8-44e0aae34d2f] - Request started
2026-03-26 11:14:25 - app.access - INFO - [8698ec4f-75be-444c-bcf8-44e0aae34d2f] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [e3ec4259-9c36-4965-9922-5fd3d7338993] - Request started
2026-03-26 11:14:25 - app.access - INFO - [e3ec4259-9c36-4965-9922-5fd3d7338993] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [b3c7fe19-e09b-460e-ba20-148d9bfa7534] - Request started
2026-03-26 11:14:25 - app.access - INFO - [b3c7fe19-e09b-460e-ba20-148d9bfa7534] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [3f518d99-50bd-49e3-b7ef-721c436c7076] - Request started
2026-03-26 11:14:25 - app.access - INFO - [3f518d99-50bd-49e3-b7ef-721c436c7076] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [9dc75c6d-713e-4af8-83b6-31f3f3d9b6ad] - Request started
2026-03-26 11:14:25 - app.access - INFO - [9dc75c6d-713e-4af8-83b6-31f3f3d9b6ad] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [d6968c47-c2a2-4ff4-adad-7953f89c82f3] - Request started
2026-03-26 11:14:25 - app.access - INFO - [d6968c47-c2a2-4ff4-adad-7953f89c82f3] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [c066a5a7-bfd0-4cd4-94ae-25f5a5808414] - Request started
2026-03-26 11:14:25 - app.access - INFO - [c066a5a7-bfd0-4cd4-94ae-25f5a5808414] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [2c3ea843-55c7-43a3-a8f2-22f530b9a543] - Request started
2026-03-26 11:14:25 - app.access - INFO - [2c3ea843-55c7-43a3-a8f2-22f530b9a543] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [74d0e47f-20f3-40e1-96ad-e808d2ed8f96] - Request started
2026-03-26 11:14:25 - app.access - INFO - [74d0e47f-20f3-40e1-96ad-e808d2ed8f96] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [9883459a-ec06-410f-b877-0ccf930bb9d3] - Request started
2026-03-26 11:14:25 - app.access - INFO - [9883459a-ec06-410f-b877-0ccf930bb9d3] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [965d5b64-90f4-4ef3-89ba-b267a9305366] - Request started
2026-03-26 11:14:25 - app.access - INFO - [965d5b64-90f4-4ef3-89ba-b267a9305366] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [9b78eb53-2d9d-4fe9-b752-9912c691589e] - Request started
2026-03-26 11:14:25 - app.access - INFO - [9b78eb53-2d9d-4fe9-b752-9912c691589e] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [25d21467-4c63-4f20-bd0d-85ffb252a6ef] - Request started
2026-03-26 11:14:25 - app.access - INFO - [25d21467-4c63-4f20-bd0d-85ffb252a6ef] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [76da6e90-dd88-4228-9149-c4e90617ee83] - Request started
2026-03-26 11:14:25 - app.access - INFO - [76da6e90-dd88-4228-9149-c4e90617ee83] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [f070f904-ee5c-439c-9bef-2f96a5bd229f] - Request started
2026-03-26 11:14:25 - app.access - INFO - [f070f904-ee5c-439c-9bef-2f96a5bd229f] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [d3326507-c77c-4611-a359-8cd2e829797a] - Request started
2026-03-26 11:14:25 - app.access - INFO - [d3326507-c77c-4611-a359-8cd2e829797a] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [4abb5eb8-6e93-4b80-b3d2-b7c755dcefb6] - Request started
2026-03-26 11:14:25 - app.access - INFO - [4abb5eb8-6e93-4b80-b3d2-b7c755dcefb6] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [d45f7fb6-ce44-499f-9c2d-25eaa7fe2f3d] - Request started
2026-03-26 11:14:25 - app.access - INFO - [d45f7fb6-ce44-499f-9c2d-25eaa7fe2f3d] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [a1711256-250e-4c1b-9258-a4376d1f08c7] - Request started
2026-03-26 11:14:25 - app.access - INFO - [a1711256-250e-4c1b-9258-a4376d1f08c7] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [a2fcd485-48fb-4f75-ab42-ec426f13dcd1] - Request started
2026-03-26 11:14:25 - app.access - INFO - [a2fcd485-48fb-4f75-ab42-ec426f13dcd1] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [1cda72da-6e6d-4610-8fe9-70d7de9cd6ab] - Request started
2026-03-26 11:14:25 - app.access - INFO - [1cda72da-6e6d-4610-8fe9-70d7de9cd6ab] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [96b68a56-8499-412b-99b0-5bca89854815] - Request started
2026-03-26 11:14:25 - app.access - INFO - [96b68a56-8499-412b-99b0-5bca89854815] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:25 - app.access - INFO - [655bdc73-4836-49bb-8dd7-cd4adc57b574] - Request started
2026-03-26 11:14:25 - app.access - INFO - [655bdc73-4836-49bb-8dd7-cd4adc57b574] - Request completed
2026-03-26 11:14:25 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
```
### pytest_integration_smoke
```text
Database initialized: D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\data\demo_feedbacks.db
============================= test session starts =============================
platform win32 -- Python 3.10.11, pytest-7.4.3, pluggy-1.6.0
rootdir: D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend
configfile: pytest.ini
plugins: anyio-3.7.1, devtools-0.12.2, asyncio-0.21.1, mock-3.12.0, timeout-2.4.0
asyncio: mode=strict
collected 2 items

tests\integration\test_release_gate_smoke.py ..

============================== warnings summary ===============================
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268
  C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\pydantic\_internal\_config.py:268: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.5/migration/
    warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning)

app\models\demo.py:10
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\models\demo.py:10: MovedIn20Warning: The ``declarative_base()`` function is now available as sqlalchemy.orm.declarative_base(). (deprecated since: 2.0) (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
    Base = declarative_base()

app\main.py:295
tests/integration/test_release_gate_smoke.py::test_release_gate_auth_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_system_probe_smoke
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\main.py:295: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\fastapi\applications.py:4547
tests/integration/test_release_gate_smoke.py::test_release_gate_auth_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_system_probe_smoke
  C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\fastapi\applications.py:4547: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 2 passed, 13 warnings in 1.24s ========================
2026-03-26 11:14:31 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 11:14:31 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 11:14:31 - app.access - INFO - [645c5208-a166-4565-a720-e9a655d165b0] - Request started
2026-03-26 11:14:31 - app.access - INFO - [645c5208-a166-4565-a720-e9a655d165b0] - Request completed
2026-03-26 11:14:31 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 11:14:31 - app.access - INFO - [af639f2d-9f43-48e0-b0bf-e58fa6dc2d73] - Request started
2026-03-26 11:14:32 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=release-gate-83cc5463b025@example.com
2026-03-26 11:14:32 - app.access - INFO - [af639f2d-9f43-48e0-b0bf-e58fa6dc2d73] - Request completed
2026-03-26 11:14:32 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 11:14:32 - app.access - INFO - [3b450cbb-8e81-4117-8db4-5b92749a0876] - Request started
2026-03-26 11:14:32 - app.access - INFO - [3b450cbb-8e81-4117-8db4-5b92749a0876] - Request completed
2026-03-26 11:14:32 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/auth/me "HTTP/1.1 200 OK"
2026-03-26 11:14:32 - app.access - INFO - [5d510805-8ea2-44e4-9377-e612e4bbad9d] - Request started
2026-03-26 11:14:32 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=release-gate-83cc5463b025@example.com
2026-03-26 11:14:32 - app.access - INFO - [5d510805-8ea2-44e4-9377-e612e4bbad9d] - Request completed
2026-03-26 11:14:32 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 11:14:32 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 11:14:32 - app.access - INFO - [a171ab97-6fb8-4890-96f0-3212a43395d1] - Request started
2026-03-26 11:14:32 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 11:14:32 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 11:14:32 - app.access - INFO - [a171ab97-6fb8-4890-96f0-3212a43395d1] - Request completed
2026-03-26 11:14:32 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 11:14:32 - app.access - INFO - [8fef6a00-8fa0-49bb-8705-0f4417f5abb9] - Request started
2026-03-26 11:14:32 - app.access - INFO - [8fef6a00-8fa0-49bb-8705-0f4417f5abb9] - Request completed
2026-03-26 11:14:32 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
```