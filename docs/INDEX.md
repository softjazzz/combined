# MedQC 活文档索引

> 历史过程计划、阶段总结、验收报告与旧版设计文档已完整归档于 Git Tag `archive/docs-pre-cleanup-202611`（`git show archive/docs-pre-cleanup-202611:<path>` 可随时查阅）。

## 入口与本地开发

| 文档路径 | 用途 |
| --- | --- |
| [`INDEX.md`](INDEX.md) | MedQC 活文档总索引与历史归档入口 |
| [`../README.md`](../README.md) | Monorepo 入口与本地启动 |
| [`../DEVELOPMENT_PORTS.md`](../DEVELOPMENT_PORTS.md) | 开发端口、代理与冲突排查 |
| [`../apps/medqc-web/README.md`](../apps/medqc-web/README.md) | MedQC 本地启动、源码入口与验证命令 |
| [`../apps/medqc-web/backend/docs/ALEMBIC_MIGRATION.md`](../apps/medqc-web/backend/docs/ALEMBIC_MIGRATION.md) | PostgreSQL 迁移与存量库接入 |
| [`../apps/medqc-web/docs/plans/PROJECT_ROLLING_TODO.md`](../apps/medqc-web/docs/plans/PROJECT_ROLLING_TODO.md) | 现行专题与历史接续入口，由应用协作指令引用 |

## 工作台 UI

| 文档路径 | 用途 |
| --- | --- |
| [`../apps/medqc-web/docs/0418/UI/WorkstationV4-医疗浅色-DESIGN.md`](../apps/medqc-web/docs/0418/UI/WorkstationV4-医疗浅色-DESIGN.md) | 工作台浅色医疗设计与组件规范 |

## 部署与运维

| 文档路径 | 用途 |
| --- | --- |
| [`../apps/medqc-web/docs/deployment/P2_RELEASE_RUNBOOK.md`](../apps/medqc-web/docs/deployment/P2_RELEASE_RUNBOOK.md) | Linux 发布、回滚与可观测性 |
| [`../apps/medqc-web/scripts/linux_app_upgrade/README-DSH.md`](../apps/medqc-web/scripts/linux_app_upgrade/README-DSH.md) | Linux 精简应用升级包随包手册 |
| [`../apps/medqc-web/scripts/linux_offline/deploy/README-DSH.md`](../apps/medqc-web/scripts/linux_offline/deploy/README-DSH.md) | Linux 离线部署包随包手册 |
| [`../apps/medqc-web/docs/deployment/客户机交付包编译打包指南.md`](../apps/medqc-web/docs/deployment/客户机交付包编译打包指南.md) | Windows 客户交付、数据库备份与只读预检 |
| [`../apps/medqc-web/scripts/backend_patch/README-DSH.md`](../apps/medqc-web/scripts/backend_patch/README-DSH.md) | 东华病历详情后端补丁随包手册 |

## 业务契约与架构

| 文档路径 | 用途 |
| --- | --- |
| [`../apps/medqc-web/docs/frontpage-qc-v2/frontpage-qc-v2-design.md`](../apps/medqc-web/docs/frontpage-qc-v2/frontpage-qc-v2-design.md) | 病案首页质控 v2 的设计、数据模型与接口 |
| [`../apps/medqc-web/docs/frontpage-qc-v2/rule-catalog-review.md`](../apps/medqc-web/docs/frontpage-qc-v2/rule-catalog-review.md) | 首页质控规则编号、判定与评分口径 |
| [`../apps/medqc-web/docs/frontpage-qc-v2/m2-backend.md`](../apps/medqc-web/docs/frontpage-qc-v2/m2-backend.md) | 首页质控后端接口、数据表与执行方式 |
| [`../apps/medqc-web/docs/frontpage-qc-v2/2026-10-20-migration-head-review.md`](../apps/medqc-web/docs/frontpage-qc-v2/2026-10-20-migration-head-review.md) | 首页质控迁移链衔接与审查依据 |
| [`../apps/medqc-web/docs/frontpage-qc-v2/m1-engine-regression.md`](../apps/medqc-web/docs/frontpage-qc-v2/m1-engine-regression.md) | 首页质控引擎回归与校准依据 |
| [`../apps/medqc-web/docs/frontpage-qc-v2/phase0-false-positive-list.md`](../apps/medqc-web/docs/frontpage-qc-v2/phase0-false-positive-list.md) | 首页质控误报与规则设计依据 |
| [`../apps/medqc-web/docs/clinical-primary-four-business-20261116/IMPLEMENTATION.md`](../apps/medqc-web/docs/clinical-primary-four-business-20261116/IMPLEMENTATION.md) | 四类临床材料的版本、正文、时间与只读边界 |
| [`../apps/medqc-web/docs/clinical-record-lifecycle-business-20261116/IMPLEMENTATION-AND-REVIEW.md`](../apps/medqc-web/docs/clinical-record-lifecycle-business-20261116/IMPLEMENTATION-AND-REVIEW.md) | 逐记录生命周期只读适配与历史兼容 |
| [`../apps/medqc-web/backend/docs/ADR-data-source-pg-only.md`](../apps/medqc-web/backend/docs/ADR-data-source-pg-only.md) | 业务 PostgreSQL 和独立只读 CDM 的数据源决策 |
| [`../apps/medqc-web/docs/architecture/ADR-2026-03-26-modular-boundaries.md`](../apps/medqc-web/docs/architecture/ADR-2026-03-26-modular-boundaries.md) | 核心模块的职责与依赖边界 |
| [`../apps/medqc-web/docs/architecture/ADR-2026-08-19-offline-product-activation.md`](../apps/medqc-web/docs/architecture/ADR-2026-08-19-offline-product-activation.md) | 离线激活方式与密钥边界 |
| [`../apps/medqc-web/docs/architecture/ADR-LX0609-001-customer-hybrid-execution-package.md`](../apps/medqc-web/docs/architecture/ADR-LX0609-001-customer-hybrid-execution-package.md) | 客户专项规则执行包、证据准入与状态边界 |
| [`../apps/medqc-web/docs/architecture/adr-qc-dispatch-boundaries.md`](../apps/medqc-web/docs/architecture/adr-qc-dispatch-boundaries.md) | 质控调度、任务所有权与模型 Gateway 边界 |
| [`operations/qc-automatic-cdm-material.md`](operations/qc-automatic-cdm-material.md) | 单病历质控自动取材、冻结和重跑契约 |
| [`../apps/medqc-web/docs/0602/泸县0609质控点-业务标准基线-v1.md`](../apps/medqc-web/docs/0602/泸县0609质控点-业务标准基线-v1.md) | 泸县 0609 正式规则的现行业务口径 |

