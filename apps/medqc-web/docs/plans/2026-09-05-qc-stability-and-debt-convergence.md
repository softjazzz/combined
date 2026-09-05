# 质控稳定性与技术债收口实施计划

**Goal：**关闭已知回归失败，消除会诊规则族在聚合器中的重复业务所有者，并形成样本池服务可执行、可回滚的拆分方案。

**Architecture：**复用现有执行器、RuleDecision、Binding、Finalizer 和公共证据投影。先修正缺陷建立绿色基线，再冻结一个完整规则族并等价迁移；样本池仅并行审计，代码迁移另立闭环。

**Tech Stack：**Python 3.10、pytest、PostgreSQL、SQLAlchemy、Vue、现有 LX0609 统一执行链。

执行采用 executing-plans 的阶段检查方式。本文负责确定范围与门禁；涉及尚未证实的根因和新模块接口，须先完成指定调查产物，不预先编造实现。

## 1. 决策与已完成基线

本计划调整前一份《LX0609 生产规则扩展能力下一阶段计划》的执行顺序：先稳定性修复，再主动治理会诊族，随后恢复真实 076/077 扩展验证。旧计划的真实规则业务定义及验收要求继续适用。

已完成项目，不重复实施：

- `dfe22c443`：基础时限规则族收口。
- `dc3bdb209`：规则目录 ID 集合由 master 唯一声明，phase 与其完整同序，未激活规则不能被 phase 标为可执行。

最新实测基线：4271 项 LX0609 测试，5 项失败、4266 项通过；排除相同 5 项后为 4266 passed。该结果只能证明当时的增量未引入其他失败，不能作为完整发布门全绿的证明。

当前规模参考：聚合器 6308 行、近 90 天 110 次修改；样本池服务 6717 行、近 90 天 20 次修改。行数作为风险提示，不作为拆分目标。

本计划交付范围：阶段 A 的缺陷关闭、阶段 B 的一个完整会诊族收口、阶段 C 的样本池拆分审计。不会把这三个成果表述为全系统技术债清零。

## 2. 工作区、分工与提交规则

- 启动时记录 HEAD、工作区已有改动及各阶段测试清单。当前前端脏改属于用户，禁止混入本计划提交。
- 主协调 Agent 亲自核对调用链、根因、最小修改范围及验收结果；实现代理编码，独立审查代理证伪。
- 可并发：A 的两组只读排查、C 的只读审计；不可并发写同一文件。
- 阶段 B 必须等待 A 全绿。C 不依赖 A，可先出审计文档，但不直接迁移代码。
- 每个缺陷或迁移使用独立提交。提交验收后结束该闭环；阶段内按已批准顺序推进，扩大规则族或公共合同需重新评审。
- 测试应使用隔离环境。先检查 conftest、应用启动钩子和测试数据库地址，避免宽泛测试命令触发本机业务数据库初始化或写入。

## 3. 阶段 A：关闭 5 个既有回归失败

### A1. 复现并分类

读取并运行以下实际失败点，保留完整结果和耗时：

