# Customer Sample Two-Stage Incremental Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将客户样本验证同步改为“主记录优先可见、明细后台整理、后续按可靠水位增量更新”，缩短病例进入病历池的等待时间并减少在院病例重复传输。

**Architecture:** 保留一个同步任务和现有 API，在任务内部依次执行 `primary_visibility` 与 `detail_sync` 两个阶段。主记录阶段始终快速核对 `mr / inpat_registration / admission_record` 并立即回写样本匹配；明细阶段依据每份病历、每张源表的同步能力选择“更新时间水位、只增不改时间水位、按病历全量重拉”三种策略，只有本地写入成功后才推进水位。发生变化的病历才刷新 Bundle，出院状态转换时执行一次完整收口同步。

**Tech Stack:** FastAPI、SQLAlchemy、PostgreSQL、Alembic、Python `ThreadPoolExecutor`、Vue 3、TypeScript、Ant Design Vue、pytest、Vitest。

---

## 1. 已确认的产品口径

1. 第一次同步分为两个阶段：
   - 第一阶段：同步主记录、住院登记、入院记录，使病例尽快出现在病历池。
   - 第二阶段：后台同步病程、医嘱、检查检验、手术、麻醉、输血等明细。
2. 第一阶段完成后前端显示：
   - `病历已进入样本池，文书整理中`
3. 后续同步同时处理：
   - 新增记录；
   - 已存在记录的修改；
   - 在院转出院状态变化。
4. 没有可靠更新时间的源表不得伪装成增量同步：
   - 有可靠更新时间：按水位拉取；
   - 只新增且有稳定记录时间：按记录时间水位拉取；
   - 无可靠更新时间：按该病历重拉整表数据。
5. 第一版不处理源库物理删除：
   - 有软删除字段时同步删除状态；
   - 无删除标记时，出院收口同步和定期全量核对负责发现差异。
6. 不通过简单提高并发数解决性能问题；表级并发默认 3，上限 6。

## 2. 当前代码基线

- 同步入口：`backend/app/routers/qc_sample_pools.py`
- 同步服务：`backend/app/services/custom_qc_sample_pool_service.py:5990`
- 远端拉取及本地 UPSERT：`backend/app/services/etl_sync.py:2480`
- 前端 API：`src/services/manual-case-sample-service.ts:433`
- 前端进度：`src/views/workstation-v4/CustomerSampleValidationView.vue:3129`
- 当前已有能力：
  - 明细表 3 路并发；
  - 本地每批 500 行 UPSERT；
  - 当前在院、期间出院及合并范围；
  - `mr` 缺失时使用住院登记或入院记录识别在院患者；
  - running、final、domain Bundle 刷新。

## 3. 状态与失败语义

| 场景                       | 任务状态                | 病历池表现                 | 水位处理                      |
| -------------------------- | ----------------------- | -------------------------- | ----------------------------- |
| 主记录阶段失败             | `failed`                | 不承诺病历可见             | 不推进                        |
| 主记录阶段成功             | `running`               | 病历可见，显示“文书整理中” | 只推进成功主表                |
| 明细表部分成功、必需表失败 | `failed`                | 病历仍可见，文书未就绪     | 成功表推进，失败表不推进      |
| 可选源表不存在             | `completed` + warnings  | 已有文书正常展示           | 记录受控 warning              |
| 明细全部成功               | `completed`             | 文书就绪，可质控           | 全部成功表推进                |
| 无任何变化                 | `completed`             | 保持原状态                 | 水位仅更新时间，不重建 Bundle |
| 在院转出院                 | `running` → `completed` | 完成后切换为终末状态       | 强制完整收口                  |

前端不得展示源库 IP、端口、SQL 或驱动异常；只展示“源数据库暂时不可用”“部分文书尚未同步完成”等客户语言。

## 4. 同步水位数据模型

新增表 `custom_qc_sample_sync_cursors`：

