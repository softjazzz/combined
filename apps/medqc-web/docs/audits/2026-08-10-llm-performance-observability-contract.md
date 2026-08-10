# 模型性能观测看板：调用链与计量合同审计

日期：2026-08-10

范围：`工作台 / 系统配置 / 模型性能` 设计与实施前置审计

状态：Task 0，只读合同冻结；未修改生产代码、数据库、接口或前端

## 1. 结论

当前系统已有零散的模型调用计数和 Token 字段，但**不能直接支撑模型性能看板**：

1. `GET /api/v1/system/metrics` 每次构造新的 `SichuanQCService`，读取的是新客户端的进程内计数；服务重启、多进程或新实例都会丢失历史，通常不能代表实际业务调用。
2. `SichuanQCLLMClient.call_count` 表示业务层 `generate()` 次数；思考模型因输出截断发生的第二次 HTTP 请求不会增加该值。
3. 当前客户端只累计最终成功响应的 usage；发生重试时，前一次已经消耗的 Token 会被后一次 usage 覆盖，不能据此核算真实总成本。
4. 客户质控任务的 `llm_call_count_basis=result_participation_count` 统计的是“参与模型结果的规则条数”。例如完整任务显示的 44 是 44 条非程序型规则结果，不是 44 次模型 HTTP 请求。
5. `actual_llm_pack_call_count` 在现有完整任务中为 0，但这是旧 pack 指标没有接入统一 Native 执行器，不表示实际调用为 0。
6. 当前没有持久化的单病历调用明细、输入/输出 Token、重试次数、历史响应时间或跨进程并发数据。
7. 项目存在多条模型出口。只采集 `SichuanQCLLMClient` 会漏掉首页抽取、ICD、诊疗画像、字段映射等调用，不能把局部数值命名为“全系统总调用”。

因此，正式看板必须基于模型 HTTP 尝试级的持久化事件，而不是任务结果条数、当前客户端内存计数或日志反推。

## 2. 已识别的模型出口

### 2.1 后端统一质控客户端

权威入口：`backend/app/services/qc_llm_client.py::SichuanQCLLMClient.generate`

已知消费者包括：

- LX0609 检查检验、会诊、病程、手术、输血、肿瘤病理、MDT 等 Native 执行器；
- 文书切分 `llm_document_splitter`；
- 分段质控 `segmented_qc_pipeline`；
- 编码质控 `coding_qc_service`；
- 模型配置连通性测试。

该入口已有逻辑调用数、最终响应 Token 和总 API 时间的内存计数，但没有持久化、调用上下文、重试完整 Token 或并发记录。

### 2.2 后端独立模型客户端或直连调用

以下入口绕过 `SichuanQCLLMClient`，但多数复用 `safe_post_json`：

- `frontpage_extraction_service.py::FrontPageLLMClient.generate`；
- `icd_coding_service.py::_llm_suggest`；
- `diagnosis_surgery_profiling_service.py::_call_llm`；
- `custom_qc_service.py::generate_custom_prompt`；
- `routers/proxy.py` 的模型代理；
- `routers/demo.py` 的演示规则生成；
- `qc_agent/intent_router.py` 的意图识别调用。

`field_mapper.py` 使用 OpenAI SDK 直接访问模型，同样绕过统一质控客户端和 `safe_post_json`。

### 2.3 浏览器侧模型出口

前端仍存在模型调用实现：

- `src/services/llmService.ts`：普通文本通过后端代理，但文件上传分支可直接请求配置端点；
- `src/services/llm-unified/OpenAIClient.ts`：可直接请求 `/chat/completions`；
- 若这些路径在正式页面启用，后端无法完整统计调用，也无法统一保护模型凭据。

在浏览器直连路径完成关闭或全部转入受控后端代理之前，看板必须显示“观测覆盖范围”，不得声称全系统覆盖。

## 3. 权威指标定义

### 3.1 调用层级

| 指标         | 权威定义                                                    |
| ------------ | ----------------------------------------------------------- |
| 逻辑调用数   | 业务代码发起一次模型生成意图；同一 `logical_call_id` 计一次 |
| HTTP 请求数  | 实际发送到模型提供商的请求尝试数；重试逐次累计              |
| 重试数       | `HTTP 请求数 - 逻辑调用数`，只在同一逻辑调用内计算          |
| 涉及病历数   | 具有合法病例上下文的调用，按稳定病例引用去重                |
| 单病历调用数 | 同一根任务、同一病例引用下的逻辑调用数                      |

