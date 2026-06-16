# 泸县0609质控结果-证据链Schema

更新时间：2026-06-16

## 1. 文档目的

本文定义泸县0609质控结果的证据链结构。目标是让每条质控结论都可以被质控员、信息科和研发人员复核，而不是只展示“模型认为有问题”。

本 schema 先作为产品和后端结果结构的目标约束，后续逐步对齐 API、数据库、前端结果抽屉和导出报告。

## 2. 顶层结构

```json
{
  "qc_point_id": "LX0609-003",
  "rule_id": "LX0609-003",
  "rule_name": "手术记录：手术后24小时内是否完成",
  "rule_set_key": "luxian_0609_qc_v1",
  "rule_set_version": "2026-06-09",
  "rule_version": "v1",
  "executor_type": "program | llm | cross_document | cross_table | hybrid",
  "result_status": "non_compliant | compliant | not_applicable | data_gap | uncertain | not_executed | technical_error",
  "confidence": 0.93,
  "trigger": {},
  "dependencies": {},
  "evidence": [],
  "decision": {},
  "review": {},
  "audit": {}
}
```

## 3. 必填字段

| 字段               | 类型   | 必填 | 说明                                   |
| ------------------ | ------ | ---- | -------------------------------------- |
| `qc_point_id`      | string | 是   | 客户质控点 ID，例如 `LX0609-003`。     |
| `rule_name`        | string | 是   | 展示给用户的规则名称。                 |
| `rule_set_key`     | string | 是   | 规则集 key，例如 `luxian_0609_qc_v1`。 |
| `rule_set_version` | string | 是   | 规则集版本。                           |
| `rule_version`     | string | 是   | 单条规则版本。                         |
| `executor_type`    | enum   | 是   | 执行器类型。                           |
| `result_status`    | enum   | 是   | 结果状态。                             |
| `confidence`       | number | 否   | 置信度，程序化规则可为 1。             |
| `trigger`          | object | 是   | 触发事实。                             |
| `dependencies`     | object | 是   | 数据依赖和缺口。                       |
| `evidence`         | array  | 是   | 来源证据列表。                         |
| `decision`         | object | 是   | 判断过程和结论。                       |
| `review`           | object | 是   | 人工复核状态。                         |
| `audit`            | object | 是   | 执行审计信息。                         |

## 4. Trigger Gate 结构

```json
{
  "applicable": true,
  "trigger_facts": [
    {
      "fact_type": "surgery_event",
      "fact_label": "存在手术记录",
      "fact_value": "腹腔镜胆囊切除术",
      "source_table": "surgery_record",
      "source_document_type": "手术记录",
      "source_document_id": "SR-001",
      "record_time": "2026-06-01 10:00:00"
    }
  ],
  "not_applicable_reason": null,
  "gate_version": "trigger_gate_v1"
}
```

要求：

- 无触发事件时返回 `not_applicable`，不进入 LLM 裁决。
- 缺少关键触发数据时返回 `data_gap` 或 `not_executed`。
- 触发事实必须给出来源表、文书类型、记录时间或结构化字段。

## 5. 数据依赖结构

```json
{
  "required_sources": [
    {
      "source_type": "document",
      "source_name": "手术记录",
      "table_name": "surgery_record",
      "required_fields": ["operation_end_time", "record_time", "record_content"],
      "availability": "available"
    }
  ],
  "missing_sources": [],
  "data_gap_reason": null,
  "source_coverage_level": "full | partial | missing"
}
```

要求：

- `data_gap` 结果必须列出 `missing_sources` 和 `data_gap_reason`。
- 缺医嘱、费用、检查、检验、输血、麻醉或手术相关表时，不得返回 `compliant`。

## 6. 来源证据结构

```json
{
  "evidence_id": "E-001",
  "source_table": "surgery_record",
  "source_document_type": "手术记录",
  "source_document_name": "2026-06-01 手术记录",
  "source_document_id": "SR-001",
  "record_time": "2026-06-02 11:30:00",
  "field_path": "record_content",
  "quote": "手术记录于2026-06-02 11:30完成。",
  "normalized_value": "2026-06-02 11:30:00",
  "evidence_role": "actual_completion_time"
}
```

要求：

- 命中类结果至少有一条可定位证据。
- 跨文书规则至少有两个证据对象，分别指向参与比较的文书。
- 跨表联查规则必须包含结构化表字段证据。

## 7. 判断过程结构

```json
{
  "decision_summary": "手术记录完成时间距手术结束超过24小时。",
  "threshold": "24小时",
  "expected_value": "2026-06-02 10:00:00前完成",
  "actual_value": "2026-06-02 11:30:00完成",
  "delta": "25.5小时",
  "is_violation": true,
  "suggestion": "请核查手术记录完成时间并补充说明超时原因。"
}
```

时限规则必须包含：

- 触发时间。
- 截止时间。
- 实际完成时间。
- 计算间隔。
- 结论。

跨文书规则必须包含：

- 比较对象。
- 冲突字段或缺失字段。
- 参与判断的文书名称和记录时间。
- 原文片段或结构化值。

LLM 语义规则必须包含：

- 被判定文本片段。
- 语义判断理由。
- 置信度。
- 低置信度时进入 `uncertain` 或人工复核。

## 8. 人工复核结构

```json
{
  "review_status": "pending | accepted | rejected | corrected",
  "reviewer": null,
  "reviewed_at": null,
  "review_comment": null,
  "final_status": null
}
```

要求：

- 所有 `non_compliant` 默认 `review_status=pending`。
- `LLM-only` 严重缺陷不得直接作为最终结论。
- 人工修改结论必须保留原始系统结论和修改理由。

## 9. 审计结构

```json
{
  "job_id": "batch-job-id",
  "visit_id": "2313364",
  "patient_id": "P001",
  "model_name": "qwen3.5-35b-a3b",
  "prompt_version": "luxian_0609_v1",
  "executed_at": "2026-06-16 10:00:00",
  "elapsed_ms": 1234,
  "technical_status": "success",
  "error_message": null
}
```

要求：

- 前端不展示 `prompt`、`raw_response`、完整病历全文。
- 后端日志可保留必要审计信息，但需要权限控制。
- `technical_error` 必须记录错误类型和可重试状态。

## 10. 前端展示要求

结果卡片应至少展示：

- 规则名称和规则版本。
- 结果状态。
- 触发事实。
- 关键证据。
- 判断过程。
- 数据缺口。
- 人工复核状态。

不允许只展示：

- “符合规则要求”。
- “存在问题”。
- “AI 建议复核”。

## 11. 与现有状态的映射

| 现有或历史状态        | 新状态                         | 说明                     |
| --------------------- | ------------------------------ | ------------------------ |
| `hit`                 | `non_compliant`                | 确认存在缺陷。           |
| `not_hit`             | `compliant`                    | 确认符合规则。           |
| `data_quality_gap`    | `data_gap`                     | 数据不足。               |
| `needs_manual_review` | `uncertain`                    | 无法稳定判断。           |
| `rejected_by_gate`    | `not_applicable` 或 `data_gap` | 需按拒绝原因区分。       |
| `unsupported`         | `not_executed`                 | 规则未实现或工具未接入。 |
| provider/parse error  | `technical_error`              | 技术异常。               |

## 12. 后续落地步骤

1. 后端 DTO 增加 evidence schema 兼容字段。
2. 泸县0609主干结果先填充 `trigger/dependencies/evidence/decision`。
3. 客户样本验证结果抽屉按 schema 展示。
4. 导出报告使用同一 schema。
5. 真实样本 golden set 使用同一字段做人工复核。
