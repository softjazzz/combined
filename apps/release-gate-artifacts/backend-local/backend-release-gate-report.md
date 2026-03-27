# Backend Release Gate Report

- total gates: 6
- passed gates: 6
- failed gates: 0
- all passed: True

## Gate Details
- auth_guard: PASS (0.09s)
  metrics: {"required_checks": 7, "passed_checks": 7, "coverage_ratio": 1.0}
- secret_hygiene: PASS (0.88s)
  metrics: {"findings": 0}
- migration_roundtrip: PASS (3.98s)
  metrics: {"head_count": 1, "head": "20260315_000002"}
- pytest_contract: PASS (11.77s)
  metrics: {"passed": 21, "failed": 0, "skipped": 0}
- pytest_security_consistency: PASS (12.18s)
  metrics: {"passed": 30, "failed": 0, "skipped": 0}
- pytest_integration_smoke: PASS (9.28s)
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
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
  C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.5/migration/
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

C:\Python310\lib\site-packages\fastapi\applications.py:4547
tests/unit/test_auth_sync_contract.py::test_refresh_contract_accepts_json_and_returns_stable_shape
  C:\Python310\lib\site-packages\fastapi\applications.py:4547: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 21 passed, 11 warnings in 3.51s =======================
2026-03-26 10:27:07 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 10:27:08 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 10:27:08 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:08 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:08 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:08 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:09 - app.access - INFO - [103cf6ee-9faa-4d3e-8f1b-c51cef85e7a0] - Request started
2026-03-26 10:27:09 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 10:27:09 - app.access - INFO - [103cf6ee-9faa-4d3e-8f1b-c51cef85e7a0] - Request completed
2026-03-26 10:27:09 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 10:27:09 - app.access - INFO - [7c0f47a8-086d-414b-b00d-f837da33a80f] - Request started
2026-03-26 10:27:09 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=admin@medqc.com
2026-03-26 10:27:09 - app.access - INFO - [7c0f47a8-086d-414b-b00d-f837da33a80f] - Request completed
2026-03-26 10:27:09 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 10:27:09 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:09 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:09 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:09 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:09 - app.access - INFO - [bc5bfdb1-e5f5-4328-8b7b-c7aafc36f4fd] - Request started
2026-03-26 10:27:09 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 10:27:09 - app.access - INFO - [bc5bfdb1-e5f5-4328-8b7b-c7aafc36f4fd] - Request completed
2026-03-26 10:27:09 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 10:27:09 - app.access - INFO - [55a02a51-824a-446e-b0c4-07a754062a44] - Request started
2026-03-26 10:27:09 - app.access - INFO - [55a02a51-824a-446e-b0c4-07a754062a44] - Request completed
2026-03-26 10:27:09 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 10:27:09 - app.access - INFO - [0eeac266-7f08-4bc1-a260-c9457019fc75] - Request started
2026-03-26 10:27:09 - app.access - INFO - [0eeac266-7f08-4bc1-a260-c9457019fc75] - Request completed
2026-03-26 10:27:09 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 10:27:09 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:09 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:09 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:09 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:09 - app.access - INFO - [dd3f8bb9-75c5-46d7-b226-e8e4c5d4d934] - Request started
2026-03-26 10:27:10 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=doctor@medqc.com
2026-03-26 10:27:10 - app.access - INFO - [dd3f8bb9-75c5-46d7-b226-e8e4c5d4d934] - Request completed
2026-03-26 10:27:10 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 10:27:10 - app.access - INFO - [b7c6c819-1e79-4a06-8a64-ee75b746ccd0] - Request started
2026-03-26 10:27:10 - app.main - WARNING - [b7c6c819-1e79-4a06-8a64-ee75b746ccd0] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 10:27:10 - app.access - WARNING - [b7c6c819-1e79-4a06-8a64-ee75b746ccd0] - Request completed
2026-03-26 10:27:10 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 10:27:10 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:10 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:10 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:10 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:10 - app.access - INFO - [6e5cb898-8287-4f0e-9517-efdea95a76bc] - Request started
2026-03-26 10:27:10 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 10:27:10 - app.access - INFO - [6e5cb898-8287-4f0e-9517-efdea95a76bc] - Request completed
2026-03-26 10:27:10 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 10:27:10 - app.access - INFO - [8fc1f8b1-c8c7-474c-a0f8-fdc50f6a6012] - Request started
2026-03-26 10:27:10 - app.routers.qc_sichuan - INFO - [no-trace-id] - Loaded 179 Sichuan rules from JSON file
2026-03-26 10:27:10 - app.access - INFO - [8fc1f8b1-c8c7-474c-a0f8-fdc50f6a6012] - Request completed
2026-03-26 10:27:10 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/qc/sichuan/rules "HTTP/1.1 200 OK"
2026-03-26 10:27:10 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:10 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:10 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:10 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:10 - app.access - INFO - [0adb66ae-4671-4165-8999-54eae0ddb9f4] - Request started
2026-03-26 10:27:10 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 10:27:10 - app.access - INFO - [0adb66ae-4671-4165-8999-54eae0ddb9f4] - Request completed
2026-03-26 10:27:10 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 10:27:10 - app.access - INFO - [2d56e137-e17b-4e68-b8e1-fc449dbad359] - Request started
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251110_041209.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251109_233517.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_234838.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_070941.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_065547.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_065421.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_062819.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_053504.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_021345.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_015054.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_014934.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_013113.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_005230.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\fe17a51e-5db0-4d37-ab6d-ac41cecca752_sequential_batch_20251112_130619.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\f41ab06d-0f77-4f0f-ad27-e9c08fea5756_sequential_batch_20251112_143049.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\f158d3cf-7fa9-4059-82e6-01e478d60399_sequential_batch_20251112_142617.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\e6cd1e70-88ac-4df9-a164-1326d35a6874_sequential_batch_20251110_064046.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\daf44f72-0baa-453b-bf32-b9355bd3bd01_sequential_batch_20251112_011112.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\defbcbd9-94e9-4723-b6df-dbf0b21ea4f7_sequential_batch_20251112_233633.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\c79d0012-c564-4d1c-bd4c-cf5aebe1fd92_sequential_batch_20251112_132237.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\aliyun_lx030_model_report_20251113_083256.json: 'list' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\a9c69ec9-9675-40ed-b203-5d830842a11c_sequential_batch_20251112_013953.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\aliyun_lx030_model_report_20251113_082322.json: 'list' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\a2bbfbe5-48de-4da8-bb47-e0cc59424775_sequential_batch_20251112_233854.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\9d5ec2a7-dc69-40dc-86ac-2c1e52f9aafd_sequential_batch_20251112_031338.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\89bb0a9d-14b9-48bc-8f67-f04f89fbb9c5_sequential_batch_20251112_031203.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\81d4a41f-bd3d-457d-aea6-1c32a412312e_sequential_batch_20251111_120900.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\818fe627-f5ad-4101-b06d-8a2addf10a71_sequential_batch_20251111_134659.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6fd14104-4d02-4b52-bc3d-a012cf4ede90_sequential_batch_20251112_232848.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6de19991-4266-4aa4-8bef-ee3001fb3ddc_sequential_batch_20251113_000427.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6154a09c-c692-4cfd-83a7-eb2773a9ad8b_sequential_batch_20251112_141218.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\5a2b1859-a0a8-436b-a4a0-af30eb6db6dc_sequential_batch_20251111_235912.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\57c72978-223b-4e01-b6ff-180e802c1718_sequential_batch_20251112_130944.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4eb1f192-80d8-48fa-8393-0c91b788d0d9_sequential_batch_20251111_235832.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4798fb59-6450-4f11-94c3-848d2702cf6c_sequential_batch_20251112_151503.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4596298c-eca7-4ca2-89ce-30ce5ae2898d_sequential_batch_20251111_012838.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\36f11425-d816-4f8a-b624-dced1ac4c164_sequential_batch_20251112_060145.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\2c59b9ef-9b2f-4ef8-b671-d0840df86da8_sequential_batch_20251112_231936.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\1e2886a3-253f-4008-b4c7-da32548e5826_sequential_batch_20251111_121107.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\1ca2602c-56e6-4310-b686-19a73531a8a9_sequential_batch_20251112_232958.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\13c4efdd-6bff-4ff7-aa51-2bc906aad435_sequential_batch_20251112_232048.json: 'NoneType' object has no attribute 'get'
2026-03-26 10:27:10 - app.access - INFO - [2d56e137-e17b-4e68-b8e1-fc449dbad359] - Request completed
2026-03-26 10:27:10 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/qc/sichuan/results/history?page=1&page_size=10 "HTTP/1.1 200 OK"
2026-03-26 10:27:10 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:10 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:10 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:10 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:10 - app.access - INFO - [65c55617-aa3c-4e02-9b35-319086a5de19] - Request started
2026-03-26 10:27:11 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 10:27:11 - app.access - INFO - [65c55617-aa3c-4e02-9b35-319086a5de19] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.access - INFO - [0d1f8eb1-bd62-4a87-9cf0-0ddb576d16a4] - Request started
2026-03-26 10:27:11 - app.access - INFO - [0d1f8eb1-bd62-4a87-9cf0-0ddb576d16a4] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [e707c100-98ff-48e0-9542-ecde5ca42af5] - Request started
2026-03-26 10:27:11 - app.access - INFO - [e707c100-98ff-48e0-9542-ecde5ca42af5] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.access - INFO - [1dd830c1-84b6-45aa-85e6-29b89dc8a23f] - Request started
2026-03-26 10:27:11 - app.access - INFO - [1dd830c1-84b6-45aa-85e6-29b89dc8a23f] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.access - INFO - [78b62e72-9aa4-4772-90b9-0b9641d2ac8f] - Request started
2026-03-26 10:27:11 - app.main - WARNING - [78b62e72-9aa4-4772-90b9-0b9641d2ac8f] - HTTP Exception: 403 - 数据同步读取权限不足（仅 admin / qc_manager 可访问）
2026-03-26 10:27:11 - app.access - WARNING - [78b62e72-9aa4-4772-90b9-0b9641d2ac8f] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 403 Forbidden"
2026-03-26 10:27:11 - app.access - INFO - [e7f38661-efee-4161-8d4c-0eeebb9d7511] - Request started
2026-03-26 10:27:11 - app.main - WARNING - [e7f38661-efee-4161-8d4c-0eeebb9d7511] - HTTP Exception: 401 - Authentication required
2026-03-26 10:27:11 - app.access - WARNING - [e7f38661-efee-4161-8d4c-0eeebb9d7511] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 401 Unauthorized"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [c01c7973-093a-4cbd-a7b1-d61e800e8101] - Request started
2026-03-26 10:27:11 - app.main - WARNING - [c01c7973-093a-4cbd-a7b1-d61e800e8101] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 10:27:11 - app.access - WARNING - [c01c7973-093a-4cbd-a7b1-d61e800e8101] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [27e3127f-8e06-40ec-82a2-734848ce10c3] - Request started
2026-03-26 10:27:11 - app.main - WARNING - [27e3127f-8e06-40ec-82a2-734848ce10c3] - Validation Error: [{'type': 'greater_than_equal', 'loc': ('body', 'lookback_minutes'), 'msg': 'Input should be greater than or equal to 0', 'input': -1, 'ctx': {'ge': 0}, 'url': 'https://errors.pydantic.dev/2.5/v/greater_than_equal'}]
2026-03-26 10:27:11 - app.access - WARNING - [27e3127f-8e06-40ec-82a2-734848ce10c3] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/mongo "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 10:27:11 - app.access - INFO - [1338abb7-21ae-4853-8638-2d2d49527882] - Request started
2026-03-26 10:27:11 - app.access - INFO - [1338abb7-21ae-4853-8638-2d2d49527882] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/mongo "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [558e3837-2190-4b2f-b1c9-d2613047caaa] - Request started
2026-03-26 10:27:11 - app.access - INFO - [558e3837-2190-4b2f-b1c9-d2613047caaa] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [0ad178c7-b7f3-4b70-8bb6-c98ad98b3c8c] - Request started
2026-03-26 10:27:11 - app.access - INFO - [0ad178c7-b7f3-4b70-8bb6-c98ad98b3c8c] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/test-connection/all "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [8cf30369-8812-4f32-92f1-fd24c443c2e2] - Request started
2026-03-26 10:27:11 - app.access - INFO - [8cf30369-8812-4f32-92f1-fd24c443c2e2] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/preflight "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [65bd37d8-6050-402d-9a55-d9157b769d71] - Request started
2026-03-26 10:27:11 - app.access - INFO - [65bd37d8-6050-402d-9a55-d9157b769d71] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/preflight "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [f817b473-c308-44fb-b7b0-c64240fc05fc] - Request started
2026-03-26 10:27:11 - app.access - INFO - [f817b473-c308-44fb-b7b0-c64240fc05fc] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [c1967deb-0eae-4bf9-80c4-0358ce95157c] - Request started
2026-03-26 10:27:11 - app.routers.sync - INFO - [no-trace-id] - sync.trigger operator=sync@test.local source=mongo tier=tier1 status=success total_records=2
2026-03-26 10:27:11 - app.access - INFO - [c1967deb-0eae-4bf9-80c4-0358ce95157c] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [c135adc8-73e4-4cf0-bed4-c4c1abc4239e] - Request started
2026-03-26 10:27:11 - app.access - INFO - [c135adc8-73e4-4cf0-bed4-c4c1abc4239e] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/runs?source=mongo&tier=tier2&limit=20 "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [312a8126-7687-4496-992b-dfd9214292e8] - Request started
2026-03-26 10:27:11 - app.access - INFO - [312a8126-7687-4496-992b-dfd9214292e8] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/templates "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.access - INFO - [c30beb3c-9d60-4891-b667-bbf1141c2ee6] - Request started
2026-03-26 10:27:11 - app.main - WARNING - [c30beb3c-9d60-4891-b667-bbf1141c2ee6] - HTTP Exception: 403 - 数据同步读取权限不足（仅 admin / qc_manager 可访问）
2026-03-26 10:27:11 - app.access - WARNING - [c30beb3c-9d60-4891-b667-bbf1141c2ee6] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/templates "HTTP/1.1 403 Forbidden"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [282f5116-1bac-41df-ab47-27e497b6079e] - Request started
2026-03-26 10:27:11 - app.access - INFO - [282f5116-1bac-41df-ab47-27e497b6079e] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [37083db6-0b9a-4f4d-8a2c-5a62bbc22b6a] - Request started
2026-03-26 10:27:11 - app.main - WARNING - [37083db6-0b9a-4f4d-8a2c-5a62bbc22b6a] - HTTP Exception: 422 - 该模板必须选择科室
2026-03-26 10:27:11 - app.access - WARNING - [37083db6-0b9a-4f4d-8a2c-5a62bbc22b6a] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 10:27:11 - app.access - INFO - [057cd62a-eb7d-4b9c-84fb-cbdc355feaef] - Request started
2026-03-26 10:27:11 - app.main - WARNING - [057cd62a-eb7d-4b9c-84fb-cbdc355feaef] - HTTP Exception: 422 - 科室列表不允许同时包含 * 和具体科室
2026-03-26 10:27:11 - app.access - WARNING - [057cd62a-eb7d-4b9c-84fb-cbdc355feaef] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [08ca108d-6264-4f75-bd8c-2d19307114b5] - Request started
2026-03-26 10:27:11 - app.access - INFO - [08ca108d-6264-4f75-bd8c-2d19307114b5] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/departments "HTTP/1.1 200 OK"
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:11 - app.access - INFO - [70d2b77d-7e68-4499-9f88-9083955704bf] - Request started
2026-03-26 10:27:11 - app.main - WARNING - [70d2b77d-7e68-4499-9f88-9083955704bf] - HTTP Exception: 422 - mongo_uri 未配置
2026-03-26 10:27:11 - app.access - WARNING - [70d2b77d-7e68-4499-9f88-9083955704bf] - Request completed
2026-03-26 10:27:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/departments "HTTP/1.1 422 Unprocessable Entity"
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
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
  C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.5/migration/
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

