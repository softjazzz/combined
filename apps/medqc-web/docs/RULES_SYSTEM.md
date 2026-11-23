# MedQC 质控规则系统

最后更新：2026-11-22。

- 病案首页形式质控 v2 的规则编号、判定、评分及启停口径见[首页质控规则清单](frontpage-qc-v2/rule-catalog-review.md)。目录实现位于 [catalog.py](../backend/app/services/frontpage_qc_v2/catalog.py)。
- 泸县 0609 专项规则以[业务标准基线](0602/泸县0609质控点-业务标准基线-v1.md)为业务依据，按[混合执行包 ADR](architecture/ADR-LX0609-001-customer-hybrid-execution-package.md)解释证据准入与状态。
- 修改通用质控执行链时，依据[质控调度 ADR](architecture/adr-qc-dispatch-boundaries.md)确认任务、规则和模型 Gateway 的职责边界。

开发与运维文档见 [MedQC 活文档索引](../../../docs/INDEX.md)。
