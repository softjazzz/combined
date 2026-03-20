# MedQC Demo->Prod Database Plan Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 2026-03-23~2026-03-29 完成可演示的全功能数据库数据面，在 2026-03-30~2026-04-05 完成生产切换到真实 Mongo 抽取且不与演示数据混淆。  
**Architecture:** 统一采用“本地 PostgreSQL 作为业务读写库”，数据来源按环境区分：Demo 用 mock seed，Prod 用 Mongo 同步入 PG；禁止把“数据源切换”理解为运行时直读 Mongo API。  
**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, Alembic, Mongo Sync Pipeline

---

## 1. 现状分析（静态审查）

### 1.1 已完成（代码已具备）

1. Mongo 同步配置与触发链路已实现（UI + API + Service）  
   - `SystemConfigView` 已调用 `/api/v1/sync/config/mongo`、`/api/v1/sync/test-connection/mongo`、`/api/v1/sync/trigger`。  
   - 后端 `sync.py` 提供 `/status`、`/trigger`、`/config/mongo`、`/test-connection/mongo`、`/statistics`。  
   - `mongo_sync.py` 具备 `sync_watermarks`、`sync_visit_status`、`ON CONFLICT` UPSERT。

2. QC 主体表/视图与路由改造已推进  
   - `qc_views.sql` 已包含 6 个视图（含 `qc_statistics_view`、`v_qc_coder_ranking`）。  
   - 最近提交链显示 D1~D5 主体改造与验收测试已落地（见 git log）。

3. split schema 的 Alembic 脚手架已存在  
   - `20260315_000001_baseline_pg_schema.py`  
   - `20260315_000002_split_schema_layout.py`  
   - `RUNBOOK_SPLIT_SCHEMA_ALEMBIC.md` 已给出 precheck/stamp/upgrade/postcheck。

### 1.2 未完成/有风险（本次必须补齐）

1. “数据源切换”存在认知断层（高风险）  
   - `repository.py` 的 `DATA_SOURCE=mongo_api` 对应 `MongoApiRepository` 仍大量 `NotImplementedError`。  
   - 当前可用路径是“Mongo -> 同步入 PG -> 业务读 PG”，不是“业务运行时直读 Mongo API”。

2. split schema 尚未形成环境级闭环（高风险）  
   - 代码支持 `DB_SCHEMA_MODE=split`，但默认仍是 `single`。  
   - `.env`/`.env.example` 未形成一套清晰的 split 配置模板。  
   - 是否已在目标环境执行 Alembic upgrade，当前无法仅靠静态代码确认。

3. 演示数据面偏 CDM，QC 业务态 mock 仍可能不完整（中高风险）  
   - `seed_full_testdata.py` 主要覆盖 CDM 相关病历表。  
   - 需要补“任务/缺陷/申诉/整改/通知/统计”的可演示链路数据，且质控结果要由真实规则运行产生。

4. 配置基线不一致（中风险）  
   - `.env.example` 仍有 `DOCUMENTS_TABLE=medical_documents_test`，与当前“默认正式表名”的目标不一致。  
   - 可能导致新环境初始化时表名误用。

5. P1 权限模型未完全落地到 ORM（中风险）  
   - split migration里包含 `sys_roles/sys_role_permissions` 迁移目标。  
   - 当前 `models/qc.py` 仅见 `sys_users/sys_departments`，需确认是否由其它模型或 SQL 创建，否则新库会缺表。

---

## 2. 关键结论（给管理层/客户演示口径）

1. **建议采用“双环境双库 + 每库分 schema”**  
   - `medqc_demo`：用于 2026-03-23 当周演示。  
   - `medqc_prod`：用于 2026-03-30 当周生产。  
   - 两个库都采用 `cdm/qc/sys/legacy` schema 分离，避免跨环境数据污染。

2. **统一业务读写入口为 PG，不做运行时直连 Mongo API 切换**  
   - Demo：mock seed -> PG(cdm) -> 质控计算 -> PG(qc)。  
   - Prod：Mongo sync -> PG(cdm) -> 质控计算 -> PG(qc)。  
   - 好处：前后端接口不变，演示与生产差异仅在“数据注入层”。

3. **下周演示的“质控结果”必须实时或预跑生成，不要硬编码结果**  
   - 规则和结果都落表；结果由 QC 引擎对 mock 病历实际跑出。  
   - 演示时可重复“重跑质控 -> 指标变化”验证可信度。

---

## 3. 任务清单（按日期）

### Task 1: 2026-03-16 ~ 2026-03-18（架构封版 + 配置基线）

**Files:**
- Modify: `apps/medqc-web/backend/.env.example`
- Modify: `apps/medqc-web/backend/docs/ALEMBIC_MIGRATION.md`
- Modify: `apps/medqc-web/backend/docs/RUNBOOK_SPLIT_SCHEMA_ALEMBIC.md`
- Modify: `apps/medqc-web/backend/app/database/repository.py` (文案与弃用提示)
- Test: `apps/medqc-web/backend/tests/test_prd_acceptance.py`（补充配置基线断言）

