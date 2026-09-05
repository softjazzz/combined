# 质控引擎验收补齐与技术债治理实施计划

**Goal：** 补齐会诊族 020–023 的事实单一所有者和真实业务入口验收，并为两个巨型服务文件形成有证据、可分批实施的治理清单。

**Architecture：** 继续使用现有执行器、Binding、公共证据投影和 Canonical 合同。执行器产生业务事实；投影与 Finalizer 验证合同，拒绝矛盾数据；聚合器装配结果。技术缺陷修复与结构迁移分别提交。

**Tech Stack：** Python、FastAPI、pytest、PostgreSQL/隔离测试数据库、Vue 现有结果工作台。

**执行方式：** 沿用用户指定的 Terra / high 子代理实施，主协调 Agent 负责调用链确认、方案和最终审查。执行时采用现有 executing-plans 流程；本文件是计划，不代表已经开始代码修改或业务库写入。

## 当前基线与范围

- 审查基线：`56218fa4e`；历史冻结 `b98e26e72`，会诊迁移 `29841a0f3`。
- 已完成：聚合器移除 020–023 专属分支；master 按实际声明数量校验，phase 与 master 一致。目录相关 37 项测试已重新通过，不重复实现目录扩容。
- 未闭合：会诊事实投影重算计数、三业务入口覆盖不足、历史结构提交包含状态修复、性能材料未完整进入可复查交付物。
- 两个巨型文件已有治理价值。本阶段必须形成完整职责台账及首个候选的实施边界，禁止以“先审计”为由无限延长。
- 不新增未定义的生产规则。076/077 仅作为后续编号示例，不视为已批准业务。
- 用户现有前端修改、临时病例文件及隔离 worktree 均不纳入本任务提交。

## 工作包 A：纠正验收基线（文档独立提交）

**负责人：** 主协调 Agent。

**文件：**

- 修改 `docs/acceptance/2026-09-05-consultation-family-b3-business-entry-and-performance.md`。
- 修改 `docs/acceptance/2026-09-05-production-extension-boundary.md`。
- 必要时为 B2 验收记录增加后续勘误链接，保留历史事实。

**步骤：**

1. 把 B3 结论改为“worker 集成和局部性能验证通过，全族业务验收待补”。
2. 明确记录 technical_error → compliant 是已提交迁移中包含的既有缺陷修复，不能称为最终状态等价。
3. 将目录“固定 75 条拒绝扩展”改为已解决；仍区分 loader 扩展和真实新规则上线。
4. 对此前 Goal 关闭保留勘误记录；不改写 Git 历史、不倒置既有提交。

**完成标准：** 文档与当前源码一致，每项“通过”均注明证明范围；历史行为偏差不能靠重新命名基线消失。

## 工作包 B：会诊事实计数合同纠偏（缺陷修复独立提交）

**负责人：** 实现 Agent A；主协调先核对四个计数生产点，再派发。

**文件白名单：**

- `backend/app/services/luxian_0609/consultation_customer_projection.py`
- `backend/app/services/luxian_0609/native_consultation_episode_execution.py`（仅计数生产点确有矛盾时修改）
- `backend/tests/unit/test_luxian_0609_consultation_customer_projection.py`
- `backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py`
- `backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py`（仅对应反例）

**权威口径：** 执行器采用的逐条建议事实是汇总计数依据，执行器同时交付一致的汇总。投影层可以计算期望值做验证，但不能覆盖输入计数；未知执行状态不得被合并为“缺失”。

**步骤：**

1. 先检查 `recommendation_results` 是否完整、是否可能截断；若只是展示子集，不按子集校验全量计数，必须先明确现有合同再实现。
2. 添加失败反例：完整明细有 2 条 missing，输入汇总却为 0；现状若悄悄修正，测试必须失败。
3. 完整明细与计数矛盾时投影返回合同无效，由现有 Finalizer 收敛为 `technical_error`；保留当前技术原因码合同。
4. 添加正常、unknown、空集合、越界及单规则隔离反例；不得影响同任务其他规则。
5. 保证原本有效输入的 status、reason、facts、文书坐标、Prompt、调用数保持一致。

**验证命令：**

```powershell
python -m pytest -q -o log_cli=false backend/tests/unit/test_luxian_0609_consultation_customer_projection.py backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py
```

**完成标准：** 后续层不再悄悄修正会诊业务计数；技术合同错误不能变成 data_gap 或 uncertain。只修改已定位缺陷，不借机重构执行器。

## 工作包 C：实际任务创建入口到证据查看验收（测试独立提交）

**负责人：** 测试 Agent B；可以与 B 并行写测试，最终验收依赖 B 完成。

**文件：**

- 新增 `backend/tests/integration/test_luxian_0609_consultation_api_entry_flow.py`。
- 复用 `backend/tests/integration/test_luxian_0609_consultation_business_entry_flow.py` 的隔离资料与数据库能力，避免另造测试执行器。
- 只读定位 `backend/app/routers/qc_sichuan.py` 中 `create_workspace_batch_job`。
- 只读定位 `backend/app/routers/qc_sample_pools.py` 中 `run_sample_pool_intrinsic_validation`。
- 只读定位 `backend/app/services/custom_qc_sample_pool_service.py`、`sichuan_workspace_batch_worker.py` 的正式派发路径。

**步骤：**

