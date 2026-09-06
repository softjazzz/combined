# LX0609 069/071/072/073/074 连续性与会诊族精确证据坐标验收

日期：2026-09-07

## 范围

本闭环只收紧 native extended executor 的 `RuleDecision.fact_refs`：
`LX0609-069`、`LX0609-071`、`LX0609-072`、`LX0609-073`、`LX0609-074`。状态、
原因码、展示 facts、既有判定器口径及 Aggregator、Finalizer、Renderer、API、前端均不修改。

新增的完整职责位于 `continuity_evidence_selection.py`：按各规则执行器已经交付的冻结 facts
回定位已消费行，并以显式 `(source_key, row)` 唯一映射为同一 Evidence Snapshot 的逐文书 ref。
它不重新判定、不复制规则状态机、不生成客户 DTO；无法唯一定位时显式关闭为
`technical_error/snapshot_mismatch`，不退回整类客户文书。

## 证据坐标合同

| 规则 | 精确客户证据                              | 无逐文书消费时的最小锚点                |
| ---- | ----------------------------------------- | --------------------------------------- |
| 069  | 实际唯一配对的会诊申请与会诊记录          | `consultation_record` snapshot 判定锚点 |
| 071  | 实际匹配的交班、接班记录                  | 选中的变更来源 snapshot 判定锚点        |
| 072  | 唯一转科医嘱和实际匹配的转入、转出文书    | `inpat_nondrug_order` snapshot 判定锚点 |
| 073  | 唯一转科医嘱和实际匹配的转入、转出文书    | `inpat_nondrug_order` snapshot 判定锚点 |
| 074  | 发生变化的诊断行和实际匹配的理由/依据病程 | `diagnosis` snapshot 判定锚点           |

069 仍由既有会诊判定器决定申请时间资料是否可用；`record_time` 仅用于回定位已经被判定器
选中的配对文书，绝不冒充机构申请时间。072 的 `evaluation_context.horizon` 仅参与 24 小时
窗口成熟度判定，绝不进入 `fact_refs`。071 保留 `source_document_refs` 兼容字段，以免影响
旧 Aggregator 的 legacy 投影；公共证据已独立由精确 `fact_refs` 给出，后续结构迁移应删除
该私有兼容字段。

## 多事件与保守失败

071 按每次变更的交/接班时间分别收集已匹配记录；074 多次诊断变更仅在每次变更均唯一匹配
不同病程时绑定所有对应行。会诊或转科的多候选、诊断关联歧义仍维持既有 `data_gap` 语义。
已消费行若不能唯一坐标化为同 snapshot 的逐文书 ref，Binding 归约为 `technical_error`，不
将整类日常病程、医嘱或私有来源引用投影给客户。

## 验证

```text
py -3.10 -m pytest -q tests/unit/test_luxian_0609_native_extended_document_execution.py -k "069 or 071 or 072 or 073 or 074 or continuity_invalid"
54 passed

py -3.10 -m ruff check app/services/luxian_0609/native_extended_document_execution.py tests/unit/test_luxian_0609_native_extended_document_execution.py
All checks passed

git diff --check
exit 0
```

新增断言覆盖：069 配对文书排除无关病程；071 多变更事件的实际交/接班证据；072/073 唯一
转科医嘱、多余转科文书及 horizon 排除；074 仅变化诊断与匹配病程；以及合法格式但不属于
snapshot 的精确引用、以及已有消费文书却无法完成精确绑定，均不能伪装为业务状态。
