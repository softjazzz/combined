# 单一东华CDM实现计划

**Goal:** 新普通病例与任务固定读东华，业务状态写业务库；1026与历史结果保留原解释，不启用双普通来源共存。
**Architecture:** 复用clinical_sources/只读engine、可信材料登记与Canonical。新增部署级固定模式作为新版本默认，旧版本合同测试明确使用legacy_compat，不在界面提供切换。现有服务器配置模板明确fixed_donghua_cdm。
**Tech Stack:** FastAPI/SQLAlchemy/Vue、项目offline护栏、必要owned PG16、Vitest与现有样式。

BASE_SHA=60afbc49fbc92cad3b5234a2c7031d6261fcdf1e；新工作树business-single-donghua-cdm-20261106；063原样保留，064及旧脏树改动不纳入。

1. 先用单源unit反例复现普通GET默认旧源、新任务无上下文旧源、任意样本池强制旧源、旧任务自动恢复。
2. 最小策略owner固定普通来源；登记PDF/可信自建材料通过业务库登记判断；历史saved_snapshot语义不变；无登记的伪材料拒绝。
3. 固定模式禁止应用侧旧同步API和实际ETL入口；不触及东华同步服务或真实任务/配置。
4. 前端去除来源下拉与启用原源操作，普通请求固定CDM；历史任务和材料页不伪标来源。沿用现有工作台样式，不加页面。
5. 本机offline/前端测试；必要PG16证明普通CDM读、业务写、登记材料与历史结果保护；不再重跑双普通来源共存矩阵。无模型、无5432/现场访问。
6. 中文提交后从干净提交构建复审候选，包含前后端必要源码/资源、063及依赖说明，SHA/CHECKSUMS/解压自检。只交候选，不部署。