## 打包、校验与下载依赖

| 文档路径 | 用途 |
| --- | --- |
| [`../apps/medqc-web/docs/RULES_SYSTEM.md`](../apps/medqc-web/docs/RULES_SYSTEM.md) | 质控规则入口，供 `check-work-rules.*` 校验 |
| [`../apps/medqc-web/docs/AUGMENT_WORK_RULES.md`](../apps/medqc-web/docs/AUGMENT_WORK_RULES.md) | 项目规则入口，供 `check-work-rules.*` 校验 |
| [`../apps/medqc-web/docs/AUGMENT_QUICK_REFERENCE.md`](../apps/medqc-web/docs/AUGMENT_QUICK_REFERENCE.md) | 开发命令速查，供 `check-work-rules.*` 校验 |
| [`../apps/medqc-web/docs/plans/2026-11-03-strata-p9d-delivery.md`](../apps/medqc-web/docs/plans/2026-11-03-strata-p9d-delivery.md) | `package-p9d-isolated.py` 随包复制的 DSH 操作说明 |
| [`plans/2026-11-05-business-bundle-refresh-repair.md`](plans/2026-11-05-business-bundle-refresh-repair.md) | 刷新表修复候选包的合同及差异清单输入 |
| [`plans/2026-11-05-business-bundle-refresh-repair-test-report.md`](plans/2026-11-05-business-bundle-refresh-repair-test-report.md) | `build_refresh_repair_candidate.py` 打包的隔离验收证据 |
| [`plans/2026-11-05-business-bundle-refresh-repair-time-compat.md`](plans/2026-11-05-business-bundle-refresh-repair-time-compat.md) | `build_refresh_repair_candidate.py` 打包的文书时间兼容复审 |
| [`plans/2026-11-05-dual-source-local-acceptance.md`](plans/2026-11-05-dual-source-local-acceptance.md) | `build_refresh_repair_candidate.py` 打包的历史双源联验说明 |
| [`../apps/medqc-web/docs/0418/QC/2026-05-03-Sheet2客户验收包.md`](../apps/medqc-web/docs/0418/QC/2026-05-03-Sheet2客户验收包.md) | `build_sheet2_blocked_customer_gap_list.py` 读取和回写的验收包 |
| [`../apps/medqc-web/docs/0602/客户第一批质控点-语义规则覆盖矩阵.md`](../apps/medqc-web/docs/0602/客户第一批质控点-语义规则覆盖矩阵.md) | LX0609 目录校验和映射审计读取的覆盖矩阵 |
| [`../apps/medqc-web/docs/0602/泸县0609质控点-执行依赖矩阵.md`](../apps/medqc-web/docs/0602/泸县0609质控点-执行依赖矩阵.md) | LX0609 目录校验读取的执行依赖矩阵 |
| [`../apps/medqc-web/docs/0602/泸县0609质控点-客户待确认口径清单.md`](../apps/medqc-web/docs/0602/泸县0609质控点-客户待确认口径清单.md) | 客户反馈工作簿生成脚本读取的业务口径表 |
| [`../apps/medqc-web/docs/0602/泸县0609质控点评估报告.md`](../apps/medqc-web/docs/0602/泸县0609质控点评估报告.md) | 样本池 API 提供的 Markdown 下载文件 |
