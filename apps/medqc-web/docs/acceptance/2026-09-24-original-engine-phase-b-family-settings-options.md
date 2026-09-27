# 原始 LX0609 阶段 B：规则族子任务执行配置边界方案比较

本文基于只读审计，不修改生产代码。先前固定探针 `00c165bd9` 已证明：同一客户样本父任务的两个子任务，在先后启动时分别读取 Settings；医学门禁开关变化会传到实际 `prepare`，而关闭目标 Native 族时会在正式计划处安全失败。该探针没有证明真实病例结论漂移。

## 现有权威链与可复用载体

| 内容 | 当前所有者、位置与行为 |
| --- | --- |
| 任务接纳/范围 | `qc_sample_pools.py:984–1525` 读取规则集，组装 `job_filters`，包含 `rule_set_key/version`、选择的规则、`task_frozen_date`、逐病例 `record_evaluation_snapshot`、运行参数；`execution_scope_hash` 用于近期同范围去重。 |
| 父子复制 | `qc_sample_pools.py:1525–1636` 在同一次路由调用中从 `job_filters` 派生父任务与每个规则族子任务的 `child_filters`。 |
| 持久化 | `CustomQCWorkspaceService.create_batch_job`（`custom_qc_workspace_service.py:2736–2840`）把筛选条件作为 JSON 文本写入 `custom_qc_batch_jobs.filters_json`（Text 列）；`_row_to_batch_job` 从同一列读取 `filters`。布尔值和小型字符串字典可以使用现有序列化能力，不需要新表或全量 Settings。 |
| 运行设置 | `sichuan_workspace_batch_worker.py:1328–1361` 每个 Worker 独立 `get_settings()`，再解析主链开关、核查正式 Native 包；`running_final_bundle_service.py:80–119` 接收 Worker 传来的 `task_settings`，并将其用于包计划；`execution.py:225–282,882–943` 用同一对象选择 Typed Decision、证据快照和触发门禁。 |
| 规则版本 | `rule_set_version` 在 Worker 中用作进度、观测和摘要标签（约 1313、1709、3116、3584 行）；未看到它与运行时目录/代码版本比较。`runtime_build.json` 已有受控 `build_id/git_commit` 读取器，但开发/未打包环境可返回 unavailable；该声明也不是防篡改证明。 |

### 应比较的最小医学执行字段

下列名称都来自 `Settings`（`settings.py:133–188`），只保存其**有效布尔值**，不是环境文件原文；先调用 `resolve_mainline_rule_decision_settings`，再取值，避免把基础值与实际 overlay 混淆。

1. **正式路径/发布门禁（3）：** `MAINLINE_RULE_DECISION_ENABLED`、`CUSTOMER_AGGREGATION_ENABLED`、`UNIFIED_ENGINE_ENABLED`，均加 `LUXIAN_0609_` 前缀。它们影响是否准入正式主链、是否建立统一执行信封和结果发布路径（`rule_decision_settings.py:202–266`；Worker 1328–1355；`execution.py:194,264`）。
2. **Native 包选择（12）：** `NATIVE_EXECUTION_ENABLED`、`NATIVE_MDT_040_ENABLED`、`NATIVE_EXTENDED_DOCUMENT_ENABLED`、`NATIVE_BASIC_TIMELINESS_ENABLED`、`NATIVE_CONSULTATION_ENABLED`、`CONSULTATION_EXECUTION_LINK_ENABLED`、`NATIVE_EXAM_LAB_ENABLED`、`NATIVE_TRANSFUSION_ENABLED`、`NATIVE_TUMOR_PATHOLOGY_ENABLED`、`NATIVE_COURSE_QUALITY_ENABLED`、`NATIVE_SURGERY_GATE_ENABLED`、`NATIVE_SURGERY_DOCUMENT_ENABLED`。`native_package.py:421–483` 按这些值构建执行包；关掉目标族通常由正式 Native-only 门禁拒绝，而非静默降级。
3. **Typed Decision 发布范围（13）：** `RULE_DECISION_007_ENABLED`、`RULE_DECISION_COURSE_SEVERITY_ENABLED`、`RULE_DECISION_BASIC_TIMELINESS_ENABLED`、`RULE_DECISION_TRANSFUSION_ENABLED`、`RULE_DECISION_CONSULTATION_ENABLED`、`RULE_DECISION_COURSE_COPY_ENABLED`、`RULE_DECISION_COURSE_ADMISSION_ENABLED`、`RULE_DECISION_TUMOR_PATHOLOGY_ENABLED`、`RULE_DECISION_MDT_040_ENABLED`、`RULE_DECISION_SURGERY_TIMELINESS_ENABLED`、`RULE_DECISION_SURGERY_GATE_REMAINING_ENABLED`、`RULE_DECISION_EXAM_LAB_ENABLED`、`RULE_DECISION_SURGERY_DOCUMENT_ENABLED`。`rule_decision_settings.py:11–103` 有逐规则映射；`execution.py:272` 据此选择 Typed Decision 范围。并非每个标志都影响每个子族，但保持同父任务的有效发布路径一致需要在任务级比较。
4. **触发/证据选择（3）：** `TRIGGER_GATE_ENABLED`、`LLM_TRIGGER_GATE_ENABLED`、`EVIDENCE_SNAPSHOT_SIDECAR_ENABLED`。前两项用于 `execution.py:882–896` 的门禁路径，后一项在 `execution.py:280–294` 决定统一证据快照入口；即使本轮两个原生规则没有观测到结论差异，也不能按“资源开关”排除。

