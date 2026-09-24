# 原始 LX0609 阶段 C 启动前只读盘点

审计时点：2026-09-24；工作树提交基线 `e975e537c`。范围仅为原始 0609 规则的定义、计划、执行器协议和交付状态。未改生产代码、医学判据或模型配置；未访问客户病例和数据库。阶段 B 已做单个任务内 Settings 传递的局部修复，不等于跨部署的规则代码或配置版本冻结，也不满足整个 B 阶段退出条件。

## 当前责任链

| 属性 | 当前读取与校验路径 | 结论 |
| --- | --- | --- |
| 客户规则、文书、判据 | `luxian_0609_rules_v1.json` → `native_package.py:189–265` | 临床目录是输入；依赖清单从目录及规则族定义生成。 |
| `family_key`、`executor_key`、`execution_mode` | `customer_rule_package.py:25` 的规则族清单及各 native 执行器 ID 集 → `native_package.py:209–245`；`rule_contracts.py:324–329` 比对覆盖层；`executor_registry.py:672–680` 比对回调键；`engine.py:220–246` 检查批次归属 | JSON 的重复字段目前承担漂移哨兵职责，编译器会拒绝不一致。未复现双重权威导致的成功误派发；不应另建注册框架。 |
| 执行结果完整性 | `execution_contract.py:362–424` 检查所选规则恰好一次、无越界或错序；失败转技术 envelope；`engine.py:330` 调用 | 是执行层协议，和单规则客户允许状态不同。 |
| 规则状态 | `rule_contracts.py:28–36,190` 强制所有规则共用七种执行状态；原始 001–049 的客户允许结果见 `docs/0602/luxian_0609_formal_rule_catalog.csv` 的逐行 `allowed_result_statuses`；具体 `hit/not_hit` 等到运行时状态的映射见 `luxian_0609_result_schema.py` | 当前 `allowed_final_states` 实际是执行状态全集，不是逐规则交付允许集合。不能用它证明客户状态合法。 |
| 模型调用预算 | 覆盖层 JSON 每规则声明；`rule_contracts.py:191–200` 另以两个四段式 ID 强制预算为 2，其余语义规则为 1；对应断言又在 `test_luxian_0609_rule_contracts.py:357–365` | 编译期重复约束，仓库内未发现运行时读取该字段做限流或计量。不能将字段误称为已执行的调用上限。 |

## 已发生的合同错位：原始 012

原始 012 当前 ID 为 `LX0609-06-01-05`。正式客户目录第 13 行允许 `hit; not_hit; data_quality_gap; not_applicable; needs_manual_review`；合同编译后的 `allowed_final_states` 却是七项共享执行词表，含 `evaluation_unknown`、`technical_error`、`not_executed`。受控加载目录与合同可重现这一差异，未读取病历。`native_exam_lab_execution.py:94–124` 明确因此在执行器内设置 012 专用四状态集合，并把 `evaluation_unknown` 收敛为 `data_gap`。这证明单规则客户状态职责曾不得不下沉到执行器；但已有收敛与测试，**本审计未发现 012 当前会把该状态错误交付客户**。`technical_error` 是执行失败语义，也不能直接按目录的临床结果词表判断。

阶段 C 可选的第一个小闭环：只针对原始 012，在既有合同编译器中明确区分“执行状态全集”与“客户允许结果集合”，以正式目录逐行状态为输入，在既有状态映射边界做交叉校验；待固定输入的 012 合规、不合规、资料缺口、语义未知、技术失败结果及原因码完全等价后，再考虑移除执行器内的专用允许集合。不要先删除其收敛行为，也不要把所有规则一齐重写。对未在 001–049 目录中的扩展规则，必须先找到各自扩展证明，不能套用该目录。

只读复现（在 `backend` 目录，令 `JWT_SECRET` 为隔离测试值、`DATABASE_URL=''`）：加载 `load_luxian_0609_rule_contracts()` 中的 `LX0609-06-01-05`，与 CSV 中 `LX0609-012` 的 `allowed_result_statuses` 并列打印；得到上述七状态与五状态差异。该比较只证明合同含义错位，不等于临床结果回放。

## 未证实为生产缺陷的重复属性

`family/executor/mode` 虽同时写在覆盖层和依赖清单，`rule_contracts.py:324–329` 会拒绝漂移；回调集合在 `executor_registry.py:672–680` 再检查，执行时 `engine.py:242–246` 拒绝错配。`LEGACY_NATIVE_EXECUTION_ORDER` 是现有模型调用顺序的显式合同，不能仅因其与目录顺序不同就删除。`max_llm_calls_per_rule` 的两个规则号硬编码是维护风险：改变声明需要同步构造器和测试；尚无“正式输入的实际调用被该字段误放行/误阻断”的复现，暂不列为第二个生产修复点，也不应贸然把规则预算当作规则族共享调用上限。

## 测试与后续门槛

运行 `test_luxian_0609_rule_contracts.py` 与 `test_luxian_0609_rule_extension_boundary.py`：前者 15/15 通过；后者 1/2 通过。失败的 `test_two_test_only_rule_contracts_cross_existing_extension_boundary` 使用旧三位测试 ID `LX0609-990/991`，在 `decision_model.py:279` 与 `execution_contract.py:249` 的现行四段式校验处拒绝；未到客户发布。它是编号迁移后的旧测试资料问题，不能据此推断真实四段式规则失败，亦不属于本审计授权的生产改动。应由编号迁移维护任务更新该测试资料，然后再次跑其执行器边界断言。

若进入 012 小闭环，固定同一输入与已保存模型响应，逐项比较状态、原因码、关键事实、证据坐标、调用次数/Token、执行器顺序和耗时。先保持旧执行器收敛作为基线，验证新编译校验再移除重复路径。阶段 C 不触及新增 CT/抢救内容规则，也不以合成测试替代客户病例验收。
