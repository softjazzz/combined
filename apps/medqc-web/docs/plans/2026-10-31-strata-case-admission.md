# Strata旧Prompt下的病例准入实施计划

**Goal:** 修复旧客户端绑定，在单一Strata资源上保证总请求≤2、每病例≤1，公平有界排队，降容仅以Mock验证。

**Architecture:** 复用Gateway admission/lease/lifecycle；匿名病例键通过控制元数据传递，不进入Provider payload。
最早可执行的等待者优先，跳过当前仍在途的同病例，不设置病例亲和优先级。
容量调节只提供内部方法，不新增现场健康接口；取消、超时、quarantine和任务结果语义沿用原owner。

**Tech Stack:** Python3.10、asyncio、Pydantic、httpx ASGI/MockTransport、现有offline runner。

基线 `6d255786d`，工作树 `C:/medqc-strata-case-cache-20261030`，独立分支 `codex/strata-case-cache-20261030`。

1. 用固定客户端复现UnifiedRuleEngine捕获旧generate；改为服务级动态委派，验证重载和独立任务runtime不串改。
2. admission增加病例键、有效容量及最早可执行FIFO选择。队列总数仍受max_queue约束；取消/超时归还病例与物理槽。
3. Gateway只对Strata启用病例串行。缺身份的旧请求归到共同保守通道，不能通过缺元数据突破串行；云端保持既有FIFO。
   多个Strata profile必须共享同一物理resource和同一API端点，防止配置拆池把2槽放大成4槽。
4. 正式Worker复用现有病例HMAC；服务的有坐标入口在无外层上下文时补匿名身份，保留已有任务上下文并拒绝冲突身份。
   Prime同样受病例/总槽位限制。case_prefix仍默认关闭，原Prompt、输出schema和医学Executor不变。
5. 新增内部set_capacity用于2→1→0→2的Mock验证，不中断在途请求、不解除quarantine、不提供管理HTTP入口。
6. 离线验证至少三病例、同病例跨角色/调用方、队首阻塞、超时取消、队列满、降容恢复、Provider错误和旧Prompt完整性。
   扩大相关Gateway、客户端、配置切换、冻结、保存读取和任务恢复测试；提交前只读静态检查及编码检查。

不改集成分支、不写业务数据库、不连接客户机/Strata、不调用真实模型、不重跑质控、不推送或合并。
本轮只保证模型HTTP调用串行，不声称整规则包连续执行或Replica病例亲和，也不实现三消息、Batch或医学规则包扩大。

## 实现与验收

- UnifiedRuleEngine现在绑定服务的动态委派方法，后续调用使用该服务当前客户端。
  独立任务runtime同时复制已接纳的一审/二审配置，避免构造过程中重新读取环境导致二审模型或profile漂移。
- Gateway请求增加可选 `case_key`（现有三坐标HMAC），不进入Provider payload。
  Worker沿用既有病例观测身份；独立服务入口有完整坐标时补齐身份，保留任务及执行器上下文，冲突身份拒绝执行。
  缺少身份的旧Strata请求共用保守串行通道，不能把随机请求ID当病例身份绕过限制。
- admission原子管理物理槽和病例占用，不增加先拿物理槽再等病例锁的双层阻塞。
  同病例所有角色、Prime和规则请求共用病例限制。最早可执行FIFO跳过仍在途的同病例队首，云端保持旧FIFO。
- 保留每资源 `max_inflight/max_queue` 配置；所有Strata profile必须指向同一resource和同一模型API端点。
  不新增重复的 `STRATA_MAX_INFLIGHT`，不增加第二Endpoint或Replica Router。
- 内部 `GatewayRuntime.set_resource_capacity(resource_id, capacity)` 支持从配置上限收紧至0。
  已授予lease继续计入在途并完成；降容后不新增超出有效容量的lease。暂停不延长原截止时间，等待过期沿用原失败语义。
  该方法不解除关闭或未知远端隔离；本轮没有上游健康轮询或管理HTTP入口。
- 资源快照新增 `effective_max_inflight/active_cases`，只统计Gateway自身准入状态，不表示Replica存活数。
  内部降容时既有Gateway `/health` 返回degraded；这不是两个Replica健康的证明。