| 位置                                                                        | 失败点                                                                                        | 必须确定的问题                                               |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py`         | `test_severity_order_reader_accepts_only_audited_effective_statuses_without_echo` 的 3 个参数 | row_ref 改变是否符合有效状态与来源身份合同，还是资料字段丢失 |
| `backend/tests/unit/test_luxian_0609_evidence_snapshot.py`                  | `test_059_binds_only_event_order_and_course_decision_support_sources`                         | v23/v24 是否只是快照断言过期，059 的来源集合是否准确         |
| `backend/tests/unit/test_luxian_0609_native_extended_document_execution.py` | `test_070_multi_transfusion_preserves_canonical_decision_facts_and_evidence`                  | 输血及检验证据在哪一层消失，是否属于真实证据缺陷             |

运行目录为项目根，命令：

```powershell
py -3.10 -m pytest backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py backend/tests/unit/test_luxian_0609_evidence_snapshot.py backend/tests/unit/test_luxian_0609_native_extended_document_execution.py -q --capture=fd --tb=short -k 'test_severity_order_reader_accepts_only_audited_effective_statuses_without_echo or test_059_binds_only_event_order_and_course_decision_support_sources or test_070_multi_transfusion_preserves_canonical_decision_facts_and_evidence'
```

产出 `docs/acceptance/2026-09-05-qc-regression-baseline-repair.md`：逐项写明复现、根因、业务影响、修改文件和验证方案。初始失败的 5 项必须全部可追踪；单跑与全量结果不一致时调查测试顺序和缓存污染，不以单跑成功结案。

### A2. 摘要与版本断言修复

1. 对照来源读取、规范化字段和既有身份合同，确认是否有生产缺陷。
2. 若实现正确，仅替换过时测试：比较有效状态、关键字段、来源定位及必要身份不变量。
3. 若实现错误，先补能体现资料错误的失败用例，再最小修改生产代码。
4. 版本校验保留真正的来源合同一致性门禁；不能简单删除全部版本/完整性断言。
5. 跑对应文件及来源注册/Binding 影响范围，独立提交。

候选只读生产文件为 `backend/app/services/luxian_0609/evidence_snapshot_provider.py`、`source_evidence_reader.py`、`source_registry.py`（后三者均在同一 luxian_0609 目录）。实际生产修改白名单由 A1 根因确定；无缺陷证据时不改生产代码。

### A3. 070 多事件证据闭环

1. 沿执行器选择 → fact_refs → Binding → 公共证据投影 → Canonical 保存/读取逐层比较，找到首次丢失位置。
2. 核对入院、输血和检验各文书的真实身份、字段和时间，确认预期证据确实参与本规则判定。
3. 对真实问题建立最小回归：多次输血、同次不同检验、关联冲突、非法或跨病例引用。
4. 若证据应当存在则修复丢失点；若旧预期错误则记录理由并改为正确语义断言。不能通过放松同源校验、猜文书 ID 或恢复旧投影解决。
5. 通过统一执行入口验证状态、事实和证据，再验证保存读取及前端定位；使用合法授权的本机样本，外部模型只接收已核验脱敏的必要信息。
6. 独立提交，报告证据修复带来的变化。

候选调查文件：`native_extended_document_execution.py`、`decision_binding.py`、`customer_evidence_enrichment.py`、`canonical_result_finalizer.py`（均位于 `backend/app/services/luxian_0609/`），以及 `backend/app/services/qc_workspace/canonical_result_store.py`。只允许修改已证明的首个缺陷及必要调用方，不借机迁移整个输血族。

### A4. 绿色基线验收

在隔离测试环境运行完整 LX0609 测试，不带 `-k not`、`--deselect`，不新增 skip/xfail：

```powershell
$RuleTests = Get-ChildItem -LiteralPath 'backend/tests/unit' -Filter 'test_luxian_0609_*.py' | ForEach-Object { $_.FullName }
py -3.10 -m pytest @RuleTests -q --capture=fd --tb=short
```

门禁：5 个原始失败全部通过，无新增失败；目录范围仍为当前批准的 75 条；技术错误保持 technical_error。真实数据不足以复核 070 时明确标记业务验收未完成，不能仅用测试数量替代。

## 4. 阶段 B：会诊规则族等价迁移

候选范围为 `consultation_fact_contract.py` 当前定义的 020/021/022/023。先核实实际合同和执行器覆盖，再锁定完整范围；069 会诊时限不因名称相似自动并入。

### B1. 亲自审计并冻结行为（仅测试与文档提交）

逐项列出聚合器中本族所有规则号分支、别名分支、事实校验、状态解释、来源选择和证据生成，以及 Finalizer、Store、Renderer、导出与调试信息中的所有调用者。

将修改理由分为五类：必要规则实现、规则元数据、公共合同校验、历史兼容、重复判断。产出 `docs/acceptance/2026-09-05-consultation-family-ownership-baseline.md`，标出迁移前后每项职责的唯一所有者、拟修改文件和删除位置。

优先复用已有文件：

- `backend/app/services/luxian_0609/consultation_fact_contract.py`
- `backend/app/services/luxian_0609/consultation_020_relation_contract.py`
- `backend/app/services/luxian_0609/native_consultation_execution.py`
- `backend/app/services/luxian_0609/native_consultation_episode_execution.py`
- `backend/app/services/luxian_0609/decision_binding.py`
- `backend/app/services/luxian_0609/customer_evidence_enrichment.py`
- `backend/app/services/luxian_0609/canonical_result_finalizer.py`
- `backend/app/services/luxian_0609_result_aggregator.py`

新模块仅在已有模块无法承载完整安全事实合同且审计说明收益后采用；模块名、接口和文件白名单写入 B1 产物，避免迁移中临时增加转发层。

冻结至少五类病例：单次会诊明确意见、多次会诊混合结果、无会诊且资料完整、资料缺失/关联不确定、模型非法输出/超时。保留曾误报的“继续既定治疗并随访”案例及逐次证据。

冻结字段：status、reason_code、关键事实、fact_refs 对应的真实来源、证据 ID/字段/时间、客户结论、调试信息、Prompt、调用次数和 Token。忽略任务 ID 等运行期随机字段，不忽略业务差异。发现临床口径缺陷时先独立修复，再重新冻结。

### B2. 迁移并移除旧业务实现（生产结构提交）

1. 执行器作为判定与证据选择唯一所有者，输出 RuleDecision 和 fact_refs。
2. 已有规则族合同校验客户安全事实，Finalizer 调用统一接收边界；公共 Binding 和证据投影负责坐标。
3. 聚合器保留通用装配，删除本族原状态解释、事实结构校验和证据生成。
4. 检查保存、导出和调试接口不再借道旧族投影；必要的历史入口只委托同一权威实现，不保留第二套业务算法。
5. 迁移提交保持 Prompt、临床口径、状态与公开合同不变；不清除全系统旧入口，不新增 fallback、开关或注册中心。

### B3. 正式主链、性能及定位验收

现有测试落点：`test_luxian_0609_native_consultation_execution.py`、`test_luxian_0609_native_consultation_episode_execution.py`、`test_luxian_0609_consultation_fact_contract.py`、`test_luxian_0609_mainline_services.py`、`test_luxian_0609_result_aggregator.py`（均在 `backend/tests/unit/`）。对应新增冻结测试由 B1 定名。

使用同一材料和同一评价时点验证单规则、病历池批量、客户样本验证三个业务入口。必须有实际任务 trace 和保存后结果，单纯调用 prepare 函数不等于三个入口完成。

门禁：

- 运行配置 unified engine 开启；每规则实际 executor_key 一致，无异常回退或旧 executor 调用。
- 本族聚合器业务分支、事实校验和证据生成归零；删除旧来源猜测，而非被后续结果覆盖。
- 冻结 Canonical 语义、客户结论和证据坐标逐项相等；原文定位可打开对应文书，调试字段保留。
- Stub 前后 Prompt、调用次数与输入 Token 完全一致。
- 真实模型在同模型、参数、并发、病例和机器条件下，迁移前后各预热后至少 10 次，交替取样；输入 Token 不增加、调用次数一致，报告中位耗时，回归不超过 10%。输出 Token 自然波动另列，失败与重试也计入报告。
- 实测未达标时报告失败，不用约 1 ms 的绝对值替代已批准的比例门禁；需要调整测试协议必须先说明证据。
- 完整 LX0609 回归零失败；公开接口和数据库 schema 无变化。

报告父文件行数变化、新模块行数、生产净增减、迁出职责、公开接口变化、回归耗时和未迁出职责。全族验收后结束阶段，不顺带迁移下一个族。

## 5. 阶段 C：样本池服务只读拆分审计

文件：`backend/app/services/custom_qc_sample_pool_service.py`。现有测试：`backend/tests/unit/test_custom_qc_sample_pool_service.py`、`test_qc_sample_pools_router.py`、`test_qc_sample_pool_permissions.py`。

1. 画出分类推荐、Excel 导入、病例匹配、住院范围、同步任务和池 CRUD 的依赖及事务边界。
2. 对“人工问题分类与规则推荐”与“病例匹配/同步”候选比较调用方数量、共享状态、已有测试、历史缺陷与改动频率。
3. 选择一个能完整迁移的职责，记录接口、精确文件范围、预期删除位置和冻结测试。优先复用现有模块。
4. 重点核对事务、锁、幂等、取消/重试、权限、三坐标身份、同步水位与最新任务归属；不能把一次事务拆成多个提交。
5. 产出 `docs/plans/2026-09-05-sample-pool-responsibility-audit.md`。若无法证明清晰边界和收益，写明原因，结论可以是暂不迁移。

本阶段只交付审计及一个具体建议；样本池代码迁移另立任务，不与聚合器迁移一起上线。若决定迁移，原则上迁出至少 250 行完整生产职责；不足时必须证明消除了重复所有者或明确安全风险，不以样板代码凑数。

## 6. 提交、回滚与退出条件

- A 的每个缺陷、B1 冻结、B2 结构迁移、B3 验收、C 审计分别提交。仅暂存对应白名单；不 push 或部署客户机。
- 提交前按项目规则运行编码和 lint 等检查，Python 改动补 Ruff；闭环完成再运行适当全量回归。已有前端脏改引起的检查问题单独报告，不随手修复。
- 对比在修复后的绿色提交与迁移后提交上执行。需要并行运行版本时使用隔离 checkout，数据库和输出目录独立。
- 出现状态漂移、证据错位、重复 LLM 调用、事务/权限改变或性能门失败时，停止该结构闭环，保留诊断材料；用独立回退提交恢复该结构提交，避免覆盖其他改动。数据库写操作不依赖 git 回退恢复。
- 阶段 A：5 个旧失败关闭，完整 LX0609 门全绿。
- 阶段 B：一个完整会诊族的聚合器业务所有权退出，三入口、定位和性能验收完成。
- 阶段 C：样本池形成一份经审查的可执行拆分方案或有证据的暂缓结论。
- 任一验收缺真实样本、源库或模型条件时，明确列出未完成项，不以合成测试替代业务验收。

本计划完成后，恢复真实 076/077 的业务定义和扩展验证。剩余族与样本池生产拆分按各自独立任务推进，不承诺两个大文件在本阶段全部拆完。
