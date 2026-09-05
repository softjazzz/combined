# 会诊规则族 020–023 架构收口验收（B2）

日期：2026-09-05

## 结论

B2 结构闭环通过，可以独立提交。020–023 的状态与关键事实仍由正式
`consultation_quality` episode executor 决定；聚合器中的规则专属事实校验、内部
文书 ID 推断、失败证据回退和状态二次改写已经删除。B3 的三业务入口和真实模型性能
仍未完成，因此本报告不宣称整个会诊族架构任务已经关闭。

## 实际边界

- 执行器：决定 status、reason、safe facts，并选择本次判定实际使用的内部文书引用。
- `consultation_decision_evidence.py`：将上述引用严格、全量、唯一地绑定到同一
  Evidence Session 的逐文书材料引用；任一决定性引用无法绑定时，仅对应规则
  `technical_error/snapshot_mismatch`，不交付部分证据。
- Binding：验证 snapshot、允许来源和 `fact_refs`；仅 020–023 的
  `not_applicable + trigger_absent_complete` 可为空，因为完整来源中没有可定位的会诊
  文书。`eligibility_not_met` 等其他不适用原因仍必须有证据。
- 公共证据投影：把已绑定的 `fact_refs` 转成文书 ID、字段和时间；没有新增会诊专属
  `customer_evidence` 拼装器。
- `consultation_customer_projection.py`：只校验并剥离客户 facts 中的内部 ID；逐建议
  安全引用复用已有公共 HMAC 投影，不选择文书、不改状态。
- Finalizer：客户事实合同非法时只隔离该规则为 `technical_error`，并移除由非法事实
  派生的临床结论、证据和资料缺口字段。
- Aggregator：只接收已验证 facts、投影后的 evidence 并装配结果。

## 聚合器归零证据

源码搜索 `LX0609-020` 至 `LX0609-023` 在
`luxian_0609_result_aggregator.py` 中为 0。`LX0609-069` 的
`consultation_timeliness_check` 分支仍保留，本次没有迁移或改写 069。

正式生产代码仍未导入或调用历史
`native_consultation_execution.execute_luxian_0609_native_consultation_rules()`；其测试只
作为遗留合同回归，不作为 B2/B3 主链验收。

## 证据安全反例

- 多于 8 次会诊且第 9 次为 023 缺陷：截断前强制保留末次缺陷会诊和执行文书，最终
  `RuleDecision.fact_refs` 与公共客户证据均包含两份文书。
- `RuleDecision` 既有合同会对 `fact_refs` 稳定排序，因此不承诺缺陷文书在最终列表首位；
  本次没有修改全局顺序合同，也没有新增优先级字段。
- partial、材料缺失、跨来源同名引用冲突：禁止静默丢弃；执行级反例证明只将依赖坏
  引用的 023 收敛为技术错误，020 的既有结论和证据不受污染。
- 完整来源没有会诊事件：四条规则可正确为 `not_applicable/trigger_absent_complete`，
  不再用来源级摘要或任意文书冒充证据。

## 文件规模与收益

| 文件                                       | B2 前 | B2 后 | 变化与职责                                                       |
| ------------------------------------------ | ----: | ----: | ---------------------------------------------------------------- |
| `luxian_0609_result_aggregator.py`         |  6308 |  5613 | -695；移除 020–023 的五类业务所有权                              |
| `native_consultation_episode_execution.py` |  3553 |  3822 | +269；在既有判定点接入材料绑定、逐规则失败隔离和 safe facts 交付 |
| `consultation_customer_projection.py`      |     0 |   442 | 新深模块；完整客户事实合同                                       |
| `consultation_decision_evidence.py`        |     0 |   291 | 新深模块；完整逐文书绑定与决定性证据选择                         |
| `canonical_result_finalizer.py`            |   328 |   414 | +86；通用执行器事实合同接收与单规则 fail-closed                  |
| `customer_evidence_enrichment.py`          |   269 |   331 | +62；公共已选分组引用的安全投影                                  |
| `decision_binding.py`                      |   277 |   291 | +14；会诊无触发事件的精确空引用合同                              |

相关生产代码净增 469 行。父执行器净增超过 200 行的原因是三个既有返回路径都必须在
判定现场交付 typed decisions 并隔离单规则材料失败；纯 facts 校验和证据绑定已经分别
迁入两个完整深模块，再继续抽取只会形成依赖执行器私有 `_result/_decision` 的转发壳。
因此本次保留 269 行集成代码，并以全量行为回归作为门禁，不用压缩语句规避行数规则。

公开入口、Canonical 合同、API DTO、数据库 schema 和前端均未变化。Renderer 仍保留
020–023 的客户文案条件分支，但只读取已确定 safe facts 组织文字，不改状态、原因、
事实或证据；它不是本次“聚合器业务所有权归零”的阻塞项，后续也不应把本报告解释为
Renderer 已完全声明式。

## 测试结果

- 会诊 projection、material binding、episode executor、Binding、Finalizer、公共证据
  投影、聚合器：641 passed。
- 069 时效与扩展文书反向隔离：241 passed。
- `test_luxian_0609_mainline_services.py`：162 passed。
- 全部 `test_luxian_0609_*.py`：4311 passed，38 个既有 warning，35.47 秒；执行时通过
  `PGOPTIONS=-c default_transaction_read_only=on` 强制 PostgreSQL 只读。
- 变更生产文件及新增测试 Ruff：通过。
- B2 目标文件 `git diff --check`：通过。

Stub 冻结测试确认 Prompt 内容、调用次数和 Token 未因材料引用绑定发生变化；真实材料
引用不会进入 Prompt。

## 尚未完成（B3）

1. 单病历单规则正式 batch job、病历池批量、客户样本验证叶子任务的实际任务 trace 与
   保存后结果一致性。
2. 真实模型基线/候选交替预热后各 10 次的输入 Token、调用数和中位耗时比较。
3. 三入口 trace 需要证明实际 `executor_key=consultation_quality`，且没有 legacy/fallback。

这些项目完成前，不能关闭当前 Goal，也不能开始下一规则族迁移或批量增加新规则。