```text
id                          UUID / VARCHAR(36), PK
source_identity             VARCHAR(128), NOT NULL
institute_id                VARCHAR(128), NOT NULL
patient_id                  VARCHAR(128), NOT NULL
visit_id                    VARCHAR(128), NOT NULL
table_name                  VARCHAR(128), NOT NULL
strategy                    VARCHAR(32), NOT NULL
watermark_column            VARCHAR(128), NULL
watermark_value             TIMESTAMPTZ, NULL
last_success_at             TIMESTAMPTZ, NULL
last_full_sync_at           TIMESTAMPTZ, NULL
source_row_count            INTEGER, NOT NULL DEFAULT 0
content_signature           VARCHAR(128), NULL
last_job_id                 VARCHAR(36), NULL
schema_version              VARCHAR(64), NOT NULL
created_at                  TIMESTAMPTZ, NOT NULL
updated_at                  TIMESTAMPTZ, NOT NULL
```

唯一约束：

```text
(source_identity, institute_id, patient_id, visit_id, table_name)
```

`source_identity` 使用不含密码的稳定数据源标识，例如：

```python
sha256(f"{host}:{port}/{database}:{schema}".encode()).hexdigest()[:32]
```

不得保存数据库密码或完整连接串。

## 5. 源表增量能力契约

扩展 `list_sync_tables()` 返回的表配置：

```python
{
    "name": "daily_course_record",
    "source_table": "daily_course_record",
    "key_fields": ["institute_id", "patient_id", "visit_id", "document_id"],
    "sync_phase": "detail",
    "incremental_strategy": "updated_at",
    "watermark_columns": ["update_time", "modify_time"],
    "soft_delete_columns": ["is_deleted", "delete_flag"],
    "bundle_domains": ["course", "domain"],
}
```

受控策略只允许：

```python
INCREMENTAL_STRATEGIES = {
    "updated_at",
    "append_only_record_time",
    "full_visit_reload",
}
```

主记录表固定：

```python
PRIMARY_VISIBILITY_TABLES = (
    "mr",
    "inpat_registration",
    "admission_record",
)
```

## 6. 开发任务

### Task 1: 生成源表增量能力审计报告

**Files:**

- Create: `backend/scripts/audit_sample_sync_incremental_capabilities.py`
- Create: `docs/reports/customer-sample-sync-incremental-capabilities.md`
- Test: `backend/tests/unit/test_sample_sync_incremental_capability_audit.py`

**Steps:**

1. 编写失败测试，覆盖：
   - 优先识别 `update_time / modify_time / updated_at`；
   - 无更新时间但有稳定主键和记录时间时归类为 `append_only_record_time`；
   - 其他表归类为 `full_visit_reload`；
   - 报告不得输出连接密码。
2. 运行：

```powershell
python -m pytest backend/tests/unit/test_sample_sync_incremental_capability_audit.py -q
```

预期：首次失败。

3. 实现只读审计脚本，输出每张表：
   - 主键；
   - 更新时间候选字段；
   - 记录时间候选字段；
   - 删除标记；
   - 推荐策略；
   - 风险说明。
4. 使用客户导出结构或测试数据库执行一次审计。
5. 复核报告中约 50 张表均有明确策略。
6. 提交：

```powershell
git add backend/scripts/audit_sample_sync_incremental_capabilities.py backend/tests/unit/test_sample_sync_incremental_capability_audit.py docs/reports/customer-sample-sync-incremental-capabilities.md
git commit -m "同步：增加源表增量能力审计"
```

### Task 2: 建立同步水位表和仓储边界

**Files:**

- Create: `backend/alembic/versions/20260731_000024_add_sample_sync_cursors.py`
- Create: `backend/app/services/sample_sync_cursor_repository.py`
- Test: `backend/tests/unit/test_sample_sync_cursor_repository.py`

**Steps:**

1. 编写水位读写测试：

```python
def test_cursor_advances_only_after_successful_write():
    ...

def test_cursor_isolated_by_source_identity_and_visit():
    ...
```