C:\Python310\lib\site-packages\fastapi\applications.py:4547
tests/unit/test_security_hardening.py::test_high_risk_endpoints_require_auth
  C:\Python310\lib\site-packages\fastapi\applications.py:4547: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 30 passed, 11 warnings in 4.48s =======================
2026-03-26 10:27:18 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 10:27:19 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 10:27:19 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:19 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:20 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:20 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:20 - app.access - INFO - [39937846-8298-4f0c-b4e2-bfe24c7fcfb5] - Request started
2026-03-26 10:27:20 - app.main - WARNING - [39937846-8298-4f0c-b4e2-bfe24c7fcfb5] - HTTP Exception: 401 - Authentication required
2026-03-26 10:27:20 - app.access - WARNING - [39937846-8298-4f0c-b4e2-bfe24c7fcfb5] - Request completed
2026-03-26 10:27:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/list "HTTP/1.1 401 Unauthorized"
2026-03-26 10:27:20 - app.access - INFO - [bbe4f9b0-4028-435c-8723-65f4e81c71a1] - Request started
2026-03-26 10:27:20 - app.main - WARNING - [bbe4f9b0-4028-435c-8723-65f4e81c71a1] - HTTP Exception: 401 - Authentication required
2026-03-26 10:27:20 - app.access - WARNING - [bbe4f9b0-4028-435c-8723-65f4e81c71a1] - Request completed
2026-03-26 10:27:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/drg/config/current "HTTP/1.1 401 Unauthorized"
2026-03-26 10:27:20 - app.access - INFO - [83a33b89-2cca-464d-8a00-ceb30b522a36] - Request started
2026-03-26 10:27:20 - app.main - WARNING - [83a33b89-2cca-464d-8a00-ceb30b522a36] - HTTP Exception: 401 - Authentication required
2026-03-26 10:27:20 - app.access - WARNING - [83a33b89-2cca-464d-8a00-ceb30b522a36] - Request completed
2026-03-26 10:27:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/settlement/list "HTTP/1.1 401 Unauthorized"
2026-03-26 10:27:20 - app.access - INFO - [8e65934d-b7c9-4946-be03-fc19f16dcac1] - Request started
2026-03-26 10:27:20 - app.main - WARNING - [8e65934d-b7c9-4946-be03-fc19f16dcac1] - HTTP Exception: 401 - Authentication required
2026-03-26 10:27:20 - app.access - WARNING - [8e65934d-b7c9-4946-be03-fc19f16dcac1] - Request completed
2026-03-26 10:27:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 401 Unauthorized"
2026-03-26 10:27:20 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:20 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:20 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:20 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:20 - app.access - INFO - [27a5f742-0538-446c-8ddb-8e35fff5b992] - Request started
2026-03-26 10:27:20 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=doctor@medqc.com
2026-03-26 10:27:20 - app.access - INFO - [27a5f742-0538-446c-8ddb-8e35fff5b992] - Request completed
2026-03-26 10:27:20 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 10:27:20 - app.access - INFO - [85d54a1e-21a4-4367-b254-f80dbff1cfaa] - Request started
2026-03-26 10:27:20 - app.main - WARNING - [85d54a1e-21a4-4367-b254-f80dbff1cfaa] - HTTP Exception: 403 - 此操作需要系统管理员权限
2026-03-26 10:27:20 - app.access - WARNING - [85d54a1e-21a4-4367-b254-f80dbff1cfaa] - Request completed
2026-03-26 10:27:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 403 Forbidden"
2026-03-26 10:27:20 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:20 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:20 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:20 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:20 - app.access - INFO - [314b3565-b704-46a8-be09-35c19e2e94f2] - Request started
2026-03-26 10:27:20 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 10:27:20 - app.access - INFO - [314b3565-b704-46a8-be09-35c19e2e94f2] - Request completed
2026-03-26 10:27:20 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 10:27:20 - app.access - INFO - [71105333-b0a0-4b17-83ce-8b6607c49b6b] - Request started
2026-03-26 10:27:20 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=admin@medqc.com
2026-03-26 10:27:20 - app.access - INFO - [71105333-b0a0-4b17-83ce-8b6607c49b6b] - Request completed
2026-03-26 10:27:20 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 10:27:20 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:20 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:20 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:20 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:20 - app.access - INFO - [8cf27b55-99db-46fa-99f4-acd4facd2120] - Request started
2026-03-26 10:27:21 - app.access - INFO - [8cf27b55-99db-46fa-99f4-acd4facd2120] - Request completed
2026-03-26 10:27:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 10:27:21 - app.access - INFO - [ff338bf8-cbb2-4bee-8c53-3892107c3fdb] - Request started
2026-03-26 10:27:21 - app.routers.auth - INFO - [no-trace-id] - auth.forgot_password.issued email=reset-3f3ca905@medqc.com
2026-03-26 10:27:21 - app.access - INFO - [ff338bf8-cbb2-4bee-8c53-3892107c3fdb] - Request completed
2026-03-26 10:27:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/forgot-password "HTTP/1.1 200 OK"
2026-03-26 10:27:21 - app.access - INFO - [5d279766-9ab5-41f0-a429-9a93deaaac90] - Request started
2026-03-26 10:27:21 - app.routers.auth - INFO - [no-trace-id] - auth.reset_password.success email=reset-3f3ca905@medqc.com
2026-03-26 10:27:21 - app.access - INFO - [5d279766-9ab5-41f0-a429-9a93deaaac90] - Request completed
2026-03-26 10:27:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/reset-password "HTTP/1.1 200 OK"
2026-03-26 10:27:21 - app.access - INFO - [215b90a1-5ff8-4dbf-9b9a-fd8ee00e952d] - Request started
2026-03-26 10:27:21 - app.main - WARNING - [215b90a1-5ff8-4dbf-9b9a-fd8ee00e952d] - HTTP Exception: 401 - 重置令牌已使用或失效
2026-03-26 10:27:21 - app.access - WARNING - [215b90a1-5ff8-4dbf-9b9a-fd8ee00e952d] - Request completed
2026-03-26 10:27:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/reset-password "HTTP/1.1 401 Unauthorized"
2026-03-26 10:27:21 - app.access - INFO - [c83a5241-c800-4e41-b8dd-2a1e31795bf6] - Request started
2026-03-26 10:27:21 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=reset-3f3ca905@medqc.com
2026-03-26 10:27:21 - app.access - INFO - [c83a5241-c800-4e41-b8dd-2a1e31795bf6] - Request completed
2026-03-26 10:27:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 10:27:21 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:21 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:21 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:21 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:21 - app.access - INFO - [fbc70fc2-df6b-424b-b005-33f7feaaaf4e] - Request started
2026-03-26 10:27:21 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 10:27:21 - app.access - INFO - [fbc70fc2-df6b-424b-b005-33f7feaaaf4e] - Request completed
2026-03-26 10:27:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.access - INFO - [32103c72-e187-4b88-ba05-33f241d8e978] - Request started
2026-03-26 10:27:22 - app.main - WARNING - [32103c72-e187-4b88-ba05-33f241d8e978] - HTTP Exception: 410 - Legacy write endpoint retired: /api/system/db/config. Please use /api/v1/sync/*
2026-03-26 10:27:22 - app.access - WARNING - [32103c72-e187-4b88-ba05-33f241d8e978] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/system/db/config "HTTP/1.1 410 Gone"
2026-03-26 10:27:22 - app.access - INFO - [c1d1a844-e199-40f8-ada0-d1d3d34b68c8] - Request started
2026-03-26 10:27:22 - app.main - WARNING - [c1d1a844-e199-40f8-ada0-d1d3d34b68c8] - HTTP Exception: 410 - Legacy write endpoint retired: /api/system/sync/trigger. Please use /api/v1/sync/*
2026-03-26 10:27:22 - app.access - WARNING - [c1d1a844-e199-40f8-ada0-d1d3d34b68c8] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/system/sync/trigger "HTTP/1.1 410 Gone"
2026-03-26 10:27:22 - app.services.etl_sync - INFO - [no-trace-id] - 同步 病案首页 (web.mr)...
2026-03-26 10:27:22 - app.services.etl_sync - INFO - [no-trace-id] -   \u2705 病案首页: 1 条
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [088b6f20-f871-4fd9-a741-70d7ae4c0425] - Request started
2026-03-26 10:27:22 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 10:27:22 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 10:27:22 - app.access - INFO - [088b6f20-f871-4fd9-a741-70d7ae4c0425] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [92e26657-4f29-4551-b3be-e07d0cea7a9b] - Request started
2026-03-26 10:27:22 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 10:27:22 - app.access - INFO - [92e26657-4f29-4551-b3be-e07d0cea7a9b] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [07ba2b0d-2674-4840-8bf0-d2175381e6a6] - Request started
2026-03-26 10:27:22 - app.access - INFO - [07ba2b0d-2674-4840-8bf0-d2175381e6a6] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [7a37363e-7305-415a-9010-b49f45365864] - Request started
2026-03-26 10:27:22 - app.access - WARNING - [7a37363e-7305-415a-9010-b49f45365864] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: OPTIONS http://testserver/api/v1/health "HTTP/1.1 405 Method Not Allowed"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [a00782fe-92f8-4781-a882-0af77b7dae31] - Request started
2026-03-26 10:27:22 - app.access - INFO - [a00782fe-92f8-4781-a882-0af77b7dae31] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [ef96de40-775d-4d08-a7ed-2064e85b7618] - Request started
2026-03-26 10:27:22 - app.access - INFO - [ef96de40-775d-4d08-a7ed-2064e85b7618] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [c4f5c370-1b4b-4ba9-a946-bc5dfa687685] - Request started
2026-03-26 10:27:22 - app.access - INFO - [c4f5c370-1b4b-4ba9-a946-bc5dfa687685] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [2abd28bb-b8c4-4237-95ae-f3872868817b] - Request started
2026-03-26 10:27:22 - app.access - INFO - [2abd28bb-b8c4-4237-95ae-f3872868817b] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [9fa6dd8b-76bc-4ac0-9cf4-07ec9e80c161] - Request started
2026-03-26 10:27:22 - app.access - INFO - [9fa6dd8b-76bc-4ac0-9cf4-07ec9e80c161] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [097b364d-616c-4929-95c6-8c131e71ce7c] - Request started
2026-03-26 10:27:22 - app.access - INFO - [097b364d-616c-4929-95c6-8c131e71ce7c] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [b6ba23bb-3bc7-4d66-a6ab-2e3d350f8e1a] - Request started
2026-03-26 10:27:22 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 10:27:22 - app.access - INFO - [b6ba23bb-3bc7-4d66-a6ab-2e3d350f8e1a] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [42e32ae5-ddeb-4a5b-94be-a2a8d21a163a] - Request started
2026-03-26 10:27:22 - app.access - WARNING - [42e32ae5-ddeb-4a5b-94be-a2a8d21a163a] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/nonexistent "HTTP/1.1 404 Not Found"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [218a5577-a445-4c35-8449-0febb9c99354] - Request started
2026-03-26 10:27:22 - app.access - WARNING - [218a5577-a445-4c35-8449-0febb9c99354] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/health "HTTP/1.1 405 Method Not Allowed"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [f1040f49-73ee-4892-9c4d-74d13df4a8a9] - Request started
2026-03-26 10:27:22 - app.access - INFO - [2c6c2c75-2a90-44fe-82c9-1b276bfabfc0] - Request started
2026-03-26 10:27:22 - app.access - INFO - [ffbad69d-4151-4a6c-85d1-987fdbaf29a5] - Request started
2026-03-26 10:27:22 - app.access - INFO - [31bb5d45-7ace-452f-ae4d-0dd5abbeea78] - Request started
2026-03-26 10:27:22 - app.access - INFO - [ef279bd2-549c-4947-8fc4-73a8f7f29e8f] - Request started
2026-03-26 10:27:22 - app.access - INFO - [4a2b7e21-d237-4698-8cbe-938f70c722dc] - Request started
2026-03-26 10:27:22 - app.access - INFO - [659ed812-4ad3-4b3f-ba75-f67edb5a6772] - Request started
2026-03-26 10:27:22 - app.access - INFO - [6cc63e25-c952-445e-bd46-7a3c88588e40] - Request started
2026-03-26 10:27:22 - app.access - INFO - [bd385a0e-d3ff-4430-994d-dc98c64611e9] - Request started
2026-03-26 10:27:22 - app.access - INFO - [1b719901-fcb6-4613-8f6c-4e356acdf210] - Request started
2026-03-26 10:27:22 - app.access - INFO - [f1040f49-73ee-4892-9c4d-74d13df4a8a9] - Request completed
2026-03-26 10:27:22 - app.access - INFO - [2c6c2c75-2a90-44fe-82c9-1b276bfabfc0] - Request completed
2026-03-26 10:27:22 - app.access - INFO - [ffbad69d-4151-4a6c-85d1-987fdbaf29a5] - Request completed
2026-03-26 10:27:22 - app.access - INFO - [31bb5d45-7ace-452f-ae4d-0dd5abbeea78] - Request completed
2026-03-26 10:27:22 - app.access - INFO - [ef279bd2-549c-4947-8fc4-73a8f7f29e8f] - Request completed
2026-03-26 10:27:22 - app.access - INFO - [4a2b7e21-d237-4698-8cbe-938f70c722dc] - Request completed
2026-03-26 10:27:22 - app.access - INFO - [659ed812-4ad3-4b3f-ba75-f67edb5a6772] - Request completed
2026-03-26 10:27:22 - app.access - INFO - [6cc63e25-c952-445e-bd46-7a3c88588e40] - Request completed
2026-03-26 10:27:22 - app.access - INFO - [bd385a0e-d3ff-4430-994d-dc98c64611e9] - Request completed
2026-03-26 10:27:22 - app.access - INFO - [1b719901-fcb6-4613-8f6c-4e356acdf210] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [32b43df5-2a2f-4491-959c-d9307715c0e8] - Request started
2026-03-26 10:27:22 - app.access - INFO - [32b43df5-2a2f-4491-959c-d9307715c0e8] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [e3dda20b-a5d3-4bc9-97fc-e74d64f0689a] - Request started
2026-03-26 10:27:22 - app.access - INFO - [e3dda20b-a5d3-4bc9-97fc-e74d64f0689a] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [844aa0ba-bf56-4047-84b8-9c3da8aaae60] - Request started
2026-03-26 10:27:22 - app.access - INFO - [844aa0ba-bf56-4047-84b8-9c3da8aaae60] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [9b86c6d3-d757-47a2-b9fd-b6683f1de1dd] - Request started
2026-03-26 10:27:22 - app.access - INFO - [9b86c6d3-d757-47a2-b9fd-b6683f1de1dd] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health?test=1&test=2 "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 10:27:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 10:27:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 10:27:22 - app.access - INFO - [9d4fb61b-1c94-4f25-bdc3-ceafe3de4d18] - Request started
2026-03-26 10:27:22 - app.access - INFO - [9d4fb61b-1c94-4f25-bdc3-ceafe3de4d18] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.access - INFO - [143ef488-4f02-45f3-a602-d3f4af48717a] - Request started
2026-03-26 10:27:22 - app.access - INFO - [143ef488-4f02-45f3-a602-d3f4af48717a] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.access - INFO - [79d8e54a-e226-4eba-95a2-08a62932669e] - Request started
2026-03-26 10:27:22 - app.access - INFO - [79d8e54a-e226-4eba-95a2-08a62932669e] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.access - INFO - [67412f43-e40d-4984-a99c-34e9c3703d1a] - Request started
2026-03-26 10:27:22 - app.access - INFO - [67412f43-e40d-4984-a99c-34e9c3703d1a] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:22 - app.access - INFO - [2a7361e1-ab8e-444b-99fa-96a1d642b884] - Request started
2026-03-26 10:27:22 - app.access - INFO - [2a7361e1-ab8e-444b-99fa-96a1d642b884] - Request completed
2026-03-26 10:27:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [34f5d1fc-e7af-420f-a384-75be3a0e6308] - Request started
2026-03-26 10:27:23 - app.access - INFO - [34f5d1fc-e7af-420f-a384-75be3a0e6308] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [138e9750-14b4-4311-a2b7-9eba327fe475] - Request started
2026-03-26 10:27:23 - app.access - INFO - [138e9750-14b4-4311-a2b7-9eba327fe475] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [4a426aac-53bc-483a-b6c8-55c88f5c5e34] - Request started
2026-03-26 10:27:23 - app.access - INFO - [4a426aac-53bc-483a-b6c8-55c88f5c5e34] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [2c497814-b994-4d44-8df2-6f6535303032] - Request started
2026-03-26 10:27:23 - app.access - INFO - [2c497814-b994-4d44-8df2-6f6535303032] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [0b8c2242-9f6d-49e9-9721-fb5f62d04ea9] - Request started
2026-03-26 10:27:23 - app.access - INFO - [0b8c2242-9f6d-49e9-9721-fb5f62d04ea9] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [47e6d2a6-c4b6-44a4-bb63-7179a1e242bd] - Request started
2026-03-26 10:27:23 - app.access - INFO - [47e6d2a6-c4b6-44a4-bb63-7179a1e242bd] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [ad7cb560-d5c8-4e97-868d-1c0d8928a910] - Request started
2026-03-26 10:27:23 - app.access - INFO - [ad7cb560-d5c8-4e97-868d-1c0d8928a910] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [31e332a9-c343-4bf1-b82e-08b2617cca4f] - Request started
2026-03-26 10:27:23 - app.access - INFO - [31e332a9-c343-4bf1-b82e-08b2617cca4f] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [4a7e2f5c-68dd-45b8-af66-cfabde79e746] - Request started
2026-03-26 10:27:23 - app.access - INFO - [4a7e2f5c-68dd-45b8-af66-cfabde79e746] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [c7489bec-9125-4e7c-980f-bf700365e4cb] - Request started
2026-03-26 10:27:23 - app.access - INFO - [c7489bec-9125-4e7c-980f-bf700365e4cb] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [e6613bc8-7e97-4324-8042-448283229979] - Request started
2026-03-26 10:27:23 - app.access - INFO - [e6613bc8-7e97-4324-8042-448283229979] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [ae4cdf47-fffd-4192-b0e4-7a537914dbac] - Request started
2026-03-26 10:27:23 - app.access - INFO - [ae4cdf47-fffd-4192-b0e4-7a537914dbac] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [03673664-b65f-46ef-839b-8adff8cbdbe4] - Request started
2026-03-26 10:27:23 - app.access - INFO - [03673664-b65f-46ef-839b-8adff8cbdbe4] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [cdbdee96-a73c-4579-aab6-9aa338486994] - Request started
2026-03-26 10:27:23 - app.access - INFO - [cdbdee96-a73c-4579-aab6-9aa338486994] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [832a8b23-84bc-459c-96dd-3116434434a4] - Request started
2026-03-26 10:27:23 - app.access - INFO - [832a8b23-84bc-459c-96dd-3116434434a4] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [93c034a4-c0c0-4002-adbc-54da04ec1bb6] - Request started
2026-03-26 10:27:23 - app.access - INFO - [93c034a4-c0c0-4002-adbc-54da04ec1bb6] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [2eff04d5-466f-4c79-836f-694408ac0ba2] - Request started
2026-03-26 10:27:23 - app.access - INFO - [2eff04d5-466f-4c79-836f-694408ac0ba2] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [551d7b1a-d38b-4a6b-b077-1145953b7e41] - Request started
2026-03-26 10:27:23 - app.access - INFO - [551d7b1a-d38b-4a6b-b077-1145953b7e41] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [8610eba1-9bf2-4f7e-9e41-37aadc0cbd4b] - Request started
2026-03-26 10:27:23 - app.access - INFO - [8610eba1-9bf2-4f7e-9e41-37aadc0cbd4b] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [ad3503a6-1e5c-403b-bb06-8e429f60cdc0] - Request started
2026-03-26 10:27:23 - app.access - INFO - [ad3503a6-1e5c-403b-bb06-8e429f60cdc0] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [468032a3-d519-4d26-a5d9-fb9a5dd7fe51] - Request started
2026-03-26 10:27:23 - app.access - INFO - [468032a3-d519-4d26-a5d9-fb9a5dd7fe51] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [cec5a2bf-392a-45f9-ae24-3dddb3f2f45f] - Request started
2026-03-26 10:27:23 - app.access - INFO - [cec5a2bf-392a-45f9-ae24-3dddb3f2f45f] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [599b17e2-51fe-4485-81ed-7491d2723f94] - Request started
2026-03-26 10:27:23 - app.access - INFO - [599b17e2-51fe-4485-81ed-7491d2723f94] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [7113b149-1f0f-4494-adb4-6a25e634b8e8] - Request started
2026-03-26 10:27:23 - app.access - INFO - [7113b149-1f0f-4494-adb4-6a25e634b8e8] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [744d7e91-c472-4413-a0d1-fecbff7c02ce] - Request started
2026-03-26 10:27:23 - app.access - INFO - [744d7e91-c472-4413-a0d1-fecbff7c02ce] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [005aefe4-fc20-4e52-9e28-0d80edff0528] - Request started
2026-03-26 10:27:23 - app.access - INFO - [005aefe4-fc20-4e52-9e28-0d80edff0528] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [d548c6b9-c8e3-4b08-b1e6-37b2b2dd06b6] - Request started
2026-03-26 10:27:23 - app.access - INFO - [d548c6b9-c8e3-4b08-b1e6-37b2b2dd06b6] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [1edb79be-ca23-47d4-b399-329e20b66d07] - Request started
2026-03-26 10:27:23 - app.access - INFO - [1edb79be-ca23-47d4-b399-329e20b66d07] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [e839ca00-7db3-4841-95fe-d4b96a2e2e73] - Request started
2026-03-26 10:27:23 - app.access - INFO - [e839ca00-7db3-4841-95fe-d4b96a2e2e73] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [2d19b6cd-9a3e-42a2-a6a9-5de6fea99a6f] - Request started
2026-03-26 10:27:23 - app.access - INFO - [2d19b6cd-9a3e-42a2-a6a9-5de6fea99a6f] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [3f576608-c62b-4ce1-80cf-068e339947c7] - Request started
2026-03-26 10:27:23 - app.access - INFO - [3f576608-c62b-4ce1-80cf-068e339947c7] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [7dbfbd3b-1dec-4b46-93ac-3a03d4dbfb32] - Request started
2026-03-26 10:27:23 - app.access - INFO - [7dbfbd3b-1dec-4b46-93ac-3a03d4dbfb32] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [109777c8-55d2-4644-a0d3-16aed8833788] - Request started
2026-03-26 10:27:23 - app.access - INFO - [109777c8-55d2-4644-a0d3-16aed8833788] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [af266f25-d52a-4044-b6e8-e399e72c4688] - Request started
2026-03-26 10:27:23 - app.access - INFO - [af266f25-d52a-4044-b6e8-e399e72c4688] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [fa20eeed-a503-486a-aedb-f9afdab1ea39] - Request started
2026-03-26 10:27:23 - app.access - INFO - [fa20eeed-a503-486a-aedb-f9afdab1ea39] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [5a83f1e2-c0d0-4631-9d59-37bbc207b085] - Request started
2026-03-26 10:27:23 - app.access - INFO - [5a83f1e2-c0d0-4631-9d59-37bbc207b085] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [9f614db2-b378-496b-af2f-ab8a76465975] - Request started
2026-03-26 10:27:23 - app.access - INFO - [9f614db2-b378-496b-af2f-ab8a76465975] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [b5ad0bb5-bb41-48ac-a0b4-6dbb06223ad2] - Request started
2026-03-26 10:27:23 - app.access - INFO - [b5ad0bb5-bb41-48ac-a0b4-6dbb06223ad2] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [a770fe56-4466-4293-b362-9323d8c38d26] - Request started
2026-03-26 10:27:23 - app.access - INFO - [a770fe56-4466-4293-b362-9323d8c38d26] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [0e8f90c1-6808-49a6-bb1f-b20355058181] - Request started
2026-03-26 10:27:23 - app.access - INFO - [0e8f90c1-6808-49a6-bb1f-b20355058181] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [dabcbb8e-98cb-461b-8a5e-260f9188aaf1] - Request started
2026-03-26 10:27:23 - app.access - INFO - [dabcbb8e-98cb-461b-8a5e-260f9188aaf1] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [0edb6cf1-9dec-457f-a408-a259f87fc28c] - Request started
2026-03-26 10:27:23 - app.access - INFO - [0edb6cf1-9dec-457f-a408-a259f87fc28c] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [19fad2a5-df51-4a94-90e9-85bae09ab6ea] - Request started
2026-03-26 10:27:23 - app.access - INFO - [19fad2a5-df51-4a94-90e9-85bae09ab6ea] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [aa289409-c2af-4f79-b590-c857ffbb72dd] - Request started
2026-03-26 10:27:23 - app.access - INFO - [aa289409-c2af-4f79-b590-c857ffbb72dd] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [dfc741ed-e0b3-40a6-bf4d-dde518a0b1b9] - Request started
2026-03-26 10:27:23 - app.access - INFO - [dfc741ed-e0b3-40a6-bf4d-dde518a0b1b9] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [a1c1a1a7-273f-4b34-9803-7e02cd200282] - Request started
2026-03-26 10:27:23 - app.access - INFO - [a1c1a1a7-273f-4b34-9803-7e02cd200282] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [aa02dfda-8af9-41ab-b760-5a62888d4baa] - Request started
2026-03-26 10:27:23 - app.access - INFO - [aa02dfda-8af9-41ab-b760-5a62888d4baa] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [3aa51bf5-51f4-4cbe-934d-a828a2679acd] - Request started
2026-03-26 10:27:23 - app.access - INFO - [3aa51bf5-51f4-4cbe-934d-a828a2679acd] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [03fde812-9132-46e8-8569-3e404529270b] - Request started
2026-03-26 10:27:23 - app.access - INFO - [03fde812-9132-46e8-8569-3e404529270b] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [003816db-1d51-46d2-8934-f8499e28ad1d] - Request started
2026-03-26 10:27:23 - app.access - INFO - [003816db-1d51-46d2-8934-f8499e28ad1d] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [610f6ffd-1c38-4fdf-9047-460ab7368b60] - Request started
2026-03-26 10:27:23 - app.access - INFO - [610f6ffd-1c38-4fdf-9047-460ab7368b60] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [0d793522-7e24-46a7-a0ce-5cb3ef92a8f5] - Request started
2026-03-26 10:27:23 - app.access - INFO - [0d793522-7e24-46a7-a0ce-5cb3ef92a8f5] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [5f64d3c1-a9d1-4282-82d0-b74c918ba0c0] - Request started
2026-03-26 10:27:23 - app.access - INFO - [5f64d3c1-a9d1-4282-82d0-b74c918ba0c0] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [f5427ce4-67ef-444c-afb9-240e194299a6] - Request started
2026-03-26 10:27:23 - app.access - INFO - [f5427ce4-67ef-444c-afb9-240e194299a6] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [ae5a8e60-d2ff-4507-97cf-c7c028971c9f] - Request started
2026-03-26 10:27:23 - app.access - INFO - [ae5a8e60-d2ff-4507-97cf-c7c028971c9f] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [8765f081-a591-4bcf-8ec5-a7bcd71b38b1] - Request started
2026-03-26 10:27:23 - app.access - INFO - [8765f081-a591-4bcf-8ec5-a7bcd71b38b1] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [de066f76-5aa9-49f5-8c40-087238c457df] - Request started
2026-03-26 10:27:23 - app.access - INFO - [de066f76-5aa9-49f5-8c40-087238c457df] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [3599a101-4143-4c06-819d-5b5bb5433f92] - Request started
2026-03-26 10:27:23 - app.access - INFO - [3599a101-4143-4c06-819d-5b5bb5433f92] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [34030884-3f01-4a59-96c0-62ec210e06e7] - Request started
2026-03-26 10:27:23 - app.access - INFO - [34030884-3f01-4a59-96c0-62ec210e06e7] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [c44f65b9-228d-4b2f-aab2-d8575a9f5bc5] - Request started
2026-03-26 10:27:23 - app.access - INFO - [c44f65b9-228d-4b2f-aab2-d8575a9f5bc5] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [a236fa46-9927-4f55-b117-adf6419dc389] - Request started
2026-03-26 10:27:23 - app.access - INFO - [a236fa46-9927-4f55-b117-adf6419dc389] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [caf463bd-b28e-4f05-bcae-e2bc9601ed0c] - Request started
2026-03-26 10:27:23 - app.access - INFO - [caf463bd-b28e-4f05-bcae-e2bc9601ed0c] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [f06a1441-e6ca-41ae-9fed-9f5ae6ac1880] - Request started
2026-03-26 10:27:23 - app.access - INFO - [f06a1441-e6ca-41ae-9fed-9f5ae6ac1880] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [7b0094d5-3bed-43c8-9ac9-6244720046c0] - Request started
2026-03-26 10:27:23 - app.access - INFO - [7b0094d5-3bed-43c8-9ac9-6244720046c0] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [a2549b83-796c-429e-ae7f-f8616b201e40] - Request started
2026-03-26 10:27:23 - app.access - INFO - [a2549b83-796c-429e-ae7f-f8616b201e40] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [9e75cd84-396b-41fc-a439-4994ae353083] - Request started
2026-03-26 10:27:23 - app.access - INFO - [9e75cd84-396b-41fc-a439-4994ae353083] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [dd559caa-52c2-4e9f-8a95-e0c864b2592a] - Request started
2026-03-26 10:27:23 - app.access - INFO - [dd559caa-52c2-4e9f-8a95-e0c864b2592a] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [6599ab66-2761-49fc-bdbc-352d222578e9] - Request started
2026-03-26 10:27:23 - app.access - INFO - [6599ab66-2761-49fc-bdbc-352d222578e9] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [c58ef305-c198-4add-98e3-d73bde219c85] - Request started
2026-03-26 10:27:23 - app.access - INFO - [c58ef305-c198-4add-98e3-d73bde219c85] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [2918c49a-a3aa-4e85-b458-755a45bf059c] - Request started
2026-03-26 10:27:23 - app.access - INFO - [2918c49a-a3aa-4e85-b458-755a45bf059c] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [3d8cb327-3074-411d-a469-ba2198b19a87] - Request started
2026-03-26 10:27:23 - app.access - INFO - [3d8cb327-3074-411d-a469-ba2198b19a87] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [d92500ce-dc9b-4873-a3b9-19c2258ea57c] - Request started
2026-03-26 10:27:23 - app.access - INFO - [d92500ce-dc9b-4873-a3b9-19c2258ea57c] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [b2f5571c-1371-472b-af7b-e20f2ac20aa0] - Request started
2026-03-26 10:27:23 - app.access - INFO - [b2f5571c-1371-472b-af7b-e20f2ac20aa0] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [38d95cce-eaa7-4baa-bd64-91d3e64093e0] - Request started
2026-03-26 10:27:23 - app.access - INFO - [38d95cce-eaa7-4baa-bd64-91d3e64093e0] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [89da92ee-3bb2-4bc8-accf-61080f4ef041] - Request started
2026-03-26 10:27:23 - app.access - INFO - [89da92ee-3bb2-4bc8-accf-61080f4ef041] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [f29199e3-35ca-4cbf-95c8-28021a19d7f2] - Request started
2026-03-26 10:27:23 - app.access - INFO - [f29199e3-35ca-4cbf-95c8-28021a19d7f2] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [bbdd3796-bfab-4354-828c-8451e763fbde] - Request started
2026-03-26 10:27:23 - app.access - INFO - [bbdd3796-bfab-4354-828c-8451e763fbde] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [c2e130e8-5eef-4a57-b4a2-86fd60e86a8a] - Request started
2026-03-26 10:27:23 - app.access - INFO - [c2e130e8-5eef-4a57-b4a2-86fd60e86a8a] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [37defc11-20e9-4c8c-8ae8-e661353afd3d] - Request started
2026-03-26 10:27:23 - app.access - INFO - [37defc11-20e9-4c8c-8ae8-e661353afd3d] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [38d11d4c-489a-466d-b5f4-aae0dd85e201] - Request started
2026-03-26 10:27:23 - app.access - INFO - [38d11d4c-489a-466d-b5f4-aae0dd85e201] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [0862919f-6ff8-4f67-b0fa-38b605c42f59] - Request started
2026-03-26 10:27:23 - app.access - INFO - [0862919f-6ff8-4f67-b0fa-38b605c42f59] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [91a7a8e2-f4d5-4ecd-9739-26c1b94fb1ab] - Request started
2026-03-26 10:27:23 - app.access - INFO - [91a7a8e2-f4d5-4ecd-9739-26c1b94fb1ab] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [d6283bdd-82f2-4207-b6a7-f3cf9cfae9f9] - Request started
2026-03-26 10:27:23 - app.access - INFO - [d6283bdd-82f2-4207-b6a7-f3cf9cfae9f9] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [e04c5a06-032f-4206-890f-19f43e5473a6] - Request started
2026-03-26 10:27:23 - app.access - INFO - [e04c5a06-032f-4206-890f-19f43e5473a6] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [edc49284-ae21-430d-b1f9-f69c27212b66] - Request started
2026-03-26 10:27:23 - app.access - INFO - [edc49284-ae21-430d-b1f9-f69c27212b66] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [0ed2c76c-cf3f-4e8f-a4e1-ecf4d273f371] - Request started
2026-03-26 10:27:23 - app.access - INFO - [0ed2c76c-cf3f-4e8f-a4e1-ecf4d273f371] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [38095293-41a8-4bdd-8005-bd704041823f] - Request started
2026-03-26 10:27:23 - app.access - INFO - [38095293-41a8-4bdd-8005-bd704041823f] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [1ebdffaf-53b2-4729-acb9-0f92dca719f5] - Request started
2026-03-26 10:27:23 - app.access - INFO - [1ebdffaf-53b2-4729-acb9-0f92dca719f5] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [a08faba1-0bc7-4f8f-80ac-7fbfcfdafb7f] - Request started
2026-03-26 10:27:23 - app.access - INFO - [a08faba1-0bc7-4f8f-80ac-7fbfcfdafb7f] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [3f1a11cb-802d-4a90-8118-a43583852fe3] - Request started
2026-03-26 10:27:23 - app.access - INFO - [3f1a11cb-802d-4a90-8118-a43583852fe3] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [ad219c56-6b2d-43af-b7e5-126be955b95e] - Request started
2026-03-26 10:27:23 - app.access - INFO - [ad219c56-6b2d-43af-b7e5-126be955b95e] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [eabc86d1-053a-4122-818e-f39783bffc5e] - Request started
2026-03-26 10:27:23 - app.access - INFO - [eabc86d1-053a-4122-818e-f39783bffc5e] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [f62907ae-c97b-4556-ae47-7582df924606] - Request started
2026-03-26 10:27:23 - app.access - INFO - [f62907ae-c97b-4556-ae47-7582df924606] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [109e8fad-3082-41da-b89e-168d14395288] - Request started
2026-03-26 10:27:23 - app.access - INFO - [109e8fad-3082-41da-b89e-168d14395288] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:23 - app.access - INFO - [78d1e0b3-7629-4cfc-b592-a579c5329b55] - Request started
2026-03-26 10:27:23 - app.access - INFO - [78d1e0b3-7629-4cfc-b592-a579c5329b55] - Request completed
2026-03-26 10:27:23 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
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
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
  C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.5/migration/
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

C:\Python310\lib\site-packages\fastapi\applications.py:4547
tests/integration/test_release_gate_smoke.py::test_release_gate_auth_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_system_probe_smoke
  C:\Python310\lib\site-packages\fastapi\applications.py:4547: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 2 passed, 13 warnings in 1.53s ========================
2026-03-26 10:27:31 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 10:27:31 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 10:27:32 - app.access - INFO - [819561fb-5346-4d00-b3d3-0b1847cd3424] - Request started
2026-03-26 10:27:32 - app.access - INFO - [819561fb-5346-4d00-b3d3-0b1847cd3424] - Request completed
2026-03-26 10:27:32 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 10:27:32 - app.access - INFO - [cbf73784-8d49-47a5-b2fe-2d2010e485a2] - Request started
2026-03-26 10:27:32 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=release-gate-4c4d5e6b7d92@example.com
2026-03-26 10:27:32 - app.access - INFO - [cbf73784-8d49-47a5-b2fe-2d2010e485a2] - Request completed
2026-03-26 10:27:32 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 10:27:32 - app.access - INFO - [793be281-b8f2-4e84-8ff4-1f8cb57283cd] - Request started
2026-03-26 10:27:32 - app.access - INFO - [793be281-b8f2-4e84-8ff4-1f8cb57283cd] - Request completed
2026-03-26 10:27:32 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/auth/me "HTTP/1.1 200 OK"
2026-03-26 10:27:32 - app.access - INFO - [86318633-c1f7-4ddd-81a1-72de7a30f17e] - Request started
2026-03-26 10:27:32 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=release-gate-4c4d5e6b7d92@example.com
2026-03-26 10:27:32 - app.access - INFO - [86318633-c1f7-4ddd-81a1-72de7a30f17e] - Request completed
2026-03-26 10:27:32 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 10:27:32 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 10:27:33 - app.access - INFO - [10dd1b5d-a4e4-47a8-9b2d-ba441eab47ad] - Request started
2026-03-26 10:27:33 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 10:27:33 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 10:27:33 - app.access - INFO - [10dd1b5d-a4e4-47a8-9b2d-ba441eab47ad] - Request completed
2026-03-26 10:27:33 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 10:27:33 - app.access - INFO - [6dd44b0f-8e7d-4afe-a3bf-df607d890564] - Request started
2026-03-26 10:27:33 - app.access - INFO - [6dd44b0f-8e7d-4afe-a3bf-df607d890564] - Request completed
2026-03-26 10:27:33 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
```