- 修复Python3.10 `wait_for`在完成/取消同刻的吞取消边界，取消与超时均归还等待项、病例和槽位。
  已开始的Provider HTTP请求仍由原lifecycle持槽到实际终止，不能因调用方取消提前放行同病例下一请求。

## 配置、部署及回滚

Gateway进程新增 `STRATA_CASE_MODEL_SEQUENTIAL=true`（默认）。置false后回到原有请求FIFO，资源2槽上限仍保留。
只更新示例配置，未修改运行env或重启服务。部署时需同步更新Gateway与Worker/后端；旧Gateway会拒绝新控制字段，不能自动去掉身份重发。
所有Worker共用同一Gateway容量owner和一致的病例HMAC密钥配置；分别启动多个独立限流Gateway不能形成全局2槽。

Strata资源示例条目（加入现有 `LLM_GATEWAY_RESOURCES_JSON`）：

```json
{"strata_gpu":{"capacity_class":"strata","max_inflight":2,"max_queue":32}}
```

32为有界排队配置示例，不是性能验收值。原默认max_queue=4保持兼容；正式部署须结合病例/族并发和请求截止时间设定队列容量。
超过队列容量明确返回原有429，超时/取消/失败交由原任务owner处理，不生成合规结论；已有成功结果不因准入层而清除。
HIS取数、确定性规则、Binding/Finalizer和保存层不持有模型lease。
回滚先排空在途，再重启Gateway应用开关；保留原Prompt、成功结果及quarantine/sentinel，不能靠删隔离状态恢复资源。
Strata直接调用兼容路径仍存在；本次跨Worker容量保证依赖统一Gateway部署，后台Strata配置入口已经要求Gateway。

## 实际验证

- offline统一扩大集合 **519 passed、242 warnings、31.67秒**；命令为
  `py -3.10 scripts/run_qc_scheduler_tests.py --profile offline --suite strata-admission` 并追加下列既有保护文件。
- 之后增加的两项运行级Mock保护单独验证 **2 passed**：降容排空/暂停/恢复保留三个固定应答；调用方取消后同病例仍等待原Provider真正完成。
  不将分批数字叠加成新的统一运行数量。
- 覆盖SDK→Gateway进程内ASGI→固定Sender，至少三病例、同病例跨任务/角色、匿名身份不透传、资源2槽、零队列、队满、取消获准同刻、未知远端隔离及云端兼容。
- 既有检查结果核验、阳性分析、检查原因及正式Binding/Finalizer/内存SQLite保存读取的固定应答保护通过。
  状态、原因、事件/证据关系继续由原执行器和保存合同负责，没有真实模型医学回归或现场吞吐测试。

追加保护文件均在 `tests/unit/`：
`test_llm_config_loader.py`、`test_llm_config_permissions.py`、`test_llm_observability.py`、
`test_strata_observation.py`、`test_strata_observation_client.py`、`test_qc_llm_client.py`、
`test_qc_llm_client_thinking_budget.py`、`test_qc_llm_client_qwen_thinking.py`、`test_shared_http_client.py`、
`test_qc_worker_recovery.py`、`test_failed_rule_retry.py`、`test_latest_full_record_result.py`、
`test_luxian_0609_canonical_result_finalizer.py`、`test_qc_sichuan_record_result_exports.py`、
`test_qc_sichuan_batch_cancel.py`、`test_luxian_0609_task_runtime_identity.py`、
`test_qc_scheduler_execution_policy.py`、`test_llm_execution_concurrency.py`、
`test_luxian_0609_exam_result_record_check.py`、`test_luxian_0609_exam_finding_analysis.py`、`test_luxian_0609_exam_reason_check.py`。

所有测试使用严格offline护栏，禁止dotenv、真实网络/业务库和普通子进程；仅固定应答和合成内存数据。
修改/新增Python文件Ruff通过；大服务文件的7项Ruff问题与HEAD按规则/消息逐项相同，无新增问题。
编码检查17个文本文件通过，额外UTF-8无BOM/LF及Python3.10 AST检查覆盖18个暂存文件（含env示例）。
全量只读ESLint为0错误、3401警告，未清理无关警告。
本轮没有前端源码或类型变动；未重跑前端类型检查/全量单测，也未运行真实模型、客户机、Strata、部署/迁移/业务质控。
