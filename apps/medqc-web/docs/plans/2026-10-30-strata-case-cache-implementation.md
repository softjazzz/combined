# Strata 病例缓存与有界亲和调度开发计划

> 初版仅制定计划。后续用户已授权实施P0，当前交付见
> [P0观测与请求组盘点](2026-10-30-strata-p0-observation-delivery.md)；P1–P5尚未实施。
> 实施时按下列任务逐项执行与复核，不因本计划存在而自动获得客户环境操作授权。

**Goal:** 在保留现有医学判断、证据校验和任务恢复合同的前提下，减少 Strata 重复 Prefill，并以完整病历吞吐验收。

**Architecture:** 复用已有单活动 LLM Gateway；病例与证据归属由业务入口产生，Prompt 适配器仅提供经明确划分的相同证据前缀，Gateway 负责短期 checkpoint 元数据与资源准入。先观测，再接一类可证明复用的请求组，最后增加有界病例亲和；不重写 11 个 Executor，不合并医学判断。

**Tech Stack:** Python 3.10、asyncio、Pydantic、HTTPX、现有 Gateway/Observability、严格隔离的 pytest 与固定应答。

## 1. 已读取资料与固定基线

- 任务附件：`C:/Users/Coldplay/.codex/attachments/c6697876-d31a-471d-9bd3-5cae7b21597f/已粘贴的文本.txt`。
- 技术报告：`C:/Users/Coldplay/Downloads/Strata_客户现场测试与病历质控推理方案_20261030.docx`。
- 原始交接与示例：`C:/Users/Coldplay/Downloads/handoff/HANDOFF-STRATA-CASE-CACHE.md`、`qc_prefix_client.py`、`acceptance_probe.py`。
- 独立工作树：`C:/medqc-strata-case-cache-20261030`。
- 独立分支：`codex/strata-case-cache-20261030`。
- 起点：`af914704fb2427fc1e41e4dd3814b85d2a5dabf1`，包含刚完成隔离验收的 M0/M1/M2；不是 R26.5，也不是已合并的业务集成基线。
- 初版计划时已创建工作树，当时尚未修改功能代码。本功能只依赖 Gateway 前置能力，不要求启用 RabbitMQ；未来正式集成需另外核对前置提交，不整分支盲目移植。

## 2. 当前源码核对结论

以下路径均相对于 `apps/medqc-web/backend`。

| 实际入口/所有者 | 已确认行为 | 对本次方案的限制 |
| --- | --- | --- |
| `app/services/luxian_0609/execution.py::prepare_luxian_0609_execution` | 装配证据快照、隐私包装与 11 类 native 执行资源 | 不能在 Provider 内另查全量病例，扩大某规则可见的证据范围 |
| `app/services/luxian_0609/engine.py::Luxian0609ExecutionEngine.execute` | 处理依赖图、族级信号量、截止时间、取消，并携带 executor 观测上下文 | 保留依赖执行；不在这里增加覆盖整例的串行锁 |
| `app/services/qc_llm_client.py::SichuanQCLLMClient.generate` | 默认把 Prompt 放入单条 user 消息；`_perform_observed_attempt` 再做最终隐私保护与 direct/gateway 分流 | 当前不是 DSH 的 `[system, case, rule]`；只增加 strata_prefix 不会建立共同 checkpoint |
| `app/services/llm_dispatch/client.py::GatewayDispatchClient.complete` | 认证、profile/provider/端点身份校验与端到端剩余预算 | 新增病例元数据必须保持窄合同；不能携带端点或凭据去覆盖服务端路由 |
| `app/llm_gateway/main.py::GatewayRuntime.complete` | 获取资源 lease，实际 Provider task 持有槽位；发送后断开仍跟踪在途，未知在途隔离资源 | Prime 也必须进入同一容量/截止时间/隔离机制，不能另开旁路 HTTP |
| `app/llm_gateway/admission.py::ResourceAdmissionPool` | 按 resource 共享、有界 FIFO、取消撤回及关闭/隔离 | 亲和调度应扩展这一准入 owner，不能在 Worker 各自再建“全局锁” |
| `app/llm_gateway/providers.py::prepare_provider_payload` | 严格白名单；目前不接受 strata_prefix | 只有明确 Strata profile 才能加入该字段，其他 Provider 合同保持 |
| `app/services/unified_rule_engine.py::_build_batch_prompt_compact` | 规则卡片在前、裁剪后的证据上下文在后；预算与质量 profile 会影响材料 | 同例、同规则族也不一定有相同前缀；一包多条规则可能只有一次 API 请求 |
| `app/services/luxian_0609/exam_lab_fact_extraction.py::build_exam_lab_fact_prompt` 及各专项核验 | 主抽取、各专项核验有不同材料投影、事件范围、片段与输出要求 | 首批可评估检查检验族，但不能把所有检查请求视为同一前缀组 |
| `app/services/llm_observability.py` | 已有病例匿名键、族、逻辑调用/attempt、输入/缓存/输出 Token 与总耗时 | 缺少 Strata 实读 Token、Prefill/Decode、Prime 成本等独立观测 |
| `app/services/qc_execution_cache.py` 与 `luxian_0609/*freeze.py` | 分别存在结果缓存与已校验事实冻结 | 与远端 KV checkpoint 是不同层，不能相互冒充或为缓存压测关闭正确的结果复用 |

