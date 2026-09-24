# 原始 LX0609 阶段 C 启动前只读盘点

审计时点：2026-09-24；工作树提交基线 `e975e537c`。范围仅为原始 0609 规则的定义、计划、执行器协议和交付状态。未改生产代码、医学判据或模型配置；未访问客户病例和数据库。阶段 B 已做单个任务内 Settings 传递的局部修复，不等于跨部署的规则代码或配置版本冻结，也不满足整个 B 阶段退出条件。

## 当前责任链

| 属性 | 当前读取与校验路径 | 结论 |
| --- | --- | --- |
| 客户规则、文书、判据 | `luxian_0609_rules_v1.json` → `native_package.py:189–265` | 临床目录是输入；依赖清单从目录及规则族定义生成。 |
| `family_key`、`executor_key`、`execution_mode` | `customer_rule_package.py:25` 的规则族清单及各 native 执行器 ID 集 → `native_package.py:209–245`；`rule_contracts.py:324–329` 比对覆盖层；`executor_registry.py:672–680` 比对回调键；`engine.py:220–246` 检查批次归属 | JSON 的重复字段目前承担漂移哨兵职责，编译器会拒绝不一致。未复现双重权威导致的成功误派发；不应另建注册框架。 |
| 执行结果完整性 | `execution_contract.py:362–424` 检查所选规则恰好一次、无越界或错序；失败转技术 envelope；`engine.py:330` 调用 | 是执行层协议，和单规则客户允许状态不同。 |
| 规则状态 | `rule_contracts.py:28–36,190` 强制所有规则共用七种执行状态；原始 001–049 的客户允许结果见 `docs/0602/luxian_0609_formal_rule_catalog.csv` 的逐行 `allowed_result_statuses`；具体 `hit/not_hit` 等到运行时状态的映射见 `luxian_0609_result_schema.py:42–49` | 两者属于执行状态与客户目录状态两个层级。当前 `allowed_final_states` 是共享执行词表，不能单独证明逐规则客户允许状态。 |
| 模型调用预算 | 覆盖层 JSON 每规则声明；`rule_contracts.py:191–200` 另以两个四段式 ID 强制预算为 2，其余语义规则为 1；对应断言又在 `test_luxian_0609_rule_contracts.py:357–365` | 编译期重复约束，仓库内未发现运行时读取该字段做限流或计量。不能将字段误称为已执行的调用上限。 |

## 两层状态词表与原始 012 的职责表达

原始 012 当前 ID 为 `LX0609-06-01-05`。正式客户目录第 13 行允许 `hit; not_hit; data_quality_gap; not_applicable; needs_manual_review`；合同编译后的 `allowed_final_states` 是七项共享执行词表，含 `evaluation_unknown`、`technical_error`、`not_executed`。受控加载仅证实这两个**不同层级**的词表，不能由七项与五项不同推出真实交付缺陷。`native_exam_lab_execution.py:94–124` 的专用状态集合及 `evaluation_unknown → data_gap` 是现有实现证据；它包含原始 012 的业务判断，应继续由执行器拥有。`canonical_result_finalizer.py:834–878` 在事实合同损坏时转为 `technical_error`，这是技术失败处理，不能改写成某种临床状态以凑客户目录集合。本审计未发现 012 当前错误交付。

现有 `test_luxian_0609_rule_catalog.py:177–192` 已核对原始目录 CSV 与 JSON 的逐规则允许状态，并核对阶段暂停状态。后续阶段 C 若发现确切的客户状态违约，应先定位目录允许集合及发布校验的现有 owner；仅在既有编译或发布校验处补合法性检查，不重判状态、不把 012 的语义收敛搬到通用映射或 Finalizer，也不新增第二份逐规则状态目录。固定输入需覆盖 012 合规、不合规、资料缺口、语义未知和技术失败，证实状态、原因码及证据保持原样。扩展规则各找自身证明，不套用 001–049 的目录。

只读核对（在 `backend` 目录，令 `JWT_SECRET` 为隔离测试值、`DATABASE_URL=''`）：加载 `load_luxian_0609_rule_contracts()` 中的 `LX0609-06-01-05`，与 CSV 中 `LX0609-012` 的 `allowed_result_statuses` 并列打印，得到七项执行状态和五项客户目录状态。该输出只用于辨认层级，不能当作生产错误复现。

## 未证实为生产缺陷的重复属性

`family/executor/mode` 虽同时写在覆盖层和依赖清单，`rule_contracts.py:324–329` 会拒绝漂移；回调集合在 `executor_registry.py:672–680` 再检查，执行时 `engine.py:242–246` 拒绝错配。`LEGACY_NATIVE_EXECUTION_ORDER` 是现有模型调用顺序的显式合同，不能仅因其与目录顺序不同就删除。`max_llm_calls_per_rule` 的两个规则号硬编码是维护风险：改变声明需要同步构造器和测试；尚无“正式输入的实际调用被该字段误放行/误阻断”的复现，暂不列为第二个生产修复点，也不应贸然把规则预算当作规则族共享调用上限。

## 测试与后续门槛

初次运行 `test_luxian_0609_rule_contracts.py` 与 `test_luxian_0609_rule_extension_boundary.py`：前者 15/15 通过；后者 1/2 通过。失败的 `test_two_test_only_rule_contracts_cross_existing_extension_boundary` 使用旧三位测试 ID `LX0609-990/991`，在 `decision_model.py:279` 与 `execution_contract.py:249` 的现行四段式校验处拒绝；未到客户发布。随后仅把该测试文件的两个测试专用常量改为目录中不存在的 `LX0609-99-99-01/02`，原断言不变，扩展边界两项测试 2/2 通过。它们覆盖测试内注册的 Engine、决策绑定/归约、聚合与证据坐标，不经过任务 API、正式目录编译或发布存储；不能据此声称新增真实规则无需改公共层或已完成临床验收。

若后续找到确切的逐规则状态违约，再用同一输入与已保存模型响应比较状态、原因码、关键事实、证据坐标、调用次数/Token、执行器顺序和耗时。目前没有足以启动 012 生产改动的证据；这不缩小阶段 C 对其他重复属性的继续盘点。阶段 C 不触及新增 CT/抢救内容规则，也不以合成测试替代客户病例验收。
