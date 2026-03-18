# PRD-病历数据库（CDM）数据契约设计 v1.2

> v1.3 | 2026-03-19 | PostgreSQL 单栈 | 单一事实源（SSOT）| 同库分 schema 定版
>
> **v1.3 变更：新增 `ai_frontpage_draft` AI 首页草稿副表，隔离 AI 生成数据与原始 HIS 数据**

---

## 1. 背景与目标

当前病历数据相关信息分散在多个文档（接口清单、功能 PRD、专题设计）和代码中，导致协作时需要反复串联上下文才能确认表结构与字段语义。

本 PRD 目标：

1. 形成病历数据库的唯一权威数据契约（SSOT）。
2. 让 agent/开发/测试可直接定位“表结构、键规则、接口映射、迁移边界”。
3. 与已定版的质控数据库 PRD 对齐（PostgreSQL 单栈、同库部署、Alembic 管理）。

---

## 2. 范围定义

`In Scope`

1. CDM 病历域数据模型（59 张业务表）与系统同步元数据表（2 张）。
2. 三元主键规范、跨域关联规则（CDM ↔ `qc_*`）。
3. 后端核心接口到数据对象映射（`medical_records.py`、`emr_render.py`、`repository.py`）。
4. 遗留表兼容策略（`medical_records*`、`medical_documents*`、`qc_result`）。

`Out of Scope`

1. 前端页面交互细节。
2. 具体 ETL 程序实现代码。
3. 医院侧 Mongo 物理库设计细节（仅定义对接契约）。

---

## 3. 已确定架构决策（ADR）

1. `ADR-MR-001` 数据库选型：统一 PostgreSQL（开发/测试/生产同构）。
2. `ADR-MR-002` 部署策略：CDM 与质控同库部署，按 schema 隔离（`cdm` / `qc` / `sys` / `legacy`）。
3. `ADR-MR-003` 命名策略：
`CDM` 保持标准原名（如 `mr`、`diagnosis`）；
质控业务使用 `qc_` 前缀（如 `qc_results`）。
命名例外：`qc_rules`、`scoring_rules`、`scoring_config` 为历史兼容对象，暂不强制改名前缀。
4. `ADR-MR-004` 变更策略：引入 Alembic 管理 schema 变更与回滚。
5. `ADR-MR-005` 关联策略：CDM 业务主键统一为三元键 `(institute_id, patient_id, visit_id)`。

### 3.1 Schema 边界

1. `cdm`：CDM 病历域业务表（本 PRD 主体对象）。
2. `qc`：质控业务表（如 `qc_results`、`qc_tasks`），由质控 PRD管理。
3. `sys`：系统与同步管理表（如 `sync_visit_status`、`sync_watermarks`、权限/用户）。
4. `legacy`：过渡兼容表（历史 `medical_records*` / `medical_documents*`）。

---

## 4. 全局键与数据契约

### 4.1 主键标准

1. `Patient Key`：`(institute_id, patient_id)`。
2. `Visit Key`：`(institute_id, patient_id, visit_id)`。
3. 文书/明细表在 `Visit Key` 基础上叠加业务子键（如 `document_id`、`diagnosis_id`、`order_id`）。

### 4.2 跨域关联标准（CDM ↔ 质控）

1. 目标态：质控域统一通过 `visit_id` 或三元键关联 CDM。
2. 现状：`record_id` 并非恒等于 `visit_id`，当前代码同时存在 `medical_records.id`、`visit_id`、临时生成 ID 三种来源。
3. 约束：在映射统一完成前，禁止在文档和代码中声明 `record_id = visit_id` 为既成事实。
4. 对仍使用 `record_id` 的模块，必须建立稳定映射，不允许“前端随机 ID 直写数据库”。
5. 推荐新增映射表（P1）：
`record_identity_map(record_id, institute_id, patient_id, visit_id, source, created_at)`。

### 4.3 时间与审计字段规范

1. 全量同步判定字段：`update_time`。
2. 业务审计字段：`created_at/updated_at`（系统自建表）或 `last_modified_datetime`（CDM 标准表）。
3. 时间字段统一 `TIMESTAMP`（PostgreSQL）。

