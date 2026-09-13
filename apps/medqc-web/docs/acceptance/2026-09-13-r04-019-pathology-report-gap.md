# LX0609-019 病理报告结果缺口修复验收

## 问题证据

LX0609-019 的权威业务基线要求同时核对手术记录中的病理取材情况和病程记录中的病理结果，并先建立病理报告与病程记录的同次事件关联。缺少可用于关联和核对的病理最终结果时，不能交付确定性合规或不合规。

旧执行器只为 LX0609-013 校验病理报告的最终诊断和报告时间。typed 019 会在报告结果正文缺失时继续检查取材记录或调用模型，导致旧结果中 C01、C02、C07 为 `compliant`，C04、C29、C30 为 `non_compliant`。这些结论都没有完整的病理结果事实支持。

排查开始时曾假设只有 C04、C29、C30 受影响。首轮正式 API 回归显示有 6 个病例进入报告缺口分支；随后直接统计本地客户原始 CDM 表，确认 C01、C02、C04、C07、C29、C30 的病理报告均有报告时间，但 `diagnosis` 和 `record_content` 全部为空。这说明影响范围假设不完整，且缺口来自客户原始 CDM 数据，不是 Bundle 投影丢字段。原假设已在任务计划中留痕更正。

## 最小修复

- typed 019 复用 013 已有的病理报告完整性门禁。没有同一份报告的最终诊断和有效报告时间时，直接产出 `data_gap/required_field_missing`，不再进入取材确定性结论或 LLM 分支。
- 复用已有 `pathology_report_field_gap` 客户事实、病理报告文书引用和缺失字段汇总。
- 事实白名单、Renderer 和 Finalizer 只接受并展示执行器已经裁决的 019 报告缺口，不重新解释业务状态。
- legacy 019 保持原行为；本轮正式交付链路使用 typed Bundle/Evidence 会话。

## 保护集合与时点

- 对照产物：`.tmp/0910-full-audit/typed-pathology-019/status.json`，对应 2026-09-10 的 019 正式 30 例任务。
- 旧确定结论 C01、C02、C04、C07、C29、C30 使用了已被当前权威双条件合同推翻的“取材单条件”口径，不作为本次零回退保护项；本次明确更正为资料不足。
- 保护集合为其余 24 个旧 `not_applicable/trigger_absent_complete` 结果。两次新任务中这 24 个结果的状态、原因码和客户展示事实均保持不变。

## 测试与真实回归

- 病理执行器与报告缺口测试：121 项通过。
- 肿瘤病理事实映射、Canonical Finalizer 和 Customer Renderer：495 项通过。
- Ruff 与 `git diff --check`：通过。
- 第一次正式 30 例任务：`5024ee68-f2ef-47dc-9726-275f4d596c0b`。
- 第二次正式 30 例任务：`25234212-2a2d-4950-937a-018ce0ff5b58`。
- 两次均为 6 个 `data_gap/required_field_missing`、24 个 `not_applicable/trigger_absent_complete`，30 个病例全部成功。
- 两次任务的状态、原因码、客户展示事实和证据来源类型完全一致；均为 0 次 LLM 调用、0 次重试、0 Token。
- 六个资料不足结果均列出“病理最终诊断”缺失，并定位到具体病理报告；未出现 `uncertain` 或 `technical_error`。
- 私有产物：`.tmp/0910-full-audit/r04-019-final-run1-private.json`、`.tmp/0910-full-audit/r04-019-final-run2-private.json`、`.tmp/0910-full-audit/r04-019-final-comparison-private.json`。

## 剩余风险

病理报告结果完整的病例仍需单独验证“病理报告与病程记录同次事件关联”是否完整实现。本任务只关闭已真实发生的报告结果缺失误判，不扩展关联平台或重写 019 全链路。