以上共 **31 个布尔字段**。`EVIDENCE_FORMATTER_ENABLED` 在 `execution.py:943,1054` 影响客户可见证据组织，不直接选医学判据；若目标包括同任务展示一致性，可作为第 32 个单独的**交付格式**字段比较，不能混称临床判据。

不纳入医学配置比较：`FAMILY_MAX_CONCURRENCY`、`QC_BATCH_RECORD_MAX_CONCURRENCY`、`LLM_HTTP_MAX_CONCURRENCY`、任务的 `max_parallel_records`（资源/预算）；`RUNTIME_SHADOW_ENABLED`、`059_SHADOW_ENABLED`、`025_SHADOW_ENABLED`（不发布的影子观察）；`PREPRODUCTION_API_ENABLED`（入口授权）；JWT、数据库、LLM API Key/Endpoint、完整 `Settings` 对象（凭据/环境）。模型与采样参数另有 `job_filters.model_code/temperature/top_p/max_tokens`，但 Worker 侧没有直接读取这些四项的代码命中；实际 `SichuanQCService` 可能由默认服务配置初始化。因此本报告**不能宣称模型身份已冻结**，模型配置是独立的同任务一致性审计项，不能用这 31 个布尔值替代。

## 两个最小方案

| 方案 | 读取/写入与旧任务策略 | 优点 | 风险与回滚 |
| --- | --- | --- | --- |
| A．创建时冻结、所有子任务沿用 | 路由创建时读取并解析一次有效 31 项，作为版本化小字典写入现有 `job_filters`，父子复制；Worker 以当前 Settings 为基础，用已有 `ReadOnlySettingsOverlay` 仅覆盖这 31 项，然后将对象传到已有 Worker→bundle→prepare 路径。旧任务缺字典须明确拒绝或标为 legacy，不得悄悄用当前设置假装冻结。规则代码版本仍需独立核对。 | 同一父任务的布尔医学配置一致，可执行跨启动回放；不冻结并发预算。 | 运营人员紧急关闭不安全的 Native/门禁开关后，旧任务仍按冻结的 true 执行，可能抵触止损意图；代码升级后旧布尔组合在新代码上语义未必相同。必须给紧急停用优先级和版本不一致的拒绝策略，否则不建议直接上线。 |
| B．创建时记录、运行前比对，不一致拒绝 | 路由同样只记录有效 31 项小字典；每个 Worker 在领取后、构建计划前再解析当前值并逐字段比对，差异则受控失败，不运行模型、不发布本子任务结果。`filters_json` 的父子复制仍是唯一快照 owner。旧分组任务无字典时，按保守策略拒绝并提示重新发起；未分组历史任务可保持原路径，须明确界定。 | 尊重运行时紧急关闭；最小化临床误混用风险和实现改动；配置漂移显性可排查。 | 若首子任务完成后才改设置，剩余子任务会失败，父任务会成为混合“已完成/失败”状态，不能承诺原任务继续完成；旧排队任务需重发。要在客户任务详情明确“执行配置变化”而非伪装资料不足。 |

两方案均需让现有 `execution_scope_hash` 的输入包含这份小字典；否则两分钟内同病例同规则、但医学配置不同的新请求可能被旧 queued/running 任务去重。这里复用既有范围身份机制，不另建普通 DTO 哈希。重试同一父任务应保持原字典；如果要应用新医学配置，应新建任务而非在同 ID 重试中静默换代。

**当前倾向先选 B。** 它与现有“正式 Native 不可用即失败关闭”的原则一致，不会在紧急回滚后强行继续旧冻结配置。先只限定客户样本 LX0609 分组任务；病历池、0916、普通自定义任务均不隐式改变。上线前要决定：正式包版本升级时，用现有 `runtime_build.git_commit`（可用时）还是明确规则目录发布版本来确认代码同代次；当前 `rule_set_version=2026-06-09` 的字符串本身不足以证明实现同代。

## 最小验收及剩余决策

1. 同一父任务两子族，创建时有效布尔配置相同；调度间只改 `FAMILY_MAX_CONCURRENCY` 或全局 HTTP 槽位，第二子任务仍接纳并按当前预算运行。
2. 改动 `TRIGGER_GATE_ENABLED` 或某族 Native/Typed Decision 开关：A 应让两个子任务实际 prepare 收到同一冻结有效值；B 应让第二子任务在模型/Canonical 写入前拒绝，原因明确为配置漂移，首子任务已发布结果不被覆盖。
3. 创建后改基础开关且触发 `ReadOnlySettingsOverlay`：比较的是**解析后有效值**，不能把同效的不同基础配置误判为漂移；也不能漏掉会诊族关停产生的联动覆盖。
4. 缺失/篡改/字段类型错误快照、旧排队任务、同 ID 重试、父子任务去重、部署版本变化分别固定受控行为。历史只读结果继续可看；新任务不自动继承旧布尔字典。
5. 使用同一份病例与固定模型响应比较状态、原因码、事实、证据、调用量；真实客户病历验收在独立后续任务做。本阶段探针只证明配置读取边界，不证明实际准确率回退。

正式选择前尚需确定三个产品口径：紧急停用是否覆盖已排队任务；发布升级时旧任务是失败重建还是允许同版本回放；客户是否允许任务出现“部分规则族已完成、其余因配置漂移失败”的状态。答案会决定 B 的提示和重试入口，不应先引入通用冻结框架。