---

## 5. P0 核心数据字典（高频对象）

| 对象 | 表名 | 主键 | 说明 |
|---|---|---|---|
| 患者主索引 | `patient_information` | `institute_id, patient_id` | 患者基础身份 |
| 就诊索引 | `inpat_registration` | `institute_id, patient_id, visit_id` | 住院就诊主索引 |
| 病案首页主表 | `mr` | `institute_id, patient_id, visit_id` | 工作台核心列表来源，只存 HIS 原始数据 |
| 诊断明细 | `diagnosis` | `institute_id, patient_id, visit_id, diagnosis_id` | ICD-10 与诊断类型 |
| 手术明细 | `mr_surgery` | `institute_id, patient_id, visit_id, surgery_id` | ICD-9-CM-3 手术明细 |
| 费用汇总 | `mr_cost` | `institute_id, patient_id, visit_id` | 首页费用聚合 |
| 入院记录 | `admission_record` | `institute_id, patient_id, visit_id` | 入院文书全文与结构化字段 |
| 出院记录 | `discharge_record` | `institute_id, patient_id, visit_id` | 出院文书全文与结构化字段 |
| 质控结果（遗留） | `qc_result` | `id` | repository 仍在读写，待并轨 |
| **AI 首页草稿** | **`ai_frontpage_draft`** | **`id`（visit_id 唯一索引）** | **系统扩展表**；AI 从病历文书抽取的首页草稿；与 `mr` 完全隔离，不覆盖原始数据；支持 upsert |

关键索引（P0 必须）：

1. `mr(admission_datetime)`、`mr(discharge_datetime)`、`mr(discharge_dept_name)`。
2. `diagnosis(diagnosis_code)`、`diagnosis(diagnosis_type)`。
3. `inpat_registration(inpat_no)`、`inpat_registration(mr_no)`。

---

## 6. 文书族表契约（record_content 统一语义）

所有文书族表均遵循：

1. 以三元键为基础主键。
2. 包含 `record_content`（用于 LLM/渲染）。
3. 具备 `update_time` 审计能力。

文书族（核心）：

`first_course_record`、`daily_course_record`、`senior_course_record`、`postsurg_firstcourse_record`、`consultation_record`、`rescue_record`、`transfer_in_record`、`transfer_out_record`、`surgery_record`、`nursing_record`、`death_record`、`death_discussion`、`diffcase_discussion_record`、`summary_record`、`handoff_record`、`handover_record`、`presurg_summary`、`presurg_discussion`、`surgery_safecheck_record`、`surgery_risk_assessment`、`anesthesia_record`、`newborn_record`、`bloodtrans_record`、`outpat_record`、`daily_admission_record`、`daily_death_record`、`preane_surveil_record`、`postane_surveil_record`、`surgery_inform_consent`、`docpat_commu_record`、`epidemic_record`、`crisis_value_record`、`surgery_inventory_record`。

---

## 7. 费用/医嘱/检验/病理族契约

费用医保：

`medical_insurance_settlement`、`medical_insurance_settlement_cost`、`medinsur_receipt`、`inpat_bill_item`、`mr_cost`。

医嘱与申请：

`inpat_drug_order`、`inpat_nondrug_order`、`surgery_application`、`blood_application`。

检验检查病理：

`labtest_master`、`labtest_item`、`labtest_item_report`、`exam_item_report`、`pathology_exam_master`、`pathology_exam_report`。

首页扩展明细：

`mr_bloodtrans`、`mr_icu`、`mr_customize`。

---

## 8. API 到数据对象映射（当前代码口径）

### 8.1 `/api/medical-records/*`

