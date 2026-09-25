# 原始 LX0609 阶段 C 启动前只读盘点

## 2026-09-25 当前工程合同复验

在提交 `de9c0ce65` 上重新加载正式依赖目录：84 条规则，`native_sync` 8 条、`native_async` 76 条，兼容执行模式 0 条；计数包含新增规则，仅用于验证协议，不计作原始规则医学验收。旧 `build_luxian_0609_legacy_executor_registry` 仍由生产 `execution.py` 调用并包装 11 个现役族函数，因此不存在可直接删除的已替代适配。目录/合同漂移拒绝、临时四段式规则进入正式任务路由、Worker、执行、隔离 SQLite Canonical 与公开 DTO 的三份聚焦测试 **26/26 通过**；测试规则未加入产品目录，保存/API/前端无此规则特例。

按主计划“再收敛”表中 C 的**工程关闭依据**，属性所有者、拒绝漂移、正式扩展链与旧适配保留理由已具备，可将 C 记为“工程合同已验收”。这不代表原始规则的独立临床保护集或客户部署通过；整体 A/B/C/D goal 继续 active。若后续公共边界改动破坏这三份测试，C 须重新打开。

## 2026-09-25 旧适配保留审计

在当前集成树 `aec9ecfb2` 只读核对：`load_luxian_0609_dependency_inventory()` 返回84条目录规则，执行模式为 `native_sync` 8条、`native_async` 76条，没有 `compatibility` 模式。这个全目录计数含独立新规则，只用于确认适配调用形态，不能把新规则计入原始引擎医学验收。正式 `execution.py` 仍在 Native Engine 调用前把11个现有规则族函数包装成 `LegacyNativeExecutorFunctions`，并在 `build_luxian_0609_legacy_executor_registry` 注册相同11个回调；`executor_registry.py` 末端用规则合同执行器键集合拒绝漂移。该适配器是现有规则族函数与统一执行信封之间的在用边界，不是已被替换的旧执行结果通道。当前没有可删除的替代实现；直接移除会切断正式 Native 执行，另建一层只是增加链路。保留它并记录 owner，比按文件名强制删除更符合阶段 C 约束。

阶段 C 的测试专用规则已走过正式 Worker、现有注册表、SQLite Canonical 保存与公开 DTO，证明扩展路径；上述只读审计补充了旧适配保留理由。未覆盖客户 PostgreSQL、浏览器或全原始规则临床保护集，阶段仍按主计划保持局部验证。

## 2026-09-25 正式 Worker→Workspace→Canonical 纵向验证

沿用仅存在于 pytest 临时目录的 `LX0609-99-99-01`，本次把前面的手动组件衔接升级为正式任务执行路径：路由接纳并冻结规则范围，真实 `run_sichuan_workspace_batch_job` 从隔离 SQLite 任务表 CAS 领取任务、核对冻结运行身份并执行生产 `prepare`，经现有注册表接收测试执行器的固定 Decision。真实 `CustomQCWorkspaceService.complete_batch_job` 把任务完成状态和该病例的 Canonical Envelope 置于一个事务中保存；测试随后用相同任务/病例/规则集坐标读回 `compliant/requirement_satisfied`，并投影公开 DTO。测试只替换外部病例读取、产品激活和模型执行器；未修改目录/Worker/保存代码的医学逻辑，也未访问患者资料或客户库。该证据替代下文旧版“未运行 Worker、保存由测试手动衔接”的限制，但仍不是 PostgreSQL 多进程、真实模型、浏览器或临床验收。

验证：纵向测试单项通过、Ruff 通过。与扩展边界、Worker 冻结计划合跑的 22 项通过；另一份旧持久化合同测试在隔离 `DATABASE_URL=127.0.0.1:1` 下其构造函数仍尝试建 PostgreSQL 草稿表，12 项连接失败，不能计为本次代码回归或绿灯。阶段 C 的属性所有者、旧适配替代与部署证据仍需按主计划审计，阶段不关闭。

## 2026-09-25 生产 prepare 路由补证

前一条组件链测试手动把 Decision 交给 Binding，未经过 `prepare_luxian_0609_execution` 的 Typed 范围解析。沿正式路径复核发现，新 Native 异步规则没有旧 rollout 开关时被纳入，但同条件的同步规则被遗漏。测试先在原实现复现解析器不接受同步范围；最小改动是把已冻结计划的 `native_sync_rule_ids` 传给解析器，与异步范围合并，仅作用于无旧 rollout 开关的规则。临时目录中的测试规则在生产 `prepare` 中通过现有注册表调用合成执行器，`decision_rule_ids` 含本规则且 Decision 进入归约；既有调用组另测。该测试仍以替身快照和执行器隔离数据库/模型，未运行正式 Worker 的后台领取与保存，也不证明临床判定。阶段 C 保持未关闭。

本轮后端聚焦 20 项通过；`test_luxian_0609_execution_routing.py` 宽组另 2 项把目录规则总数写死为 49/77，在现有目录中为 50/84，未改动该测试，列为独立测试债。前端 lint、type-check 和全量单测 1066 项通过；Ruff 通过。

## 2026-09-25 测试专用规则纵向补证

集成提交 `0d9639914` 已移除 Native 规则对旧 `mapped_rule_ids` 的强制依赖，兼容模式仍要求该映射。本轮另以 `LX0609-99-99-01` 建立仅存在于 pytest 临时 JSON 中的规则，不改产品目录：主表、执行包装器、规则族和合同覆盖层经现有 loader/编译器一致校验；正式四川任务路由接纳该规则并生成冻结规则范围；生产 Engine 使用测试专用原生执行器形成受控 Decision，随后经 Binding、Aggregator、SQLite Canonical 保存与公开 DTO 读取。规则没有旧映射，保存、API DTO 与前端未新增规则分支。对应测试见 `backend/tests/unit/test_luxian_0609_formal_extension_chain.py`，同扩展/目录邻近共 54 项通过，Ruff 通过。

证据边界：任务路由使用内存 Workspace 替身，路由未提交真实后台作业；Engine 使用测试内注册的执行器，随后以路由返回的 job ID 手动运行组件链并保存到隔离 SQLite。因此这证明各正式组件的规则扩展协议能接通，**尚不证明持久化任务由正式 Worker 自动领取、真实 PostgreSQL 写入、浏览器显示或临床判定正确**。阶段 C 下一项是核对正式 Worker 是否仍按固定规则 ID 构建注册表/跳过测试新规则，并给出必要的最小修复或明确保留理由；旧适配只有在正式路径完全替代后才能删除。

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