1. 主协调记录三个 UI/API 入口实际使用的请求字段、创建服务、调度及 worker 调用链；确认运行和终末 scope 的覆盖。
2. 使用 TestClient/等效 API 集成环境发起单规则、病历池批量、客户样本验证任务。资料读取及外部模型可替换为受控输入，目录、规则选择、创建服务、派发和结果保存不能替换为成功 stub。
3. 至少覆盖五类输入：无会诊；明确申请和意见且已执行；多次会诊中部分缺陷；资料/关联不足；非法模型输出或事实合同。包含需要实际语义客户端调用的案例。
4. 逐条运行 020/021/022/023，组合执行，并保留 069 对照；对同输入比较状态、原因码、关键事实、证据坐标和客户结论。
5. 跟踪实际 executor_key、单次逻辑调用数和异常路径，验证未进入旧执行器。增加非法 attribution 贯穿 worker 失败且不交付成功 Canonical 的反例。
6. 保存结果后，从实际证据读取接口检查安全引用可解析为正确文书；不能只断言引用满足正则。
7. 选正常、缺陷、资料不足各一例，在现有前端打开并点击定位，记录结果。浏览器验收不与用户未提交 UI 修改混为生产代码变更。

**完成标准：** 测试从实际创建入口开始，覆盖全族和失败隔离；相同病例三个入口结果一致，证据能读到正确文书。真实客户资料只读提取为授权、脱敏测试材料；无可用病例时必须标记欠缺，合成数据不能冒充真实病例。

## 工作包 D：复放与性能证据补齐（验收材料独立提交）

**负责人：** 验证 Agent C；性能采样在 B 稳定、重型并行测试停止后进行。

**文件：**

- 新增 `backend/scripts/verify_consultation_family_acceptance.py`（优先复用已有可运行基准脚本；存在时不重复创建）。
- 新增 `docs/acceptance/2026-09-05-consultation-family-followup-acceptance.md`。

**步骤：**

1. 找回前次原子保存的逐轮结果、配置和复放脚本，先复用，不因文档缺链接重新付费跑模型。
2. 对相同合法原始响应做历史基线/当前代码零网络复放，固定首次分叉位置，证明技术修复；同时验证非法响应仍是技术错误。历史差异单列为缺陷修复，其他不变输入严格比较。
3. 从五类输入选确需语义判断的固定病例，固定模型和输入；记录预热轮次并剔除。材料不足时才补采基线/候选各至少 10 次交替运行。
4. 保存逐轮调用数、输入/输出 Token、API 和端到端耗时、最终状态。不得提交凭证或原始身份信息，不增加 SHA/digest。
5. Prompt 逐字符相同，调用数相同，输入 Token 不增加；比较中位耗时，回归不超过 10%。只报告该采样范围性能，不宣称整个系统提速。

**完成标准：** 他人可以根据脚本、参数及脱敏材料复放核心证据；真实模型采样与本地确定性结果比较分别说明。

## 工作包 E：两个巨型文件的治理台账（只读审计独立提交）

**负责人：** 主协调 + Agent C；与 B/C 并行做只读调查，D 采样时暂停重型检查。

**只读文件：**

- `backend/app/services/luxian_0609_result_aggregator.py`
- `backend/app/services/custom_qc_sample_pool_service.py`

**产物：** `docs/plans/2026-09-05-qc-large-service-responsibility-ledger.md`。

**步骤：**

1. 聚合器按规则族列出剩余状态解释、事实校验、证据选择、文案及装配职责，定位真实调用者和已有反例。
2. 样本池按真实代码列出候选职责，例如样本匹配、资料同步协调、任务创建/派发、进度/结果管理；这些是审计维度，不预先认定为拆分模块。
3. 每个候选记录调用边界、共享状态/事务、公开入口、既有测试、最近修改证据、迁移风险和收益。
4. 按已发生错误、重复所有者、冲突频率和可隔离性排序；主协调选出一个首批完整职责，指定文件白名单、冻结病例和回滚方案。
5. 原则上迁出至少 250 行完整职责；少于该值必须有消除重复所有者或安全风险的证据。记录父文件、新模块和生产代码净增减，不能靠转发壳降行数。

**完成标准：** 两个文件都有完整清单、优先级及负责人；首个候选已有可执行设计。实际结构迁移另作独立提交，必须在对应基线冻结后启动；本阶段不承诺未经审计的切分数量或行数目标。

## 执行顺序与并发

1. 主协调完成 A 并明确 B 的计数合同。
2. Agent A 实现 B；Agent B 编写 C；Agent C 审计 E。三者文件白名单不重叠。
3. 主协调审查 B 关键 diff；C 在稳定版本完成接口和前端验收；Agent A 转做独立证伪。
4. Agent C 完成 D，主协调核查模型输入、逐轮结果、状态差异及真实证据定位。
5. 聚焦测试通过后运行一次影响范围全量回归；新增失败才扩大检查，避免重复全量运行。
6. 主协调出具逐项通过/未通过清单，发布下一次单职责迁移的具体范围。

## 提交与最终门禁

- 文档勘误、计数合同修复、入口测试、复放性能材料、治理台账分别提交；不重写已有历史提交。
- 代码提交前执行针对性 Ruff、pytest、`git diff --check`、UTF-8/LF 和项目编码检查。编码检查若扫描 0 文件，必须显式核验本次文件，不能算覆盖通过。
- 前端 lint 使用现有 ESLint 的非修复调用检查，避免修改用户脏文件；本阶段不改共享前端类型，不反复运行全量 type-check。
- 测试写入使用明确的隔离数据库；需新建 PG 数据库/schema 时单独确认，不对本机业务库或客户源库写入。
- 本阶段完成意味着会诊族所有已承诺验收项已证明或明确未通过，且两个大文件有下一批治理边界；不等于整个引擎技术债清零。
- 若三入口验证出现新的生产缺陷，先固定反例并单独修复；不扩大为全引擎重构。
- 新规则扩展排在本阶段之后。已有正式业务定义时选择一条 native 和一条语义规则；定义不足就保留待办，不编造生产规则凑验收。
