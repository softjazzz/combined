# MedQC 项目工作规则

最后更新：2026-11-22。

- 仓库协作、最小验证和编码要求见[仓库指令](../../../AGENTS.md)与 [MedQC 应用指令](../AGENTS.md)。
- 工作台 UI 优先复用[浅色医疗设计规范](0418/UI/WorkstationV4-医疗浅色-DESIGN.md)的布局与组件。前端通过 FastAPI 调用业务接口。
- 业务读取和写入遵循 [PG 数据源决策](../backend/docs/ADR-data-source-pg-only.md)。数据库结构变更使用 [Alembic](../backend/docs/ALEMBIC_MIGRATION.md)。
- 质控链路修改遵循[质控规则系统文档](RULES_SYSTEM.md)，覆盖受影响的判定和来源边界。真实病历、连接配置、密钥及模型输出留在授权环境。
- 提交文本使用 UTF-8 无 BOM、LF 换行。完整入口见[活文档索引](../../../docs/INDEX.md)。
