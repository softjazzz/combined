# LX0609-020/023 当前生产参数规则结果核销

## 核销范围

- 当前代码：本次会诊执行关系修复后的工作树。
- 输入：0910 客户样本库的同一组正式 Bundle、同一份会诊建议冻结结果和同一评价截止时间。
- 模型：`qwen3.8-flash`。
- 思考配置：开启，`thinking_budget=256`。
- 病例：C01、C04、C08、C11、C21、C23、C25、C26、C29。
- 规则：LX0609-020、LX0609-023。
- 重放：每个病例连续 3 轮，共 27 次病例执行、54 个规则结果。

## 本次修复

1. 明确 023 的痕迹分类边界：病程记录“遵会诊意见”并写出具体检查、治疗或监测动作时判 `specific_trace`；建议只落实一部分由覆盖度字段表达，不能把具体记录降为 `generic_trace`。
2. 同一病例中，某条较晚建议没有任何会诊后病程候选时，按该建议单独收敛为 `no_trace`，不再被同批较早建议的候选范围污染。
3. 模型已给出合法病程主引用时，错误放入辅助结构化字段的另一份病程引用会被丢弃，不再作废合法主证据。
4. 二阶段成功响应的顶层为数组或其它非对象形状时，登记为可恢复的结构错误并限定重试一次；两次仍非法才进入模型输出失败。
5. 提示词为每条建议提供最多 4 个词面相关病程候选作为优先核对提示。该提示只做召回，不直接生成执行事实，也不改变引用白名单和时序范围。

## 结果

| 病例 | 020 三轮 | 023 三轮 | 单病例模型调用次数 |
| --- | --- | --- | --- |
| C01 | `non_compliant` ×3 | `compliant` ×3 | 1 / 1 / 1 |
| C04 | `non_compliant` ×3 | `non_compliant` ×3 | 2 / 1 / 1 |
| C08 | `non_compliant` ×3 | `compliant` ×3 | 1 / 2 / 2 |
| C11 | `non_compliant` ×3 | `not_applicable` ×3 | 1 / 1 / 1 |
| C21 | `non_compliant` ×3 | `compliant` ×3 | 1 / 1 / 1 |
| C23 | `non_compliant` ×3 | `compliant` ×3 | 1 / 1 / 1 |
| C25 | `non_compliant` ×3 | `compliant` ×3 | 2 / 2 / 2 |
| C26 | `non_compliant` ×3 | `compliant` ×3 | 2 / 2 / 2 |
| C29 | `non_compliant` ×3 | `not_applicable` ×3 | 0 / 0 / 0 |

- 12 条目标台账记录：修复前生产参数重放为 30/36，修复后为 **36/36**。
- 九病例全部规则结果：修复前为 48/54，修复后为 **54/54**。
- 禁止交付状态：修复后 `uncertain=0`、`technical_error=0`。
- 模型调用：修复前 37 次，修复后 33 次。
- 回放记录累计耗时：修复前 585.063 秒，修复后 646.113 秒。调用数下降，但单次延迟波动使累计耗时增加 61.05 秒（约 10.4%）。

## 独立口径更正

C11/LX0609-023 的旧人工预期写成 `compliant`。复核同一冻结输入后确认：没有找到会诊建议的后续执行记录。按既定分工，020 负责判“建议是否有执行记录或未执行理由”，023 只评价已经找到的执行记录是否具体。因此该条正确结果为：

- 020：`non_compliant/requirement_violated`
- 023：`not_applicable/trigger_absent_complete`

这属于金标更正，不是通过修改引擎迎合旧答案。

## 验证

- `py -3.10 -m pytest -q backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py -p no:warnings`
- 结果：239 passed。
- 私有原始回放：
  - `.tmp/0910-full-audit/deepseek-consult-recheck-20260914/astra-b256-contract2-focus-private.json`
  - `.tmp/0910-full-audit/deepseek-consult-recheck-20260914/astra-b256-contract2-remaining-private.json`

## 核销边界与剩余风险

本次关闭的是 020/023 的规则级状态、原因码和禁止状态门禁。推荐级证据仍有模型波动：C04、C08、C21、C25、C26 的个别建议在三轮中出现候选引用数量、`no_trace/specific_trace` 或覆盖度差异；这些变化没有改变本次 54 个规则结果，但会影响明细证据的一致性。

C01 和 C29 的当前冻结建议数仍与较早人工拆分数量不同。本次只证明当前正式 Bundle 与当前冻结建议集合下的规则结果，不把它表述为建议原子化已完成验收。

后续若要求推荐级证据也逐项稳定，应单独以固定人工关系金标验收，并优先缩减会诊二阶段的结构化辅助候选；本次不借规则结果核销扩大生产架构改动。