2. 运行测试并确认失败。
3. 增加 Alembic 迁移、唯一约束和查询索引。
4. 实现：

```python
class SampleSyncCursorRepository:
    def get_many(self, *, source_identity, visit_keys, table_names): ...
    def mark_success(self, *, visit_key, table_name, watermark_value, job_id): ...
    def mark_full_sync(self, *, visit_key, table_name, row_count, signature, job_id): ...
```

5. 确保失败路径不更新水位。
6. 运行：

```powershell
python -m pytest backend/tests/unit/test_sample_sync_cursor_repository.py -q
python -m alembic upgrade head
python -m alembic current
```

7. 提交：

```powershell
git add backend/alembic/versions/20260731_000024_add_sample_sync_cursors.py backend/app/services/sample_sync_cursor_repository.py backend/tests/unit/test_sample_sync_cursor_repository.py
git commit -m "同步：增加病历源表同步水位"
```

### Task 3: 将单个同步任务拆成两个内部阶段

**Files:**

- Modify: `backend/app/services/custom_qc_sample_pool_service.py:5990-6325`
- Modify: `backend/app/routers/qc_sample_pools.py:320-450`
- Test: `backend/tests/unit/test_custom_qc_sample_pool_service.py`
- Test: `backend/tests/unit/test_qc_sample_pools_router.py`

**Steps:**

1. 编写失败测试：
   - 主记录表必须先于明细表执行；
   - `admission_record` 可单独使在院患者进入病历池；
   - 主阶段结束立即调用 `match_pool_items()`；
   - 明细同步时任务仍为 `running`；
   - 主阶段失败时不进入明细阶段。
2. 运行聚焦测试确认失败。
3. 将当前 `sync_pool_records()` 拆为：

```python
def sync_primary_visibility(...): ...
def sync_detail_tables(...): ...
def sync_pool_records(...):
    primary = sync_primary_visibility(...)
    match_result = self.match_pool_items(pool_id=pool_id)
    emit_progress(step_key="primary_visible", ...)
    detail = sync_detail_tables(...)
    return merge_sync_summary(primary, detail, match_result)
```

4. `primary_visible` 进度至少返回：

```json
{
  "step_key": "primary_visible",
  "step_label": "病历已进入样本池，文书整理中",
  "record_progress": {
    "total": 30,
    "completed": 30,
    "basis": "primary_record_visible"
  },
  "documents_ready": 0
}
```

5. 明细表继续使用现有 3 路表级并发，不增加病历级并发。
6. 运行聚焦测试。
7. 提交：

```powershell
git add backend/app/services/custom_qc_sample_pool_service.py backend/app/routers/qc_sample_pools.py backend/tests/unit/test_custom_qc_sample_pool_service.py backend/tests/unit/test_qc_sample_pools_router.py
git commit -m "同步：主记录优先进入客户样本池"
```

### Task 4: 实现可靠的三策略增量拉取

**Files:**

- Modify: `backend/app/services/etl_sync.py`
- Modify: `backend/app/services/custom_qc_sample_pool_service.py`
- Modify: `backend/app/data/sync_table_groups.json` 或当前表配置来源
- Test: `backend/tests/unit/test_sync_consistency.py`
- Test: `backend/tests/unit/test_custom_qc_sample_pool_service.py`

**Steps:**

1. 编写失败测试，至少覆盖：
   - 首次无水位时全量拉取；
   - `update_time` 水位只返回新增和修改行；
   - 查询使用 10 分钟重叠窗口；
   - `full_visit_reload` 不使用伪更新时间；
   - 本地 UPSERT 失败时不推进水位；
   - 重叠窗口返回重复行时不会产生重复记录。
2. 实现远端查询参数：

```python
fetch_remote_rows_by_visit_keys(
    ...,
    watermark_column="update_time",
    watermark_after=cursor.watermark_value - timedelta(minutes=10),
)
```

