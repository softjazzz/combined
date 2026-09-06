# LX0609-050 疑难病例讨论规则族职责迁移

## 范围

本次仅迁移 `LX0609-050` 的客户展示事实合同：原生执行器仍负责适用性、状态、
原因码和 `fact_refs`；Canonical Finalizer 负责白名单校验；公共 selected-document
projector 继续由 `fact_refs` 生成客户证据；聚合器仅装配。

## 行为冻结

冻结 Native → Binding → Finalizer → Aggregator 的 `status`、`reason_code`、客户事实、
`fact_refs`、客户证据坐标集合、客户文案和 Prompt。此次不改 Native 判定、Prompt、
Renderer、API、数据库或前端。

## 迁移边界

`difficult_case_result_mapping.py` 只接收并白名单化执行器已裁决的：入院时间、诊断不
明确记录时间和讨论记录数量；未知字段（包含旧直调携带的原文和文书 ID）被丢弃。
它不读取文书、不推断触发条件、不生成证据。聚合器不再出现 `LX0609-050` 专属事实
校验或证据回查。

## 验收

聚焦回归覆盖：无讨论的确定问题、局部诊断不明确的待确认、无触发的不适用、带讨论
的合规、资料源不可用；并验证错误的状态/事实组合转为 `technical_error`。客户证据
以坐标集合比较，数组顺序不作为优先级。