**Checklist:**
1. 明确 ADR：不走 `DATA_SOURCE=mongo_api` 生产链路，唯一生产链路是 Mongo 同步入 PG。  
2. `.env.example` 增加并默认化：`DB_SCHEMA_MODE=split`、`DB_SEARCH_PATH=public,qc,sys,cdm,legacy`。  
3. `.env.example` 将 `DOCUMENTS_TABLE` 统一为 `medical_documents`（非 `_test`）。  
4. 在 `repository.py` 注释和日志中标记 `mongo_api` 分支为未实现/禁用，防止误切。  
5. 形成“demo/prod 两套环境变量样例模板”并入文档。

**Definition of Done:**
1. 新同事仅按 `.env.example` 即可完成 split 模式启动。  
2. 文档中不存在“可直接切 mongo_api”误导表述。  
3. 验收脚本能检测上述关键变量是否就绪。

### Task 2: 2026-03-18 ~ 2026-03-21（演示数据面补齐）

**Files:**
- Modify/Create: `apps/medqc-web/backend/scripts/seed_full_testdata.py`
- Create: `apps/medqc-web/backend/scripts/seed_qc_demo_data.py`（任务/缺陷/申诉/整改/通知）
- Create: `apps/medqc-web/backend/scripts/generate_qc_results_from_mock.py`
- Test: `apps/medqc-web/backend/tests/`（新增脚本级验收）

**Checklist:**
1. CDM mock 数据覆盖演示涉及的所有病历入口。  
2. 新增 QC 业务态 seed：`qc_tasks/qc_task_records/qc_appeals/qc_remediation_* /notifications/...`。  
3. 执行“真实规则+引擎”批量跑数，写入 `qc_results/qc_defects`，禁止硬编码结果。  
4. 生成演示快照清单（记录行数、时间戳、可回滚 SQL）。

**Definition of Done:**
1. Workstation V4、任务、缺陷、申诉、整改、统计页面均有真实可联动数据。  
2. 质控结果来自实际计算链路。  
3. 一键清理脚本可移除演示数据（按 `institute_id='LX001'` 或专用 demo 标识）。

### Task 3: 2026-03-21 ~ 2026-03-23（演示前验收）

**Files:**
- Create: `apps/medqc-web/backend/scripts/verify_demo_readiness.py`
- Modify: `apps/medqc-web/backend/tests/test_prd_acceptance.py`（增加“视图依赖表存在性”与“数据完整性”断言）

**Checklist:**
1. 验证 6 视图全部可查询且无 `unknown`/空依赖。  
2. 验证关键接口 200 且返回非空数据。  
3. 验证“刷新队列/筛选/统计”前端关键流程可走通。  
4. 输出演示验收报告（可直接给客户演示前彩排）。

**Definition of Done:**
1. 演示脚本一键通过。  
2. 客户演示路径无“暂无病历记录”空白页。  
3. 若失败可定位到具体缺表/缺视图/缺数据。

### Task 4: 2026-03-24 ~ 2026-03-30（生产切换准备）

**Files:**
- Modify: `apps/medqc-web/backend/app/services/etl_config.py`
- Modify: `apps/medqc-web/backend/app/services/mongo_sync.py`
- Modify: `apps/medqc-web/backend/app/routers/sync.py`
- Docs: `apps/medqc-web/backend/docs/RUNBOOK_SPLIT_SCHEMA_ALEMBIC.md`

**Checklist:**
1. 在 staging 执行 Alembic：baseline -> split schema -> postcheck。  
2. 配置真实 Mongo 连接并通过 `/api/v1/sync/test-connection/mongo`。  
3. 先跑小批量（指定 tier/时间窗口）验证字段映射，再全量。  
4. 对比抽取行数、更新时间、失败重试数；出具切换报告。  
5. 生产切换窗口内先停写、后补偿、再放量。

**Definition of Done:**
1. 生产 PG 的 `cdm/qc/sys` 对象与预期一致。  
2. Mongo 增量同步稳定，错误率可控。  
3. 业务接口无感切换（前端无需改 API）。

---

## 4. 完成度看板（截至 2026-03-16）

### 已完成（约 70%）
1. P0 表/视图与主要路由去内存回退（按最近提交链）。  
2. Mongo 同步 API 与服务链路已具备。  
3. Alembic + split schema 脚手架和 runbook 已存在。

### 未完成（约 30%，但都是上线关键项）
1. 环境级 split schema 真正落地与验收。  
2. 演示全链路数据准备（含 QC 业务态 + 实跑结果）。  
3. 配置/文档去歧义（`DATA_SOURCE` 与 `mongo_api` 误导）。  
4. P1 角色权限相关表在新环境建表的一致性确认。

---

## 5. 当前可直接执行的最小命令清单

1. 演示库初始化（示例）
   - `alembic -c alembic.ini upgrade head`
2. 生成 CDM mock
   - `python -m scripts.seed_full_testdata`
3. 生成 QC 规则（如需要）
   - `python -m scripts.seed_qc_rules`
4. 触发 Mongo 抽取（生产/联调）
   - `POST /api/v1/sync/trigger { "source": "mongo", "tier": "all" }`

> 注：本次审查环境缺少本地 Python/psql 运行条件，结论基于静态代码与提交链；上线前需在目标环境执行一次动态验收。

