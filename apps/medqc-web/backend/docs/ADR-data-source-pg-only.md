# ADR：业务 PostgreSQL 与临床只读 CDM

状态：已采纳。原决策日期为 2026-03-16。

## 业务数据

FastAPI 通过 PostgreSQL 读取和写入业务状态，包括任务、结果、复核与申诉。业务连接使用 `DATABASE_URL`，数据源配置使用 `DATA_SOURCE=pg`。schema 变更按 [Alembic 迁移说明](ALEMBIC_MIGRATION.md)执行。

## 临床材料

默认 `MEDQC_CLINICAL_SOURCE_MODE=fixed_donghua_cdm`。普通临床病历使用 `CDM_DATABASE_URL` 配置的独立只读 CDM，固定模式关闭旧同步入口。可信样本和 PDF 按各自登记来源取材，历史结果和重试按既有冻结材料与身份读取。实现入口见[临床来源策略](../app/services/clinical_source_policy.py)、[CDM 连接](../app/database/clinical_connection.py)和[自动取材契约](../../../../docs/operations/qc-automatic-cdm-material.md)。

历史兼容部署可显式使用 `legacy_compat`。旧 Mongo → ETL → PostgreSQL 说明保留在[归档标签索引](../../../../docs/INDEX.md)指向的历史版本。
