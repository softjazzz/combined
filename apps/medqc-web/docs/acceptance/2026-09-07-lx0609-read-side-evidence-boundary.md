# LX0609 读侧证据边界验收

## 变更范围

- `sichuan_workspace_batch_worker.py` 不再从 `medical_text` 截取会诊正文、构造 `CONSULT-*` 证据，正式 batch 仅透传执行器已生成的 `evidence_items`。
- `project_customer_safe_result_item` 不再把缺少 `customer_display_facts`/`criterion_results` 的 LX0609 `non_compliant` 改写为 `data_gap` 或 `historical_evidence_missing`；直接投影继续按 Canonical 合同 fail-closed。
- 由 `_is_luxian_0609_export_job()` 识别的正式 LX0609 batch（包括 `filters.rule_set_key`、`rule_set_id`、summary 或 job 字段）中的非 v2 项，统一隔离为既有 `technical_error`/`canonical_result_envelope_invalid`，避免一条历史行导致整批详情 409/500；当前 v2 Canonical 仍原样 fail-closed。
- Canonical Store 的 `canonical_straight_through` Envelope 读取到 `lx0609-customer-result-v2` 后，DTO 只校验冻结的 `status/result_status/display_status/is_compliant` 与事实合同、裁剪敏感字段并重签证据引用；不再以 `is_compliant` 回退状态，也不再调用 Renderer 重算客户结论或建议。
- 非正式旧内部投影直调仍维持既有 fail-closed/兼容合同。

## TDD 与验证

1. 改动前聚焦测试确认：旧会诊正文 helper 仍存在；裸历史 `non_compliant` 不抛合同错误。
2. 改动后：`tests/unit/test_luxian_0609_read_side_projection_boundary.py` 7/7 通过，覆盖源码边界、直接投影 fail-closed、无历史改判、经 `rule_set_id` 识别的历史 batch 单条隔离、带版本结果继续 fail-closed、Canonical 文案直通和状态合同。
3. `tests/unit/test_luxian_0609_canonical_result_delivery.py` 84/84 通过。
4. `tests/unit/test_luxian_0609_result_review_service.py` 34/34 通过；测试夹具已固定为 v2 Canonical 合同。
5. `tests/unit/test_qc_sichuan_batch_throughput.py`：63/64 通过；唯一失败为既存规则集快照预期未包含 `LX0609-076`、`LX0609-077`，与本次证据投影变更无关。

## 剩余风险

- 当前 v2 Canonical 的状态或事实合同损坏会继续 fail-closed，避免读侧掩盖执行链问题；正式 LX0609 batch 的非 v2 项则按既有 `technical_error` 隔离，不回退为状态或客户结论重算。