默认 KPI “模型调用”只能展示逻辑调用数；HTTP 请求数与重试数作为明确的辅助指标，禁止混用。

### 3.2 Token

- `input_tokens`：提供商返回的 `prompt_tokens` 或 `input_tokens`；
- `output_tokens`：提供商返回的 `completion_tokens` 或 `output_tokens`；
- `total_tokens`：每次 HTTP 尝试的真实 Token 总和；
- 每次重试的 Token 均独立累计；
- 提供商未返回 usage 时记录 `usage_state=unknown`，不得写 0；
- 看板必须同时展示 Token 已知调用数与未知调用数，避免虚假低成本。

### 3.3 响应时间

- HTTP 尝试耗时：单次上游请求开始到返回或抛错；
- 逻辑调用耗时：同一 `logical_call_id` 首次尝试开始到最后一次尝试结束；
- 看板展示平均值、P50、P95、P99；
- 不能把整个质控任务耗时当作模型响应时间。

### 3.4 并发

- 并发定义为同一时间处于进行中的模型 HTTP 尝试数，不是规则数、任务数或病例数；
- 历史峰值并发由尝试的 `started_at/finished_at` 区间重叠计算；
- 当前并发来自尚未结束且未超过超时宽限的尝试；
- 超过模型超时加宽限期的 `running` 事件必须标记为 `abandoned`，不能永久占用当前并发。

### 3.5 结果状态

模型性能状态只描述调用链，不改写医疗质控状态：

- `success`；
- `timeout`；
- `transport_error`；
- `upstream_429`；
- `upstream_5xx`；
- `configuration_error`；
- `cancelled`；
- `abandoned`；
- `unclassified`。

不记录异常原文、堆栈、端点、Prompt 或模型响应。`model_invalid_output` 属于模型响应后的消费者解析结果，第一闭环不从 transport 事件推断；后续若接入，必须由对应执行器显式回写受控枚举。

## 4. 病例与业务上下文

### 4.1 病例归属

单病历统计必须由任务执行入口注入合法病例上下文：

- `root_job_id`；
- `record_key_hash`：由规范化病例身份生成的服务器端 HMAC；
- `scene`：`running/final`；
- `rule_set_key/rule_set_version`；
- `executor_key`。

事件表不保存患者姓名、病历正文、Prompt、模型输出或异常原文。前端只显示脱敏病例标识和任务 ID；需要定位病历时，由受权限保护的服务端按任务结果表解析，不能把原始三坐标复制到每条模型事件。

没有病例上下文的模型配置测试、字段映射或规则生成仍可计入总调用，但必须归入对应 `business_scene`，不得计入“涉及病历”和“平均调用/病历”。

### 4.2 业务场景枚举

第一版至少冻结：

- `medical_record_qc`；
- `frontpage_extraction`；
- `coding_qc`；
- `icd_suggestion`；
- `diagnosis_surgery_profile`；
- `field_mapping`；
- `custom_rule_generation`；
- `model_connection_test`；
- `demo_or_legacy`。

未知调用记录为 `unclassified` 并进入覆盖缺口，禁止默认为质控调用。

## 5. 持久化合同

建议新增唯一事实表：`sys.llm_call_events`。每行代表一次真实 HTTP 尝试；多个尝试通过 `logical_call_id` 归并为一次逻辑调用。

核心字段：

```text
event_id
logical_call_id
attempt_no
started_at
finished_at
business_scene
root_job_id
record_key_hash
rule_set_key
rule_set_version
executor_key
provider_code
model
model_role
status
safe_error_kind
usage_state
input_tokens
output_tokens
total_tokens
latency_ms
worker_id
created_at
```

约束：

- 唯一键：`(logical_call_id, attempt_no)`；
- schema 必须显式为 `sys`，不得依赖 `search_path`；
- Token 字段允许空值，空值代表未知；
- 调用开始创建 `running` 事件，结束后原位更新；
- 观测写入失败必须 fail-open，不能改变模型调用或医疗质控结果；
- 观测失败只输出安全计数日志，不输出事件上下文或数据库异常原文；
- 原始事件默认保留 90 天；未证明数据量前不新增第二张日汇总表或统计平台。