当前显式 Strata 配置与 Gateway profile 有失败关闭保护。本次补反例，不能增加本地失败转云的兜底。

现有病历/规则族并发不在本次全局调整。MQ 整批路径已有病历上限 4，其他入口仍以实际加载策略为准，不能把旧文档中的固定数字当作所有路径现状。

## 3. 技术决策

### 3.1 选择的路线与不采用的路线

1. **推荐：显式证据组前缀 + 可选 Prime + Gateway 有界亲和。** 可保持既有规则粒度，复用真实相同的输入；需要少量 Prompt 装配适配和现场准确性对照。
2. 只增加 Provider 字段与观测：改动最小，可作为第一阶段，但现有单消息结构不保证有可复用位点，不能据此宣称提速。
3. 整例统一长前缀或联合判断：暂不采用。不同族的证据范围与预算不同；把全例追加给所有规则会扩大上下文，合并判断已有错误 PASS 反例。

不以字符串正则自动切开任意 Prompt，不用最长公共字符前缀推算 Token 位点，不把所有族强制改成全量病历输入。

### 3.2 四种模式与失败语义

拟定 `STRATA_CASE_CACHE_MODE=off|observe|prefix|prefix_affinity`，名称在实施时与现有配置 owner 统一。

- `off`：默认。原消息、参数、调用数与调度保持兼容；不增加 Prime 或缓存字段。
- `observe`：只记录安全指标和可复用组候选，不改请求内容、不增加模型调用。
- `prefix`：仅对显式适配的证据组启用 Prime/复用；其他请求沿原路，不据此保证命中。
- `prefix_affinity`：在 prefix 基础上启用 Gateway 的有界病例亲和。

非 Strata Provider 保持原请求。首版缓存与亲和仅支持已校验的 Gateway 路径；Strata direct 允许 off/observe，误配缓存模式应明确拒绝启用，不静默绕过统一容量。

缓存是性能状态，不产生临床结论；技术错误仍走原有技术失败与恢复合同。合法医学状态继续由执行器决定，不能照抄交接示例把所有错误统一变成 UNCERTAIN。

### 3.3 前缀和缓存身份

每个可复用组必须由明确的装配接口提供：固定指令、完全相同的已授权证据、独立规则后缀。规则后缀保留原判断要求、输出 schema、事件白名单与时间窗。不得追加原请求看不到的材料或改变现有裁剪上限。