3. 对 `full_visit_reload`：
   - 拉取该病历在该表的全部行；
   - 计算稳定内容摘要；
   - 摘要未变化时跳过 Bundle 刷新。
4. 本地事务提交成功后再调用 `cursor_repository.mark_success()`。
5. 将变化病历累计到：

```python
changed_visit_keys_by_domain: dict[str, set[VisitKey]]
```

6. 运行聚焦测试。
7. 提交：

```powershell
git add backend/app/services/etl_sync.py backend/app/services/custom_qc_sample_pool_service.py backend/app/data backend/tests/unit/test_sync_consistency.py backend/tests/unit/test_custom_qc_sample_pool_service.py
git commit -m "同步：按源表能力增量拉取病历明细"
```

### Task 5: 处理在院转出院和删除边界

**Files:**

- Modify: `backend/app/services/custom_qc_sample_pool_service.py`
- Modify: `backend/app/services/etl_sync.py`
- Test: `backend/tests/unit/test_custom_qc_sample_pool_service.py`

**Steps:**

1. 编写失败测试：
   - 上次状态在院、本次出现出院时间时触发 `final_reconciliation`；
   - 完整收口不受普通水位限制；
   - 软删除标记正确 UPSERT；
   - 无软删除字段时不推断物理删除。
2. 实现状态转换检测：

```python
if previous_discharge_time is None and current_discharge_time is not None:
    force_full_reconciliation = True
```

3. 收口同步完成后刷新 final Bundle。
4. 在结果 summary 中记录：

```json
{
  "final_reconciliation": true,
  "hard_delete_reconciliation": "not_supported"
}
```

5. 运行聚焦测试并提交。

### Task 6: 只为发生变化的病历刷新 Bundle

**Files:**

- Modify: `backend/app/services/custom_qc_sample_pool_service.py`
- Modify: `backend/app/services/bundles/assembly.py`
- Test: `backend/tests/unit/test_custom_qc_sample_pool_service.py`
- Test: `backend/tests/unit/test_domain_bundle_assembly.py`

**Steps:**

1. 编写失败测试：
   - 无变化不调用任何 Bundle 刷新；
   - 仅病程变化只刷新对应病历；
   - 同一病历多张表变化只刷新一次；
   - running、final、domain 共享同一次材料读取。
2. 增加统一入口：

```python
refresh_all_bundle_variants_for_rows(
    rows=changed_rows,
    policy_version="sample_pool_incremental_sync",
)
```

3. 在统一入口内读取一次 Material Snapshot，再派生所需 Bundle。
4. 替换当前三个顺序刷新调用。
5. 运行聚焦测试并提交。

### Task 7: 前端展示两个同步阶段

**Files:**

- Modify: `src/views/workstation-v4/CustomerSampleValidationView.vue`
- Modify: `src/views/workstation-v4/customer-sample-validation/types.ts`
- Test: `tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts`

**Steps:**

1. 编写失败测试：
   - 收到 `primary_visible` 后显示“病历已进入样本池，文书整理中”；
   - 主记录可见后立即刷新病历池一次；
   - 继续轮询明细进度；
   - 明细失败时病例仍保留；
   - 不展示内部错误、IP 或端口。
2. 扩展同步 summary 类型：

```typescript
type SyncPhase =
  | 'resolving'
  | 'primary_sync'
  | 'primary_visible'
  | 'detail_sync'
  | 'bundle_refresh'
  | 'completed'
```

3. 在轮询器中只在阶段首次进入 `primary_visible` 时调用：

```typescript
await Promise.all([loadPools(), loadRecords()])
```

4. 状态条显示：
   - 主阶段：`正在同步病历基本信息`
   - 明细阶段：`病历已进入样本池，文书整理中`
   - 完成：`文书已就绪`
5. 运行：

```powershell
npx vitest run tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts -t 同步 --silent
npx eslint src/views/workstation-v4/CustomerSampleValidationView.vue --no-fix --quiet
```

