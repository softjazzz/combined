# MedQC 跨会话接续

当前开发、架构与部署说明统一见 [MedQC 活文档索引](../../../../docs/INDEX.md)。

- 普通临床来源与隔离边界见 [PG 与只读 CDM 决策](../../backend/docs/ADR-data-source-pg-only.md)。
- 四类材料和逐记录生命周期的兼容及启用条件见[四类临床材料合同](../clinical-primary-four-business-20261116/IMPLEMENTATION.md)与[逐记录生命周期合同](../clinical-record-lifecycle-business-20261116/IMPLEMENTATION-AND-REVIEW.md)。
- 首页质控的现行口径见[首页规则目录](../frontpage-qc-v2/rule-catalog-review.md)，泸县专项见[业务标准基线](../0602/泸县0609质控点-业务标准基线-v1.md)。
- 架构边界治理（权限归一、表结构探测去重、取材/冻结与规则执行拆分）台账见[架构治理清单](architecture-governance-202611/IMPLEMENTATION.md)。

完整历史待办和专题接续卡可用 `git show archive/docs-pre-cleanup-202611:apps/medqc-web/docs/plans/PROJECT_ROLLING_TODO.md` 查阅。