先验证消息内容、证据 ID/时间/类型/顺序和裁剪结果；字节相同只能证明输入稳定，Token checkpoint 与医学等价仍需现场验证。改变消息边界/位置属于版本化 Prompt 变更，不能当作纯传输改动免验。

身份绑定：租户/院区域与患者/就诊匿名归属、证据快照身份、**实际脱敏前缀内容**、证据投影与规则上下文版本、Provider/物理资源/模型及量化部署版本、Chat Template/Prompt 版本和 Gateway 启动代次。复用现有快照及匿名标识，不给普通临床 DTO 重复加 hash；必要的前缀内容摘要由一个 owner 计算。

Gateway 只短期保存有界 checkpoint 元数据（L0、身份、计时、状态），不持久化远端 KV，不跨重启恢复 L0；设置条数、TTL 和并发创建上限。日志不保留完整 Prompt、患者坐标、响应正文或凭据。

### 3.4 Prime、Cache Miss 与预算

- DSH 已验证的协议是：前缀消息单独发送、`max_tokens=1`、非流式、关闭思考，L0 只取该次 `usage.prompt_tokens`，后续才可用 `strata_prefix={"tokens": L0}`。
- **首条真实规则通常不能替代 Prime**：checkpoint 落在“病例+规则”末端，不能假定是下一条规则的共同前缀。该路线仅保留待现场证明的实验选项。
- 是否 Prime 根据该前缀组预计的**真实模型请求次数**、输入规模和预算判断，不能用选中规则数代替请求数；只一次请求、已命中结果冻结或无法证明有后续复用时不 Prime。
- 先采用可测量的保守门槛，再结合 observe 成本校准；没有数据时不承诺自动优化已生效。
- 并发请求对同一组建立 checkpoint 采用有界 single-flight；等待 Prime 的调用不能先占模型槽位。
- Prime 与规则共用本次剩余预算、资源容量与故障隔离；不增加隐式多层重试。格式/元数据失败可在预算允许时退回原冷请求。若发送后超时导致远端在途未知，遵守 Gateway quarantine，不能假定已释放后继续并发发送。
- **Cache Miss 但规则已成功：保留该次有效应答，不重新执行该规则。** 记录 miss，后续请求再按成本和预算决定重建或继续冷推理，避免示例中的 prime+重问造成重复判断。
- 缺失/冲突指标是 unknown，不能当作 miss、零成本或缓存成功；pin 请求被接受也不等于命中。

### 3.5 有界病例亲和

保留 Strata 物理资源总在途上限 **2**，只改变同一 Gateway resource 的等待请求选择，不改变病历任务并发和 CPU/数据库/保存并行。

初始测试策略：同病例优先连续派发，两个槽位可以服务同病例独立请求；存在其他病例等待时，连续派发最多 4 次，或超过 15 秒软时间片后不再继续优先，转交等待病例。Prime/内部重试同样计入派发次数。时间片不强杀已在途请求，最长等待仍受请求/规则总 deadline 限制；实际延迟还包含不可抢占的单次推理。

队列沿用 resource 明确的 max_queue，上限与等待耗时均可观测；首次不偷偷扩大容量。队列满/截止时间耗尽按现有安全错误反馈。空闲时不为等同病例下一条请求而阻塞其他病例。

不持有整例锁等待某族完成，不在持有 Provider 槽位时等待另一个准入锁，不要求已依赖的 Executor 同时就绪。取消、失租、关闭与未知在途都沿现有 lease 生命周期清理；元数据清理不能冒充远端推理已结束。

## 4. 分阶段实施与验收

### P0 固定现状与补观测

**涉及位置：** `qc_llm_client.py::_perform_observed_attempt`、`llm_observability.py`、`llm_dispatch/contracts.py`、Gateway timing。

