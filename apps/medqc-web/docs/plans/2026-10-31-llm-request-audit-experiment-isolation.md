# 模型请求归因与A0/A1冻结隔离实施计划

**Goal:** 在不改变Prompt、医学判定及已有成功结果的条件下，记录实际请求参数、请求来源和已知费用，阻止A0/A1误用基线或对方事实冻结。

**Architecture:** 复用统一客户端attempt边界、已有安全collector和Gateway准入。新增可选观测收据只在控制面流转，实际Provider payload保持一致；四个持久事实store通过一个严格实验namespace helper隔离路径。未配置时保持原路径与行为。

**Tech Stack:** Python3.10、ContextVar、Pydantic、HTTPX ASGI/MockTransport、现有offline测试入口和临时文件夹/内存SQLite。

基线`915e1eaf38c74a6b69e83c817a707c54454db7a2`；工作树`C:/medqc-strata-case-cache-20261030`；分支`codex/strata-case-cache-20261030`。业务集成HEAD`cedb9c10a017c30b767e7ed449b8c9b90e356a54`保持不动。

1. 子代理请求归因：新增纯白名单参数提取，复用现有匿名上下文、逻辑ID/attempt计数、collector；支持显式独立开关，保留旧Strata观测；SDK/网关校验可选实际参数收据，Provider伪造不受信。不得保存正文、推理文字、端点和密钥。
2. 子代理冻结隔离：盘点四个持久store及复用owner，新增严格A0/A1实验namespace/ContextVar。默认路径不变，显式实验路径永不读取基线；非法标签失败关闭。固定材料/应答验证首次调用、重复复用、并发、取消及异常。
3. 主代理配置和集成复核：新增`LLM_REQUEST_OBSERVATION_ENABLED=false`，文档与offline suite；核对实际Provider参数、失败/取消/重试的未知语义，以及无Prompt/医学合同变化。
4. 一次必要扩大隔离回归，编码、只读ESLint和相关Ruff；只暂存本任务文件并本地提交。测试不读dotenv、不连接外部网络或业务数据库，使用Null事件store和临时事实目录。

不实施Thinking OFF实验、输出缩减、上下文裁剪、新Prompt、真实C02执行、客户机或Strata连接、业务库/迁移、服务重启、推送或合并。固定应答只能证明隔离/观测合同，不能证明服务端实际关闭Thinking、医学准确率或性能改善。


## 实现与边界

### 请求归因

统一client的每个attempt增加安全旁路元数据：provider/model/model_role、匿名病例/包、root_job/executor、logical_call_id/attempt_no及experiment_namespace。既有已审计请求分组能识别的用途直接复用，其余标unknown，不重新解读医学Prompt。report新增按provider/executor/model_role/实验标签的成本归因，已知sum和unknown数量分别保留；逻辑调用、规则attempt、Prime attempt和实际HTTP数不是同一指标。

参数快照只取实际payload白名单：max_tokens/max_completion_tokens、顶层/模板enable_thinking、thinking.type、顶层/模板budget及显式冲突。单次覆盖参数与截断重试的新预算分别记录，不用配置默认值代替未发送字段。响应只记受控finish_reason、reasoning_content/think标签存在性及API明确上报的Reasoning/Answer Token；缺失/非法/冲突不补零、不按总输出或文字长度推导。不记录提示词、模型回答/推理文字、端点、密钥或患者坐标原文。

Gateway的可选`observe_request`控制字段只发给Gateway，永不转发给Provider；返回收据绑定当前request_id，来源为`gateway_prepared_only`。成功及prepare之后的已知400/超时/准入错误可以保留归一化参数；prepare之前失败或传输不明保持未知。Provider同名字段被剥离、坏收据丢弃，不改变既有结果/错误码、重试或临床状态。它证明Gateway已准备参数，**不证明HTTP已送达、Replica已执行或服务端Thinking关闭**。真实HTTP次数仍由传输观测证明。

Prime与Rule沿原费用合同拆开；Prime失败且Rule未发出时，不能把Prime的max_tokens=1归给Rule。当前Prime trace没有完整参数收据，Prime参数明确unknown，不冒充规则预算。Gateway状态未知隔离、总槽数2/同病例串行/连续优先、剩余时间预算不变。

### A0/A1隔离

新增纯模块`llm_experiment.py`：`current_llm_experiment_namespace()`、`llm_experiment_scope(namespace)`及`experiment_store_dir(base)`。标签只接受A0/A1或A0-/A1-开头的安全run标识，最长64字符；路径/空白/其他非法标签失败关闭。进程未配置或空值保持现有基线路径。

隔离在四个持久owner最终IO处生效：检查检验、抗菌药、会诊意见、会诊应答；validated_fact_freeze复用检查owner自动覆盖。实验路径为`<原owner>/experiments/<namespace>`，不读基线、不跨实验回退，不修改既有key或原冻结文件。显式会诊store_dir也隔离。已加载应答的FrozenResponseClient绑定namespace，跨实验使用/commit拒绝；兼容QCExecutionCache按namespace分桶，基线/A0/A1的clear互不影响。

这不修复“生产基线同Prompt更换模型/参数时自动失效”的全部历史设计，只保证本轮显式实验隔离。每个新配置/重复冷实验用新的run标识；同标签重跑会有意复用自己的冻结，因此不能把热命中当成Thinking优化收益。Gateway KV与Strata服务端前缀缓存未加实验分区；本轮A/B应保持旧Prompt与缓存关闭，不把共享服务器缓存收益归给Thinking变化。

## 配置和回滚（仅说明，未修改运行环境）

