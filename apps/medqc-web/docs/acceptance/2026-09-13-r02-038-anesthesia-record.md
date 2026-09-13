# R02 LX0609-038 麻醉记录单核查验收

## 权威口径

业务标准基线 `docs/0602/泸县0609质控点-业务标准基线-v1.md:119` 的原文为：`非局麻且实施麻醉时，应存在麻醉记录单。`

正式目录 `docs/0602/luxian_0609_formal_rule_catalog.csv` 的第 038 行确认客户原文为“无麻醉记录单（局麻除外）”；该行允许 `not_applicable`。规则主数据 `backend/app/data/luxian_0609_rule_master_v1.json` 将 038 标为 active，来源文书为麻醉记录单。

本条按“实施麻醉 + 麻醉方式为非局麻”触发，局部麻醉排除；规则没有传统手术分类的前提。治疗性操作本身不构成排除条件。正式目录列出的允许状态为 `hit`、`not_hit`、`data_quality_gap`、`not_applicable`、`needs_manual_review`；当前 typed 合同使用 `compliant`、`not_applicable` 等 canonical 状态，本次未新增状态或修改合同。

## 五例独立预期与当前结果

| 病例 | Evidence/目录交叉核对事实 | 独立预期 | 当前 typed / 正式结果 | 当前是否正确 |
| --- | --- | --- | --- | --- |
| C05 | 80.5200、04.4900x042 为目录确认的传统手术；两条手术主表均为局部浸润麻醉；无麻醉记录 | `not_applicable`（局麻排除） | `not_applicable / eligibility_not_met`；两轮正式结果一致 | 是 |
| C10 | 03.5304 为手术；麻醉记录存在，固定标签解析为静吸复合全麻 | `compliant / requirement_satisfied` | `compliant / requirement_satisfied`；两轮正式结果一致 | 是 |
| C17 | 34.0401 为治疗性操作；手术主表为局部浸润麻醉；无麻醉记录 | `not_applicable`（局麻排除，未出现非局麻实施） | `not_applicable / performed_event_absent`；两轮正式结果一致 | 是 |
| C19 | 04.8101 为治疗性操作；麻醉方式为“-”；无麻醉记录 | `not_applicable`（没有非局麻实施证据） | `not_applicable / performed_event_absent`；两轮正式结果一致 | 是 |
| C30 | 43.4105 为治疗性操作；麻醉记录存在，固定标签解析为静脉麻醉 | `compliant / requirement_satisfied` | `compliant / requirement_satisfied`；两轮正式结果一致 | 是 |

C10、C30 的客户展示事实均为 `verification_kind=anesthesia_record_present`、`performed_anesthesia_confirmed=true`、`checked_sources=[anesthesia_record]`。C05、C17、C19 没有客户展示事实；其不适用结论由局麻排除或缺少非局麻实施事实形成。

## 证据绑定与当前代码时点

本次验收基于 `6906b095f` 后的 R02 工作树。`backend/app/services/luxian_0609/native_surgery_document_execution.py` 的 `_typed_anesthesia_trigger` 先读取受控结构化方式；缺少结构化值时，读取麻醉记录正文唯一的固定 `麻醉方式：值` 标签，冲突或缺失仍保守处理。C10 的“静吸复合全麻”和 C30 的“静脉麻醉”均为唯一标签值，因此两例均进入非局麻且实施麻醉分支，并分别绑定各自麻醉记录 Evidence。

五例正式结果的公开 Evidence refs 为：C05 `src_50d10795f36a1e8534b23a7e`、`src_39287a2db5f8fe717f0a0ebd`；C10 `src_bdd3f004847f1fe41728e3f1`；C17 `src_c035c58e93bc5ac87d2c19bb`；C19 `src_e2665a1cf48f6c3c884eafa3`；C30 `src_c638f1113dbffc1aebc255b6`。含患者事实、typed fact refs 和原始交叉核对内容保存在私有产物 `.tmp/0910-full-audit/r02-038-audit-private.json`，不复制到本文件。

## 双轮聚焦验收

- 首轮正式任务：`b66dedba-5998-4af7-962d-9038ba425c9d`，产物 `.tmp/0910-full-audit/r02-remaining-after-run1-private.json`。
- 二轮正式任务：`3bddcfe2-d69d-4c7c-a22c-ba5d2b0fe160`，产物 `.tmp/0910-full-audit/r02-remaining-after-run2-private.json`。
- 两轮均为 30 个病例、30/30 成功、0 失败；038 的 30 例以及台账中的五例结果一致，未出现 `uncertain` 或 `technical_error`。
- 两轮及本次 typed 回放均为 0 次 LLM 调用、0 Token、0 次重试。
- 已通过聚焦测试：`test_luxian_0609_rule_038_source_contract.py`（1 passed）、手术目录/规则目录聚焦测试（14 passed）、`test_luxian_0609_native_surgery_document_execution.py`（111 passed）。
- C10/C30 的麻醉方式固定标签解析属于已存在的 037 修复链；本次只更正 C30 的独立预期并写入验收/台账，没有修改代码或提交。