1. 列出 11 族请求形状、材料投影、裁剪、首次/补核/重试、冻结命中和原始调用上限；使用合成材料及获授权既有安全应答，不新增患者读取。
2. 新增 Strata 指标解析测试，再实现旁路观测；默认 payload 快照与旧版相同。
3. 观测名义 prompt_tokens、cache_n、prompt_n、prompt_ms、predicted_n/predicted_ms、Gateway 排队/HTTP、客户端总耗时及 Prime 成本。分别保留来源，不通过相减伪造实读或 Decode 时间；冲突/缺失标 unknown。
4. 与现有 logical_call_id/attempt、病例匿名键、executor_key 关联；Prime 标 purpose=prime，实际请求数、Token 和耗时纳入成本，不能只统计真实规则请求。
5. 首版使用安全结构化观测输出，不直接扩业务库。若要求长期 PG 查询，单列 nullable 指标迁移并重新核对最新 head；本计划不预占迁移号。

**通过条件：** off/observe 零额外调用；Strata/非 Strata 回归通过；输出指标无正文或身份泄露，未知不报零。交付真实可复用组清单后才进入 P1/P2。

### P1 Gateway 缓存协议与状态机

**拟新增：** `app/services/strata_case_context.py`、`app/llm_gateway/case_cache.py`。
**修改：** `llm_dispatch/contracts.py`、`llm_dispatch/client.py`、`llm_gateway/providers.py`、`llm_gateway/main.py`、`llm_gateway/config.py`、`core/settings.py`。

1. 定义窄的匿名病例/证据组上下文与 prefix 描述，不允许请求端指定任意路由或凭据。
2. 在最终隐私保护后的消息上计算并校验组身份；Gateway 同时绑定服务端真实 profile/resource/model。
3. 实现 Prime/single-flight、TTL/条数上限、L0 校验、miss/unknown、重启失效与降级；所有 HTTP 经同一 lease 和预算。
4. 原始响应的 choices/临床内容不由 cache manager 生成或覆盖；额外调用成本单列并进入总成本归集。
5. 用 MockTransport 证明 cache miss 仍调用模型、Prime 失败不跳过判定、非 Strata 不转发 strata_prefix、本地配置损坏不转云。

**通过条件：** 跨患者/机构/快照/模型/template/启动代次均不可错配；取消与失败无本地槽位泄漏；未知远端在途仍隔离。

### P2 一类实际 Prompt 的最小闭环

**候选：** 检查检验族：`exam_lab_fact_extraction.py::build_exam_lab_fact_prompt`、`exam_result_record_check.py`、`exam_finding_analysis.py`；只选择 P0 证明有重复证据池的请求组，不一次性改全部文件。
**对照：** `unified_rule_engine.py::_build_batch_prompt_compact`，单独评估旧路径，不冒充 native 主链覆盖。

1. 为明确的证据组定义装配接口；主抽取与专项核验若投影不同，必须是不同组。
2. 对比旧/新输入材料集合、事件引用、正文/时间与裁剪边界；先写失败反例再适配。
3. 保留原医学约束、输出字段、补核及最大调用数；不复制原 POC 的多规则联合 schema。
4. 用固定应答经过正式解析、证据定位、Binding、Finalizer 和内存保存/读取对照状态、原因、事实与证据。
5. 若该组实际只有一次请求或必须扩大材料才能共享，保持原路并记录阻碍；不为展示缓存收益强行改语义。发现至少一个真实可复用组再讨论扩至其他族。

**通过条件：** 结构、材料和保存合同无回退；当前 mock 只证明接线，医学等价与真正 Token 命中仍列为 P5 门槛。

### P3 Gateway 有界亲和与并发恢复

**修改：** `llm_gateway/admission.py::ResourceAdmissionPool`、`GatewayRuntime.complete` 与配置；保留已有 lease/生命周期所有者。

1. 在同一有界队列上加入匿名病例键、burst/软时间片/等待顺序，off 时 FIFO 原样。
2. 用 Event/假时钟测试相同病例连续、另病例老化、单病例断流、两槽位并行及容量不超 2。
3. 测试排队满、发送前/后取消、deadline、Prime single-flight、失联隔离、shutdown 和重启；不改变任务 CAS/heartbeat/ACK/成功结果保存。
4. 以并发族依赖图跑合成固定流，证明没有持槽等锁或整例互锁。

