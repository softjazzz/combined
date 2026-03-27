# MedQC 整改进度核对报告（2026-03-26）

## 结论
- 整改清单还没有全部完成，但 P1 主链路和“后台任务可恢复”这轮已经明显收口。
- 这次新增完成了 3 类关键工作：
  - 认证高频接口统一返回壳并保留旧字段兼容。
  - 同步运行历史补成数据库分页查询。
  - DRG 批处理和智能上传任务改为数据库留痕、启动恢复，不再只靠进程内记忆。
- 旧 `/api/system/*` 写入口现在已经硬关闭，不能再通过环境变量重新打开。
- 前端核心 token key 已统一到 `medqc_access_token / medqc_refresh_token`，并收敛了一批高频 API wrapper 到统一客户端。
- 当前仍不建议宣布“全部完工”。剩余缺口主要集中在：
  - 明文凭据治理与外部轮换；
  - API 响应壳的更大范围统一；
  - 前端剩余 legacy wrapper 收口；
  - 真实数据库迁移回滚演练；
  - 线上生产启动方式与主干分支保护的人工确认。

## 分阶段状态

### P0
- 已完成：7/10
- 进行中：3/10

仍未闭环：
- `P0-SEC-06` 密钥治理与轮换
- `P0-SEC-07` 仓库/磁盘中的明文数据库凭据清理
- `P0-REL-01` 数据库初始化失败直接退出的人工验收

### P1
- 已完成：9/14
- 进行中：5/14

本轮新增完成：
- `P1-DATA-03` 运行历史入库并补分页
- `P1-FE-02` token key 统一
- `P1-ARCH-01` 旧同步写入口彻底关停
- `P1-DOC-01` 核心部署/启动文档对齐

当前仍在进行中：
- `P1-API-01` 统一 API 响应壳
  - 高频认证链路已经统一。
  - 但还没有证据表明抽样 30 个端点全部一致。
- `P1-FE-01` 前端 HTTP 客户端收敛
  - 核心 wrapper 已切到统一客户端。
  - 仍有部分 legacy API wrapper 未收口。
- `P1-CI-01` 后端单元+集成门禁
  - 工作流和 smoke 已通过。
  - 主干分支保护是否强制，仍属于平台侧确认项。
- `P1-CI-02` 迁移升级/回滚校验
  - 现有门禁已覆盖契约与 smoke。
  - 真实数据库“升上去再回下来”的演练还没补。
- `P1-OPS-01` 统一生产启动方式
  - 代码和关键文档已切到构建产物路线。
  - 线上是否已完全停用旧方式，还需人工确认。

### P2
- 已完成：10/12
- 进行中：2/12

本轮新增完成：
- `P2-PERF-01` 上传/批处理改为可恢复后台任务
  - API 只负责受理任务。
  - 状态落到数据库。
  - 服务重启后会恢复未完成任务。
- `P2-QA-02` 性能基线压测与容量承诺文档
  - 本地压测流程、结果产物和正式报告已落地。

当前仍在进行中：
- `P2-OBS-03` 告警策略落地
  - 规则和校验已在仓库。
  - 真实告警触达演练尚未留存证据。
- `P2-SEC-01` 关键操作审计日志
  - 审计已覆盖更多关键动作。
  - 仍建议补人工验收记录，确认线上可追溯性。

## 本轮新增证据
- 后台任务恢复：
  - `backend/app/services/async_job_store.py`
  - `backend/app/services/drg/batch_task_service.py`
  - `backend/app/services/smart_upload_async_service.py`
  - `backend/alembic/versions/20260326_000003_async_job_tables.py`
- 认证与同步收口：
  - `backend/app/routers/auth.py`
  - `backend/app/services/sync_run_history.py`
  - `backend/app/routers/sync.py`
  - `backend/app/routers/system_config.py`
  - `backend/app/main.py`
- 前端收口：
  - `src/utils/auth-token.ts`
  - `src/services/apiService.ts`
  - `src/services/simplifiedApiService.ts`
  - `src/api/appeal.ts`
  - `src/api/rectification.ts`
  - `src/api/dashboard.ts`
  - `src/api/defects.ts`
  - `src/api/drg.ts`

## 本轮验证结果
- 后端定向测试：`37` 项通过
  - `backend/tests/unit/test_drg_batch_tasks_router.py`
  - `backend/tests/unit/test_smart_upload_async.py`
  - `backend/tests/unit/test_auth_sync_contract.py`
  - `backend/tests/unit/test_sync_consistency.py`
  - `backend/tests/unit/test_sync_router.py`
- 门禁/契约验证：`7` 项通过
  - `backend/tests/unit/test_openapi_contract.py`
  - `backend/tests/integration/test_release_gate_smoke.py`
- 前端定向测试：`17` 项通过
  - `src/utils/__tests__/auth-token.spec.ts`
  - `src/utils/__tests__/api-envelope.spec.ts`
  - `src/api/__tests__/apiService.trace.spec.ts`

## 当前未完成事项
1. 清理和轮换仓库中的明文凭据。
2. 补真实数据库迁移升级/回滚演练。
3. 补平台侧主干分支保护确认。
4. 确认线上已经完全改为构建产物启动。
5. 继续收口剩余前端 legacy API wrapper。
6. 扩大统一响应壳覆盖面，补更多契约抽样。
7. 完成一次真实告警触达演练并留档。