1. `/list` -> `mr`（分页、科室、时间筛选）。
2. `/frontpage/{institute_id}/{patient_id}/{visit_id}` -> `mr + diagnosis + mr_surgery + mr_cost`（只读原始数据）。
3. `/frontpage`（PUT）-> `mr`（仅 HIS 原始数据写入，禁止 AI 数据写此接口）。
4. `/ai-frontpage-draft`（POST）-> `ai_frontpage_draft`（AI 草稿 upsert，与 `mr` 完全隔离）。
5. `/ai-frontpage-draft/{visit_id}`（GET）-> `ai_frontpage_draft`（读取已保存草稿）。
6. `/record-content/*` -> `admission_record` 或 `discharge_record`。
7. `/documents/{visit_id}` -> 多文书表按顺序聚合 `record_content`。
8. `/qc-results/*` -> 当前仍走 `qc_result`（遗留）接口。

### 8.2 `/api/v1/emr/*`

1. 优先读取遗留表：`medical_documents`、`medical_records`。
2. 回退读取 CDM：通过 `institute_id/patient_id/visit_id` 从文书表装配。
3. 结论：该路由仍处于“遗留表 + CDM 回退”混合期，需迁移到纯 CDM 契约。

## 9. 同步元数据表（系统表）

用于 PG 与对端 Mongo/CDM 源的增量同步控制：

1. `sync_visit_status`：visit 级状态机（`PENDING/PARTIAL/SYNCED/STALE/FAILED`）。
2. `sync_watermarks`：集合/表级增量游标。

要求：

1. 不承载业务查询，仅用于同步控制与追踪。
2. 与业务表隔离权限，避免误写。

---

## 10. Alembic 迁移规范

1. `revision` 命名包含域前缀：`cdm_` / `qc_` / `sync_`。
2. 禁止手工改线上表结构后不补迁移。
3. 每次迁移包含：
`DDL`、`回滚`、`索引`、`兼容说明`、`数据修复脚本（如有）`。

---

## 11. 验收标准（数据契约级）

1. Agent 无需查阅其他文档，仅凭本 PRD 可回答“主键、表归属、接口映射”。
2. 核心接口可明确追溯到对应表：`/list`、`/frontpage`、`/documents`、`/emr/render`。
3. 不再新增依赖 `medical_records*` / `medical_documents*` 的业务代码。
4. 迁移脚本可复现完整建库（CDM + Sync）。

---

## 附录 A：CDM 业务表全量清单（59）

`patient_information`、`inpat_registration`、`mr`、`mr_surgery`、`mr_cost`、`diagnosis`、`admission_record`、`discharge_record`、`qc_result`、`first_course_record`、`daily_course_record`、`senior_course_record`、`postsurg_firstcourse_record`、`consultation_record`、`rescue_record`、`transfer_in_record`、`transfer_out_record`、`surgery_record`、`labtest_item_report`、`exam_item_report`、`diffcase_discussion_record`、`death_discussion`、`death_record`、`handoff_record`、`handover_record`、`summary_record`、`presurg_summary`、`presurg_discussion`、`surgery_safecheck_record`、`surgery_risk_assessment`、`anesthesia_record`、`newborn_record`、`bloodtrans_record`、`nursing_record`、`medical_insurance_settlement`、`medical_insurance_settlement_cost`、`inpat_drug_order`、`inpat_nondrug_order`、`inpat_bill_item`、`labtest_master`、`labtest_item`、`mr_bloodtrans`、`mr_icu`、`mr_customize`、`medinsur_receipt`、`pathology_exam_master`、`pathology_exam_report`、`epidemic_record`、`outpat_record`、`surgery_application`、`docpat_commu_record`、`daily_admission_record`、`daily_death_record`、`preane_surveil_record`、`postane_surveil_record`、`surgery_inform_consent`、`crisis_value_record`、`blood_application`、`surgery_inventory_record`。

**系统扩展表（非 CDM 标准）：** `ai_frontpage_draft`（AI 首页草稿，v1.3 新增）、`qc_result`（质控结果）。

---

## 附录 B：引用源（代码）

1. `backend/app/database/models/cdm.py`
2. `backend/app/database/models/sync.py`
3. `backend/app/database/models/qc.py`
4. `backend/app/database/repository.py`
5. `backend/app/routers/medical_records.py`
6. `backend/app/routers/emr_render.py`