**通过条件：** 有竞争时按约定让出优先权、无无限独占、无在队等待者阻止关闭；资源管理不分散到多个 Worker。

### P4 可重复的离线对照与质量保护

**拟新增：** `tests/unit/test_strata_case_cache.py`、`test_strata_cache_observation.py`、`test_strata_case_affinity.py`、`test_strata_prefix_fixed_flow.py`；`scripts/benchmark_strata_case_cache.py`。
**复用入口：** `scripts/run_qc_scheduler_tests.py --profile offline`，新增显式 suite，不放宽网络/数据库护栏。

1. 构造不同长度、不同病例的合成输入；对照 off/observe/prefix/prefix_affinity。
2. Mock Provider 模拟 checkpoint、缓存容量/淘汰与服务重启；报告明确标为模拟值，不写成 GPU 性能结论。
3. 保留 CT 与彩超混淆反例、非法/无支持证据、截断、JSON 无效、资料不足/不适用及技术失败不转 PASS 的保护。
4. 报告含 Prime 的全部调用数/Token/成本、命中与实读、排队/超时、每例墙钟与完成率；对照最终状态、原因、事实、证据及保存读取。
5. 运行最小相关集合后一次扩大到 Gateway、隐私、预算、任务恢复和结果保存/选轮保护，不每改小文件就跑全部检查。

**通过条件：** 固定输入/应答结果无回退，所有测试禁外网、业务库和真实模型。模拟吞吐只用于算法比较。

### P5 DSH 现场验收与回滚

这是开发交付后的客户侧门槛，本轮不执行。

1. 核对原 Strata 版本、模型/量化、32K、Batch 2、KV int8、thinking off；不改 Engine/GPU/Ubuntu，不暴露无认证 8080 到公网。
2. 先用合成探针核对 API、Token 边界与指标；不能把 reused>0 当作充分命中证据，还要核对它与预期前缀的比例。
3. 用同一批获授权病例、同一规则/材料/模型版本做四模式对照；并列记录结果冻结命中。区分冷/热执行，不能连续重复同一病例冒充不同病例吞吐。
4. 成本包含 Prime、失败与重试；按共同批次墙钟统计成功完整病例/小时，未完整或不可交付的病例不算成功。P95 使用足够样本，禁止从五例 POC 外推 SLA。
5. 逐条复核所有不合规→合规和新不适用变化，重点 CT/彩超事件与证据支持。固定应答一致不替代临床金标准。
6. 开关置 off 恢复原请求与 FIFO；对缓存丢失只冷推理，不动成功结果。切换时排空既有请求；不以删 sentinel、改 generation 或绕过 quarantine 强行恢复。

**待统一的现场标准：** 原交接表既要求“调用数不得增加”，又要求 Prime；本版保留独立判断时 N 次真实调用可变为 N+1，必须透明计入成本，不能用合并规则凑调用数。原表“miss 必须重问”和“P95 不增/最多增20%”也需统一：本计划采用不重复成功判断、正式发布不容许未解释的 P95 退化。60% 实读下降、75% 命中等可作为现场目标，不是开发机已验证承诺。

## 5. 最小交付与暂停点

先交付 P0 的真实分组清单与观测方案，然后 P1/P2 做一个可回滚的请求组闭环；P3 亲和独立开关，不能与 Prefix 一起一次性强开。每阶段独立可审查提交，保留旧路径。

开发机可证明协议、隔离、有限调度、失败与保存合同；现场才能证明实际 checkpoint 命中、净 Prefill 减少、整例吞吐和医学质量。若没有实际可复用组或成本收益为负，保留 observe/off，不能宣称完成提速。

初版计划阶段只新增本文。后续仅P0获得实施授权；其代码、隔离验证与实际限制见P0交付记录。
