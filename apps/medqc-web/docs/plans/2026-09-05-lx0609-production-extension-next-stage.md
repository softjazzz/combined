# LX0609 生产规则扩展能力下一阶段计划

> 执行要求：按三个独立闭环顺序实施。每个闭环完成后单独提交、报告验收结果并停止；不得把后续闭环或相邻规则修复顺带并入。

## 目标

证明一条业务定义完整的真实生产规则可以沿现有统一主链上线，而不需要在结果聚合器、公共任务入口、保存层、API DTO 或前端状态解释中增加规则专属逻辑。

目标链路：

```text
规则总表声明
  → 所属规则族与执行合同
  → 现有执行器产出 RuleDecision + fact_refs
  → 公共 Binding 校验与证据投影
  → Canonical Result
  → Aggregator 只装配、排序和统计
```

本阶段不以聚合器行数为目标，也不全面清理 75 条旧规则。

## 最新基线与判断

评估意见的方向正确，但应结合 2026-09-05 已完成工作更新基线：

- 基础时限规则族 `LX0609-001/002/004/005/006` 已完成职责收口；聚合器不再导入或调用该族专属事实校验、客户证据生成和来源过滤。
- 显式启用 `LUXIAN_0609_UNIFIED_ENGINE_ENABLED=true` 的正式主链回归已通过；基础时限族未回流旧执行器。
- LX0609 全量单元测试共收集 4256 项，排除 5 个已有固定基线节点后为 4251 passed、0 failed。
- 当前 `luxian_0609_result_aggregator.py` 为 6308 行，仍包含 67 个不同规则号、223 次规则号引用；这是其余规则族的历史债，不能据此否定已完成的基础族闭环。
- `rule_master` 和 `phase_scope` 仍分别硬编码 `001..075`，这是当前扩展生产规则的第一阻塞点。
- 生产代码中没有已批准的 `LX0609-076/077` 业务定义；现有 990/991 只是测试合同，不能作为生产扩展已通过的证据。

因此，最难的边界方向和基础合同已经验证，但决定真实扩展成本的最终门禁尚未通过。

## 架构红线

1. 技术失败固定为 `technical_error`；不得映射为 `data_gap`、`uncertain` 或 `not_applicable`。
2. 执行器只选择事实与 `fact_refs`；Binding 验证引用真实性和同源性；公共投影统一生成文书 ID、字段路径和时间。
3. Renderer 只增加声明式标题、说明和整改模板，不得重新计算状态或事实。
4. 不新增 Bundle、Resolver、注册中心、状态机、配置开关或隐式 fallback。
5. 不修改 `custom_qc_sample_pool_service.py`；样本池治理不属于本阶段。
6. 不为普通 DTO、Prompt、trace 或临时结果增加 SHA/digest。
7. 所有主链验收必须明确记录实际 `executor_key`、兼容批次为空、旧 wrapper 为空且未发生自动回退。

## 闭环一：统一规则目录 ID 集合权威

### 目的

只消除 `rule_master` 与 `phase_scope` 对规则 ID 集合的重复所有权，不新增生产规则，不改变现有 75 条规则的状态、Prompt、合同或客户结果。

### 设计决策

- `rule_master` 是规则 ID 有序集合的唯一权威。
- `rule_master` 编译器不再固定 75；它根据自身条目数量验证 `LX0609-001..N` 连续、有序、唯一。这样 076 可以追加，同时仍能阻止遗漏、重复和乱序。
- 删除固定 `_EXPECTED_STATUS_COUNTS`。保留每个条目的 `implementation_status` 合法性及元数据完整性校验；汇总数量从实际条目计算。
- `phase_scope` 保留“发布阶段状态”的所有权，但其 ID 顺序必须完全等于同版本 master，不再自行生成 `001..075`。
- 生产 JSON 在本闭环保持不变，生产运行结果仍是 75 条。

### 文件白名单

生产代码：

- `backend/app/services/luxian_0609_rule_master.py`
- `backend/app/services/luxian_0609/phase_scope.py`

测试与验收：

- `backend/tests/unit/test_luxian_0609_rule_master.py`
- `backend/tests/unit/test_luxian_0609_phase_scope.py`
- `backend/tests/unit/test_luxian_0609_production_extension_boundary.py`
- `docs/acceptance/2026-09-05-lx0609-rule-directory-single-authority.md`

禁止修改：

- 两份生产目录 JSON；
- `luxian_0609_result_aggregator.py`；
- 执行器、Prompt、Renderer、任务入口、保存、API、数据库和前端。

### TDD 步骤

1. 先把现有“076/077 必须被拒绝”的测试改为新的红测：临时 master 追加 076 后编译成功。
2. 增加 master 失败测试：空列表、重复 ID、缺号、乱序和非法格式均 fail closed。
3. 增加 phase 红测：临时 phase 追加 076，且临时 master 同步包含 076 时编译成功。
4. 增加 phase 失败测试：相对 master 缺少、额外、重复或乱序时均 fail closed。
5. 最小修改两个编译器使红测通过。
6. 冻结当前生产目录：仍精确返回 75 条、原顺序、原状态汇总、原 phase 状态和原客户交付范围。

### 验收标准

