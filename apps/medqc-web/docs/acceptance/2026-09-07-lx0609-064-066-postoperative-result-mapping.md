# LX0609-064/065/066 术后病程族结构迁移验收

## 范围与冻结基线

- 仅迁移 064（术后连续三日病程）、065（术后 72 小时上级医师查房）和 066（术后首次病程）的客户展示 facts 合同与证据职责。
- 迁移前，`luxian_0609_result_aggregator.py` 同时持有该族的规则号、facts 白名单、逐台脱敏、窗口校验和展示证据分支。
- 原生执行器、状态、原因码、Renderer、Prompt、API 与前端均未修改。

## 迁移后的所有权

- `postoperative_result_mapping.py` 是该族 facts 的唯一白名单与状态自洽校验者；它不读取材料、不选择 `fact_refs`、不生成文书 DTO。
- Canonical Finalizer 接收 mapping 的安全投影，合同非法、私有字段或 status/facts 冲突时清除客户事实与证据并降为 `technical_error`。
- 064/065/066 的证据只经过既有公共 `fact_refs` 投影；Aggregator 不再重选文书或解释术后事实。
- 无可展示 facts 的既有 `data_gap` / `not_applicable` 原生结果保持原状态；已提供但非法的 facts 不伪装为资料缺口。

## 冻结的可达形状

- 064：完整/缺失三日覆盖、手术结束时间缺失、窗口未成熟、评价时点缺失或冲突。
- 065：72 小时查房按时、逾期、手术结束时间缺失。
- 066：术后首次病程已覆盖、未覆盖。

逐台展示仍仅保留手术时间、名称、术者、所需/已覆盖日期和术者查房标记；原始 `document_id` 与文书内容不进入客户 facts。

## 守卫与验证

- `test_luxian_0609_postoperative_result_mapping.py` 冻结上述 facts、status 自洽、非法 facts 技术降级、公共 `fact_refs` 归属与 Aggregator 规则号归零。
- 既有 Aggregator 直调测试继续覆盖 LX0609-064 非法客户 facts 的 fail-closed/`ValueError` 兼容入口。
- Aggregator 文本规则号计数：`LX0609-064 = 0`、`LX0609-065 = 0`、`LX0609-066 = 0`。

## 聚焦命令

```powershell
pytest -q tests/unit/test_luxian_0609_postoperative_result_mapping.py tests/unit/test_luxian_0609_result_aggregator.py -k 'postoperative or 064 or 065 or 066'
pytest -q tests/unit/test_luxian_0609_native_extended_document_execution.py -k '064 or 065 or 066'
```
