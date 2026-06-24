# 项目非CDM数据结构CSV说明

## 1. 文档目的

本说明文档配套：

- [project_pg_field_list_non_cdm.csv](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/docs/project_pg_field_list_non_cdm.csv)

这份 CSV 的目标不是替代现有数据库审计或结构说明文档，而是提供一份适合测试、联调、补样本、设计回归用例的项目级结构清单。

它的使用场景更直接：

- 测试同学按 `domain`、`object_name`、`test_priority` 快速筛出需要补样本的对象
- 开发同学按 `upstream_dependency`、`downstream_dependency` 梳理链路
- 联调时快速判断某字段属于正式表、兼容对象还是运行时对象

## 2. 覆盖范围

这份 CSV 只覆盖 `CDM 医疗单据主表之外`、与当前项目主业务直接相关的数据库对象。

覆盖对象包括三类：

### 2.1 正式表

主要来源：

- `backend/app/database/models/qc.py`
- `backend/app/database/models/sync.py`
- 当前仓库中已存在的 Alembic migration

覆盖域包括：

- `sys`
- `qc`
- `async`
- `sync`

代表对象包括：

- `sys_users`
- `sys_departments`
- `qc_results`
- `qc_defects`
- `qc_tasks`
- `qc_appeals`
- `qc_remediation_tasks`
- `qc_rules`
- `scoring_rules`
- `scoring_config`
- `notifications`
- `qc_async_jobs`
- `qc_async_job_events`
- `qc_async_job_dead_letters`
- `sync_visit_status`
- `sync_watermarks`

### 2.2 视图

这些对象即使未全部在 ORM 中正式声明，也已经进入当前项目的 PRD、统计口径或测试场景，因此必须进入 CSV。

代表对象包括：

- `v_qc_task_progress`
- `qc_appeals_statistics`
- `qc_remediation_statistics`
- `qc_assignee_workload`
- `qc_statistics_view`
- `v_qc_coder_ranking`

### 2.3 兼容 / 过渡 / 运行时对象

这些对象是当前测试最容易踩坑的部分，因此必须单列，而不能因为“不够正式”而省略。

代表对象包括：

- `medical_records`
- `medical_documents`
- `qc_result`
- `record_template_center`
- `rule_baseline_import_history`
- `qc_async_job_locks`
- `ai_frontpage_draft`
- `ai_mr_snapshot`
- `ai_diagnosis_snapshot`
- `ai_mr_surgery_snapshot`
- `ai_mr_cost_snapshot`

## 3. 明确排除范围

本清单明确排除：

- `CDM 医疗单据主表`
- `cdm` schema 下的大批量业务文书对象
- 典型 CDM 主数据对象，例如：
  - `mr`
  - `diagnosis`
  - `admission_record`
  - `patient_information`

但保留两个例外口径：

- `medical_records`
  - 虽与病历相关，但当前是质控链路直接依赖的兼容承载对象，必须进入清单
- `ai_frontpage_draft`
  - 虽与首页生成相关，但不属于 CDM 医疗单据主表，且当前项目逻辑直接依赖，必须进入清单
- `ai_mr_snapshot` 等 AI 首页快照表组
  - 虽放在 `cdm` schema 下，但属于系统自有扩展表，不属于原始 CDM 主数据
  - 当前用于长期保存 AI 生成首页结果与历史页面回显，必须进入清单

一句话：

`本清单排除 CDM 医疗单据主表，但保留与质控主链路直接耦合的兼容对象和首页生成扩展对象。`

## 4. CSV 字段说明

CSV 采用 `一行一个字段` 的粒度。

字段列含义如下：

- `schema_name`
  - 对象所属 schema，当前以 `public`、`qc`、`sync`、`legacy`、`frontpage` 等口径表达
- `object_type`
  - 对象类型，固定为：
    - `table`
    - `view`
    - `compat_object`
- `object_name`
  - 表名、视图名或兼容对象名
- `domain`
  - 业务域，固定口径包括：
    - `sys`
    - `qc`
    - `records`
    - `report`
    - `template`
    - `async`
    - `sync`
    - `frontpage`
    - `legacy`
- `status`
  - 当前结构状态，见下文状态值定义
- `source_of_truth`
  - 当前字段信息的主要来源，固定口径包括：
    - `ORM`
    - `Alembic`
    - `Router-Service依赖`
    - `PRD`
    - `运行时建表`
    - 或这些口径的组合
- `field_name`
  - 字段名
- `field_type`
  - 字段类型，优先按 ORM / migration 口径填写
- `nullable`
  - 是否可空
- `pk_flag`
  - 是否主键
- `index_flag`
  - 是否索引字段
- `default_value`
  - 默认值或默认表达式
- `field_desc`
  - 字段说明
- `business_usage`
  - 字段在业务里的直接用途
- `upstream_dependency`
  - 谁写入或生成该字段
- `downstream_dependency`
  - 谁消费或依赖该字段
- `test_priority`
  - 测试优先级，固定为：
    - `P0`
    - `P1`
    - `P2`