- 临时声明式 076 能通过正式 master 和 phase loader，不再因固定 75 条被拒绝。
- 当前生产目录仍为 75 条，任何 Canonical 结果均不变化。
- `git diff --name-only` 只出现文件白名单。
- 聚焦测试通过；全部 `test_luxian_0609_*.py` 相对固定基线无新增失败。
- 不调用真实模型，不写数据库。
- 独立提交：`重构：统一 LX0609 规则目录边界`，随后停止。

## 闭环二：真实 native 规则 076 生产扩展

### 启动门禁

必须先由业务批准一条真实规则，并明确：

- 规则名称、适用文书和政策依据；
- 触发事件与不适用条件；
- 必要数据源和权威字段；
- 确定性判定公式、阈值及边界时刻；
- `compliant/non_compliant/not_applicable/data_gap/uncertain/technical_error` 的映射；
- 客户事实、证据字段、处理建议；
- 五种覆盖形状对应的真实或脱敏病例。

没有完整业务定义时不得把 990/991 政名为 076，也不得编造生产规则。

### 五种覆盖形状

1. 触发且合规；
2. 触发且确定问题；
3. 触发事件不存在，结果为 `not_applicable`；
4. 已触发但已接入关键资料缺失，结果为 `data_gap`；
5. 临界时刻、重复事件或关联冲突等边界案例。

### 允许的修改面

业务批准后，先补一份实施附录，写明唯一所属规则族和具体执行器文件。原则上只允许：

- `backend/app/data/luxian_0609_rule_master_v1.json`
- `backend/app/data/luxian_0609_phase_scope_v1.json`
- `backend/app/data/luxian_0609_rules_v1.json` 或现有 phase-1 extension（二选一，不重复声明）
- `backend/app/data/luxian_0609_rule_contracts_v1.json` 或现有 contract extension（二选一）
- `backend/app/services/luxian_0609/customer_rule_package.py`
- 已选规则族的现有执行器文件
- 必要的声明式 Renderer 文案配置
- 对应规则测试和验收文档

如果预检发现必须修改聚合器、公共任务入口、保存、API DTO 或前端解释，立即停止。先把该规则族的重复业务所有者作为另一个独立闭环迁出，不能把架构迁移混入 076 业务实现。

### 验收标准

- 076 进入正式 loader、package plan、统一引擎、Binding、公共证据投影和 Canonical 保存链。
- `executor_key` 为已批准规则族；`compatibility_rule_ids`、`compatibility_execution_rule_ids` 和 `legacy_wrapper_rules` 均为空。
- 聚合器没有新增 `LX0609-076` 或规则专属条件分支。
- 五种覆盖形状通过，证据定位到真实文书 ID、字段和时间。
- 独立提交：`新增：实现 LX0609-076 <真实规则名称>`，随后停止。

## 闭环三：真实受控语义规则 077 与三入口验收

### 启动门禁

除闭环二的业务定义外，还必须冻结：

- 最小必要上下文及裁剪规则；
- 单次模型调用上限；
- Prompt 版本；
- 严格输出 schema 和有限枚举；
- 非法结构、超时和执行异常统一为 `technical_error`；
- 事实存在但语义置信不足才允许 `uncertain`；
- 输入 Token 上限和脱敏要求。

如果选中的语义规则属于尚未收口的规则族，先以独立提交完成该族职责迁移，再实现 077；不得在同一提交里一边迁移一边改变质控口径。

### 三个正式入口

使用相同病例分别验证：

1. 单规则执行；
2. 病历池批量质控；
3. 客户样本验证。

三者必须具有相同 `executor_key`、Prompt、输入材料、Canonical 状态、原因码、客户事实和证据坐标，且均不进入旧执行器。

重点测试落点：

- `backend/tests/unit/test_luxian_0609_production_extension_boundary.py`
- `backend/tests/unit/test_luxian_0609_execution_routing.py`
- `backend/tests/unit/test_qc_sichuan_batch_throughput.py`
- `backend/tests/unit/test_qc_sample_pools_router.py`

### 性能协议

- 确定性 Stub：调用次数、Prompt、输入 Token 和 Canonical 结果完全一致。
- 真实模型：相同环境预热后至少运行 10 次；调用次数完全一致；输入 Token 不增加；比较中位耗时，主链集成相对单规则基线回归不得超过 10%。
- 输出 Token 可记录自然波动，但不得用少量样本或平均值替代中位数结论。

### 验收标准

- 077 无聚合器、公共入口、保存、API DTO 或前端状态解释改动。
- 三入口一致性、真实证据定位和十次性能门全部通过。
- 独立提交：`新增：实现 LX0609-077 <真实规则名称>`，随后停止。

## 旧债后续治理策略

闭环三完成后不立即拆完整聚合器。采用“规则族触发迁移”：

- 旧规则仅运行且无业务修改时，保留现状；
- 某规则族再次需要改变业务口径或增加规则时，先冻结该族行为；
- 以独立结构提交迁出该族在聚合器中的状态解释、事实校验和证据选择；
- 迁移通过后，再以另一个提交实现业务变化。

每次迁移的完成标准是该规则族在聚合器中的业务分支归零，不是父文件减少多少行。

## 下一步执行建议

立即只执行“闭环一：统一规则目录 ID 集合权威”。它是当前唯一已具备完整代码证据、无需新增业务定义且能直接解除 076 阻塞的任务。

闭环一通过后，由业务方选定并批准真实 076。未获得业务定义前停止，不提前创建执行器、不扩展公共层，也不把测试合同当作生产规则。