## 6. API 与权限合同

建议接口：

```text
GET /api/v1/system/llm-observability/overview
GET /api/v1/system/llm-observability/records
GET /api/v1/system/llm-observability/records/{record_ref}/calls
```

权限：

- 复用模型配置的角色边界：`admin/sync_admin/super_admin`；
- 演示账号即使具有兼容角色也不显示页签、不允许读取接口；
- 普通质控用户和医生返回 403；未登录返回 401；
- API 不返回 Prompt、模型响应、病历正文、密钥、端点、异常原文和原始三坐标。

时间范围、模型、提供商、业务场景、调用状态、规则集均由服务端筛选。KPI 与趋势必须使用同一完整筛选集，不能从当前页记录汇总。

## 7. 页面合同

在 `DataSyncConfigPage.vue` 的“模型配置”旁增加“模型性能”页签，继续使用 `workstation-v4` 医疗浅色工作台语言。

页面顺序：

1. 紧凑标题、观测覆盖提示、数据更新时间；
2. 时间/场景/模型/状态/规则集筛选条；
3. 模型调用、涉及病历、平均调用/病历、总 Token、P95 响应、峰值并发；
4. 调用与 Token 趋势；
5. 响应时间与并发；
6. 模型/提供商对比与安全失败分布；
7. 单病历性能列表和调用明细抽屉。

空数据时显示“自模型遥测启用日起统计”，不得回填旧任务中的规则参与数。未覆盖全部模型出口时显示“当前仅覆盖 X/Y 个受控模型出口”，不得展示“全系统总调用”。

## 8. 分阶段实施

### Task 1：质控模型调用事件 tracer bullet

只接入 `SichuanQCLLMClient` 的一次正常调用与一次重试：

- 新增 `sys.llm_call_events` 迁移；
- 新增最小事件写入服务；
- 从 `SichuanQCLLMClient.generate` 记录每次 HTTP 尝试；
- 正常调用一条事件，截断重试两条事件、同一 `logical_call_id`；
- Token 按两次尝试累加；
- 数据库不可用时模型调用行为不变。

完成后提交并暂停，不进入 API 或前端。

### Task 2：后端出口覆盖

按独立小闭环逐个接入首页抽取、ICD、诊疗画像、自定义质控、字段映射和代理路径。每个出口必须有业务场景和上下文测试。演示路径单独标记，不计入医疗业务 KPI。

### Task 3：浏览器直连收敛

验证正式页面是否仍使用前端直连。真实使用的调用必须迁移到受控后端代理；未使用路径保持隔离或停用。该闭环完成前不宣称全系统覆盖。

### Task 4：只读聚合 API

实现 overview、单病历列表和调用明细；锁定角色矩阵、分页独立汇总、Token 未知、不泄露敏感字段和重叠区间并发计算。

### Task 5：系统配置 UI

接入“模型性能”页签、KPI、三组图表、单病历列表和抽屉。没有真实趋势时使用空状态，不生成演示统计。

### Task 6：真实验收

用两份固定病历和模型配置测试逐项对账：

- 包装器实际 `generate()` 次数等于逻辑调用数；
- 上游请求次数等于事件行数；
- 重试 Token 不丢失；
- 单病历归属不串值；
- P50/P95 与原始事件计算一致；
- 峰值并发与冻结并发场景一致；
- 后端重启后历史仍存在；
- 遥测写入失败不改变质控状态、原因码、证据、LLM调用数或 Token；
- 遥测新增耗时不超过模型调用总耗时的 2%，看板常用范围查询 P95 小于 500ms。

## 9. 剩余风险与停止条件

- 生产模型出口未全部纳管前，只能展示明确覆盖范围内的统计。
- 现有历史任务不能可靠反推实际调用次数和重试 Token，不进行历史回填。
- 浏览器直连路径若仍在正式使用，既影响观测完整性，也存在凭据与审计边界问题，必须独立收敛。
- 任务结果、医疗状态和模型性能事件职责分离；观测层不得重新解释质控结论。
- Task 1 达到验收标准后必须提交并暂停，下一阶段需重新授权。