- `notes`
  - 风险、兼容说明、环境验证注意事项

## 5. 状态值定义

### 5.1 正式纳管

满足以下至少一项，且整体口径稳定：

- 已有 ORM 模型
- 已有明确 Alembic migration
- 当前项目主路径明确依赖，且结构处于正式管理中

### 5.2 兼容承载

对象在当前主链路中被直接依赖，但历史来源、纳管方式或管理边界并不完全标准化。

这类对象通常：

- 不是当前核心 ORM 主模型
- 或者来自兼容迁移、过渡期结构
- 但测试和上线验证不能忽略

### 5.3 设计存在但未正式纳管

对象在 PRD、前端、服务层或设计文档中已经存在明确语义，但当前仓库内看不到稳定的 ORM + Alembic 正式纳管证据。

### 5.4 运行时对象

对象依赖运行时 `CREATE TABLE IF NOT EXISTS` 或类似机制存在，而不是由正式 migration 统一管理。

这类对象必须单列，因为它们会直接影响：

- 环境一致性
- 冷环境启动
- RC / 上线期 schema 校验

## 6. 生成口径与取数优先级

本清单生成时采用以下优先级：

1. `ORM 模型`
2. `Alembic migration`
3. `代码实际依赖的 router / service / schema`
4. `PRD / 设计文档`
5. `运行时建表逻辑`

填写规则：

- `field_type / nullable / pk_flag / index_flag / default_value`
  - 优先取 ORM + migration
- `field_desc / business_usage / upstream_dependency / downstream_dependency`
  - 优先取现有文档 + router / service 实际读写
- 如果对象没有正式 ORM，但项目依赖强烈存在：
  - 仍必须进入 CSV
  - 且 `source_of_truth` 必须写清不是 ORM 主来源

## 7. 如何用这份 CSV 做测试准备

### 7.1 先筛 P0 对象

测试准备时，优先按 `test_priority = P0` 筛选：

- 认证与用户
- 质控结果与缺陷
- 任务与任务记录
- 申诉与整改主链路
- 运行时异步主表
- 当前 RC 重点兼容对象

### 7.2 按 domain 组织测试

推荐先按业务域分桶：

- `sys`
- `qc`
- `async`
- `sync`
- `records`
- `template`
- `frontpage`

这样更容易形成：

- 登录/权限测试
- 病历质控测试
- 任务/异步测试
- 统计/首页测试
- 模板与兼容对象测试

### 7.3 按 upstream/downstream 设计联动回归

当测试不只验证“字段存在”，而要验证“链路是否通”时，优先看：

- `upstream_dependency`
- `downstream_dependency`

例如：

- 某字段由任务运行时写入，再被统计页读取
- 某对象由记录服务读写，再被详情抽屉或报告区消费

这类字段适合设计联动回归，而不只是静态表结构验证。

## 8. 与现有文档的关系

这份 CSV 不是孤立文件，建议和以下文档配套使用：

- [PG数据结构审计报告.md](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/PG数据结构审计报告.md)
  - 看风险、缺口和纳管判断
- [PG质控域数据表说明与测试环境方案.md](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/PG质控域数据表说明与测试环境方案.md)
  - 看整体结构和测试环境方案
- [project_pg_field_list_non_cdm.csv](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/docs/project_pg_field_list_non_cdm.csv)
  - 看最终字段级测试清单

建议理解方式：

- 审计报告：回答“哪里有风险”
- 结构说明：回答“整体长什么样”
- CSV 清单：回答“测试要按什么字段和对象逐项落样本”

## 9. 当前需要特别注意的兼容对象说明

以下对象虽然已进入 CSV，但测试时要特别注意其“是否在真实环境里成立”，不能只看本地说明：

- `medical_records`
- `record_template_center`
- `rule_baseline_import_history`
- `qc_async_job_locks`

当前仓库的一个重要事实是：

- 历史文档曾提到 `20260329_000005_pg_schema_closure.py`，但仓库现已采用 `20260329_000005_test_db_state_bridge.py` + `20260330_000006_cdm_sys_move.py` 收口
- 当前仓库与测试库版本链已对齐，可按 runbook 直接执行

因此，CSV 中涉及这些对象的 `notes` 现在明确提示：

- 不得把“文档宣称已纳管”直接等同于“当前仓库已可验证”
- 目标环境和真实数据库仍需继续核表

## 10. 使用建议

如果你的目标是“做全方面测试”，推荐顺序是：

1. 先用 CSV 选出 `P0` 对象
2. 按 `domain` 建立测试样本清单
3. 对兼容对象单独做环境核表
4. 再按 `upstream/downstream` 设计联动回归

这样测试不会只停留在“字段有没有”，而能真正覆盖：

- 结构
- 链路
- 兼容对象
- 统计与页面消费

## 11. 当前交付位置

本轮交付物固定为：

- [project_pg_field_list_non_cdm.csv](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/docs/project_pg_field_list_non_cdm.csv)
- [项目非CDM数据结构CSV说明.md](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/项目非CDM数据结构CSV说明.md)