- `LLM_REQUEST_OBSERVATION_ENABLED=false`默认关闭。设true可在现有后端配置体系读取，适用于Strata、旧ollama别名与云Provider。现有Strata observe/prefix仍兼容，新开关本身不启用缓存/Prime，不改变Thinking或预算。旧日志前缀仍为strata_p0_attempt以保持兼容，provider_code说明真实Provider，不能据日志前缀认定全部是Strata。
- `LLM_EXPERIMENT_NAMESPACE`由**进程环境**读取，或由内部ContextVar作用域指定；Pydantic仅读取backend `.env`不代表会更新该环境变量。无需数据库迁移。
- 后端/SDK和Gateway需同步升级后再开启观测。旧Gateway不认识observe_request；保留关闭状态可维持原控制面请求形状。没有修改现有Provider endpoint/profile、模型或采样参数。

```powershell
# 示例只配置当前shell以后启动的独立实验进程；本轮未执行这些部署命令。
$env:LLM_EXPERIMENT_NAMESPACE = 'A0-run01'
# A1独立进程用 'A1-run01'；标签本身不负责开关Thinking。
# 回滚实验路径时清空进程变量后重启相关实验进程，保留实验文件：
$env:LLM_EXPERIMENT_NAMESPACE = ''
```

内部离线实验可用`with llm_experiment_scope("A0-run01"):`，完整请求含其产生的子任务应在同一scope完成。ContextVar支持并发与嵌套，作用域异常/取消后恢复原上下文。生产进程不要边运行边切环境标签。

回滚观测：关闭LLM_REQUEST_OBSERVATION_ENABLED并重启/重新构造相应运行实例；若需要彻底关闭旧Strata观测，再保持STRATA_CASE_CACHE_MODE=off。未改成功结果、原冻结材料或数据库，不需要回滚DDL。

## 验证安排

统一入口：`py -3.10 scripts/run_qc_scheduler_tests.py --profile offline --suite llm-request-audit`，另追加相关配置、缓存、保存、选轮、准生产及并发保护。offline护栏阻断dotenv、真实网络、业务数据库与普通子进程；传输仅用MockTransport/ASGI，事件存储为Null/合成内存库，冻结仅临时文件夹。

新增固定应答覆盖：默认off/on同payload/choices/usage/调用数；per-call预算和Thinking覆盖；Gateway归一化、坏收据与Provider伪造；400、超时、prepare拒绝、取消、length补发及底层断连重发；观测故障不重问；Reasoning未知/冲突与无敏感内容；Prime失败不污染Rule。基线/A0/A1相同材料固定不同答案各首次调用、分别热命中；四个owner、显式目录、已加载应答、兼容内存缓存、并发/嵌套/取消及非法namespace。

实际调用既有`native._extract_exam_lab_batch`的合成材料：基线/A0/A1各一次固定模型调用，随后只复用自己的事实；没有修改原Prompt或医学解析器。正式Native/Binding/Finalizer/Canonical内存保存读取由已有保护集回归，不能将其解释为真实C02医学或性能验收。

未做：现场11次HTTP逐条对账、真实Token成本排行、Thinking A0/A1模型实验、输出精简或Context修复、真实病历/27例质控、服务启动、客户机/Strata连接、业务PG写入、集成分支修改、推送或PR。本轮只让后续实验可归因、可隔离，不宣称真实提速或服务端开关生效。


## 最终证据与未执行项

最终统一42个相关测试文件：**711通过、1失败、261 warnings，37.91秒**。唯一失败是既有`test_preproduction_runner_cold_process_does_not_load_sichuan_service`调用subprocess.run，被offline的OfflineIsolationError直接阻断；没有放宽网络/子进程/数据库护栏，也没有修改或跳过该测试来制造通过。因此不声称全套绿灯或跨进程冷启动已验证。该测试文件、准生产入口/runner本轮无改动；同进程runner及API保护在通过项内。

新增请求观测20项、冻结隔离25项均在通过项内。子代理的146项、32项聚焦结果与统一回归重叠，不相加。相关17个Python文件Ruff通过。只读ESLint为0错误、3401项既有warning；本轮无前端/TypeScript变动，不运行全量前端类型检查与单测。编码/差异检查在暂存后执行。日志留本机backend/.tmp，不提交。

统一命令为以下suite加29文件（均tests/unit目录）：

```powershell
py -3.10 scripts/run_qc_scheduler_tests.py --profile offline --suite llm-request-audit <下面29文件>
```

```text
test_llm_config_loader.py
test_llm_config_permissions.py
test_qc_llm_client.py
test_qc_llm_client_thinking_budget.py
test_qc_llm_client_qwen_thinking.py
test_shared_http_client.py
test_luxian_0609_task_runtime_identity.py
test_failed_rule_retry.py
test_latest_full_record_result.py
test_luxian_0609_canonical_result_finalizer.py
test_qc_sichuan_record_result_exports.py
test_qc_worker_recovery.py
test_qc_sichuan_batch_cancel.py
test_luxian_0609_native_transfusion_freeze.py
test_luxian_0609_remaining_fact_freeze.py
test_luxian_0609_consultation_opinion_freeze.py
test_luxian_0609_preproduction_api.py
test_luxian_0609_preproduction_runner.py
test_qc_rule_orchestrator_pack.py
test_strata_case_admission.py
test_strata_package_continuation.py
test_strata_client_binding.py
test_luxian_0609_exam_result_record_check.py
test_luxian_0609_exam_finding_analysis.py
test_luxian_0609_exam_reason_check.py
test_strata_admin_configuration.py
test_qc_scheduler_isolation.py
test_llm_execution_concurrency.py
test_llm_observability_independent_egress.py
```

最终暂存19个任务文件，UTF-8无BOM/LF显式核对通过；编码脚本扫描18个文本文件通过，git diff --cached --check通过。集成HEAD及原6项未跟踪材料前后不变。工作区未启动/加载此修复，未推送或提PR。
