# LX0609 读侧证据边界验收

## 变更范围

- `sichuan_workspace_batch_worker.py` 不再从 `medical_text` 截取会诊正文、构造 `CONSULT-*` 证据，正式 batch 仅透传执行器已生成的 `evidence_items`。
- `project_customer_safe_result_item` 不再把缺少 `customer_display_facts`/`criterion_results` 的 LX0609 `non_compliant` 改写为 `data_gap` 或 `historical_evidence_missing`；直接投影继续按 Canonical 合同 fail-closed。
- 历史 batch 详情中的单条裸旧 payload 仅在可识别的历史指纹下隔离为既有 `technical_error`/`canonical_result_envelope_invalid`，避免一条旧行导致整批详情 409/500；当前 Canonical 或非该指纹数据仍原样 fail-closed。

## TDD 与验证

1. 改动前聚焦测试确认：旧会诊正文 helper 仍存在；裸历史 `non_compliant` 不抛合同错误。
2. 改动后：`tests/unit/test_luxian_0609_read_side_projection_boundary.py` 5/5 通过，覆盖源码边界、直接投影 fail-closed、无历史改判、历史 batch 单条隔离及带版本结果继续 fail-closed。
3. `tests/unit/test_luxian_0609_canonical_result_delivery.py` 84/84 通过。
4. `tests/unit/test_qc_sichuan_batch_throughput.py`：63/64 通过；唯一失败为既存规则集快照预期未包含 `LX0609-076`、`LX0609-077`，与本次证据投影变更无关。

## 剩余风险

- 历史隔离以无 `rule_version`、无结构化解释且带 trace/metadata 为严格识别条件；未匹配的畸形或当前 Canonical 结果会继续 fail-closed，避免读侧掩盖执行链问题。