6. 提交。

### Task 8: 增加配置、限流和重复任务保护

**Files:**

- Modify: `backend/app/core/settings.py`
- Modify: `backend/.env.example`
- Modify: `backend/app/services/custom_qc_sample_pool_service.py`
- Test: `backend/tests/unit/test_custom_qc_sample_pool_service.py`

**Configuration:**

```env
SAMPLE_SYNC_DETAIL_TABLE_WORKERS=3
SAMPLE_SYNC_DETAIL_TABLE_WORKERS_MAX=6
SAMPLE_SYNC_UPSERT_BATCH_SIZE=500
SAMPLE_SYNC_WATERMARK_OVERLAP_MINUTES=10
```

**Steps:**

1. 编写配置上下限测试。
2. 将硬编码的 `3 / 500 / 10` 改为配置读取。
3. 同一数据源、同一样本池只允许一个活动同步任务。
4. 不允许病历级并发与表级并发同时无界放大。
5. 运行测试并提交。

### Task 9: 真实样本性能验收

**Files:**

- Create: `backend/scripts/benchmark_customer_sample_sync.py`
- Create: `docs/reports/customer-sample-sync-performance-acceptance.md`

**Test sets:**

- 8 份病例；
- 30 份病例；
- 100 份病例；
- 至少包含在院、出院、手术、输血、检查检验病例。

**Metrics:**

```text
source_resolve_ms
primary_visible_ms
detail_sync_ms
bundle_refresh_ms
total_duration_ms
rows_pulled
rows_upserted
tables_skipped_unchanged
visits_refreshed
retry_count
```

**Acceptance:**

1. 主记录阶段完成后病例均可在病历池看到。
2. 在院和出院病例均不丢失。
3. 首次同步完整性与当前全量同步一致。
4. 第二次无变化同步不重建 Bundle。
5. 新增一份病程后只同步变化数据并刷新对应病例。
6. 修改旧文书后能够被 `update_time` 水位识别。
7. 在院转出院执行完整收口。
8. 相比当前基线：
   - 病历首次可见时间下降至少 70%；
   - 30 份病例第二次无变化同步耗时下降至少 70%；
   - 首次完整同步耗时下降至少 40%；
   - 客户源库连接错误率不增加。

## 7. 发布顺序

1. 先部署 Alembic 水位表迁移。
2. 后端以功能开关关闭增量模式部署：

```env
SAMPLE_SYNC_INCREMENTAL_ENABLED=false
```

3. 在测试样本池执行首次全量同步。
4. 打开增量开关，执行无变化、增加病程、修改旧文书和在院转出院验证。
5. 前端发布两阶段状态展示。
6. 客户机先对 8 份病例灰度，再扩大到 30 份和 100 份。
7. 出现增量异常时关闭开关，回退到现有全量同步；水位表保留，不影响旧链路。

## 8. 本阶段明确不做

- 不接入 PostgreSQL 逻辑复制、CDC 或数据库日志解析。
- 不用文书记录时间冒充更新时间。
- 不推断源库物理删除。
- 不把表级并发直接提高到 10 以上。
- 不重写客户样本池、质控引擎或 Canonical 结果链。
- 不在前端重新解释数据是否完整。

## 9. 完成定义

只有同时满足以下条件才算完成：

1. 主记录阶段结束后病例无需等待全部明细即可进入病历池。
2. 前端明确显示“病历已进入样本池，文书整理中”。
3. 约 50 张源表全部有受控增量策略。
4. 水位仅在本地事务成功后推进。
5. 新增和修改数据均能被识别。
6. 无可靠更新时间的表使用全病历重拉，不伪装增量。
7. 无变化同步不重复构建 Bundle。
8. 在院转出院能够完整收口。
9. 8、30、100 份真实脱敏病例完成准确性与性能验收。
10. 数据库迁移、后端聚焦测试、前端聚焦测试和客户机灰度均通过。
