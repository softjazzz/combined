# P5-B：正式LX0609 Token预算准入与检查族安全拆批

> 历史实现记录：当前收缩范围与参数口径以[2026-11-03收缩交付](2026-11-03-p5b-minimal-context-closure.md)为准。公共包装器补4096已撤回；消息形态改为显式验证。

## 本轮结论

| 项目 | 结论 | 边界 |
|---|---|---|
| 工程准入安全 | 通过本地Mock工程验收 | 正式LX0609客户端direct、Gateway和Prime逐次准入；不代表已有DSH真实计量器 |
| 检查族安全拆批 | 部分完成 | 独立检查/培养事件、06-01-04事件×病程配对可拆；不可拆单元明确技术失败 |
| 本地16K部署验收 | 未验证 | 未连接模型；没有DSH Tokenizer/模板合同与实际计量适配器 |
| 医学质量保持 | 固定应答保护通过；真实模型未验证 | 原执行器、时间、引用和保存合同保留；不能据此宣布拆批前后医学等价 |

功能默认关闭。没有推送、合并、部署、重启服务、业务库连接或模型调用。代码只在本报告所列独立工作树。


## 基线和执行计划

- 基线：远端业务集成e17ac959a61ec9586e6d72708f290483def76525（本轮只读ls-remote核实）。
- 工作树：C:\medqc-token-budget-p5b-20261102；分支codex/lx0609-token-budget-p5b-20261102；新建前无本地修改，无.codegraph。
- 本机业务集成仍a86da4f0b，分角色98a987aba未推送、未进入基线；不移植整条功能线，只依据实际客户端provider/model/profile适配。
- 本机F盘不可用，使用C盘独立目录。其他工作树不移动、不清理。
- 只使用现有统计记录、合成材料、固定应答、内存SQLite和临时冻结。禁止数据库、模型或客户机连接。

## 只读审计结论

正式入口：sichuan_workspace_batch_worker→evaluate_running_final_bundle_input→sichuan_qc_service→luxian_0609/execution→各Native族。证据快照先按规则来源取材，再由执行器构造模型请求。并非每规则重发完整病例，也不是模型自主工具取数。

| 调用点 | 输入/限制 | 恢复与最终组装 | 本轮处理 |
|---|---|---|---|
| qc_llm_client.generate/_perform_observed_attempt | 单条user消息；max_tokens是输出；隐私保护后发送 | direct safe_post_json或Gateway；length可能增加输出后重发 | 直接路径最终准入，角色/模型选择之后；无效能力拒绝 |
| llm_gateway.main._complete_uncached/_complete_prepared | Provider适配后的messages | 缓存可生成Prime及双消息规则请求；之后获取模型槽位 | 每个最终请求独立计数，排队前校验，发送前重查 |
| llm_gateway.providers.HttpxProviderSender.send | 最终Provider请求 | 独立HTTP发送，零隐藏网络重试 | 兜底准入，不把该兜底作为提前占槽的理由 |
| 检查族主抽取/native_exam_lab_execution | 按检查/培养事件及窗口；32病程、32000字符；指令/目录另算 | 协议补核、专项核验；主冻结保存验证事实 | 独立事件Token拆批；单事件需整体语义时不按任意正文切片 |
| 06-01-04/exam_result_record_check | report、course_refs、比较目录；60000字符、输出4096；原配对分批 | 客观错误定向补核/模型升级；覆盖后才完整否定 | Token二分配对，稳定事件/文书/比较上下文不丢；预算失败不能回退冻结 |
| 06-01-02、06-01-05专项 | 已有输入/输出分批 | 各自补核及事实冻结 | 统一发送准入覆盖，复杂Token拆批本轮不扩展 |
| 会诊/native_consultation_episode_execution | 意见载荷48000字符、执行候选64000字符 | 分阶段调用、补问、传输重试、意见/应答冻结 | 准入拒绝；逐建议语义依赖不在本轮重构 |
| 病程质量/native_course_quality_execution | 相关来源，单行1400/上下文18000字符，指令另算 | 事实抽取及独立语义判断 | 准入拒绝；未实现任意长文分片 |
| 扩展文书/native_extended_document_execution | 按具体文书/手术/签名等来源构造 | 局部补核，已有并发/冻结 | 准入拒绝，不改判据或候选范围 |
| 输血、肿瘤、手术及其他LX模型调用 | 由各族实际客户端发送 | 现有重试、解析、冻结 | 统一准入覆盖，不新增医学分组 |

### 历史统计口径（不追加数据库访问）

复用上轮已输出的统计：sys.llm_call_events，business_scene=luxian_0609_qc、provider_code=alibaba、model=qwen3.8-flash、status=success、usage_state=known、input_tokens>0；最近窗口started_at>=2026-10-27 00:00:00+08，至上轮已观测末尾2026-10-28 10:34:34.622371+08（含）。734次，输入>16384为69次，输入+实际输出>16384为76次。为请求尝试级用量，不是整例累计，不扣cached_tokens。

568条unknown来自上述模型/场景更大的历史总体（configuration_error64、cancelled352、transport_error131、timeout16、running5）；不能除以734，不能填零。

本轮没有这两个总体完整event_id快照，也不申请新数据库读取；精确逐请求规则/阶段与输入成因仍未知。上轮executor聚合只证明检查、会诊等族有长尾，不能由Token量猜测整包、补核或单事件过大。本地分词结果未验证。

## 最小设计与预先固定的测试边界

1. 复用既有Gateway部署Profile JSON，附加可选context_budget能力；包括模型/版本、tokenizer/版本、模板/版本、counter/版本、上下文、余量、Thinking语义和验证状态。不建第二配置中心，不增加前端。
2. 默认关闭LLM_LOCAL_TOKEN_BUDGET_ENABLED与LX0609_TOKEN_SPLIT_ENABLED。计量器采用显式注册的部署适配接口，本轮仅注入Mock；没有DSH合同/适配器时失败关闭，不用字符估算冒充真实Tokenizer。
3. 最终payload输入+与实际发送一致的输出预留+余量<=Context。cached不扣除。每次补核/升级/重试/Prime独立校验。拒绝观测与真实Provider HTTP分开，无额外数据库迁移。
4. 用既有检查事件和配对二分；有限请求数、深度、恢复及期限；保留稳定引用和比较目录。主抽取同事件没有证明安全的候选分片，不强行拆分。
5. 沿既有技术失败合同承载配置/预算异常；不能转换成临床资料不足，不清空成功结果，不完整不冻结。新策略和能力/模型身份进入冻结分区，旧数据不改写。
6. 测试边界已由用户任务确认：最终direct/Gateway/Prime发送、检查主抽取/配对归并、Native→Binding→Finalizer→Canonical及冻结。逐个关键失败用例先红后绿；严格offline runner阻断dotenv、网络、子进程和真实数据库。

## 回滚与真实验收边界

关闭检查拆批只恢复旧分批策略，保留本地Profile准入；停用未经验证Profile才是安全的部署回退。关闭准入继续向16K模型发送长请求不是安全回滚。

必须另行获得DSH真实Tokenizer/模板/输出及Thinking/特殊Token合同，验证计量误差和余量；另行授权模型原文对照。固定应答不能证明16K部署或医学等价。

## 实现与边界

### 能力与请求准入

- `app/services/llm_token_budget.py`：Profile能力、显式计量器注册、四态准入与有限恢复错误；无字符Token估算器。计量器接收完整最终payload的副本，需按指定Tokenizer及聊天模板计入特殊Token和结构化输出开销。
- `qc_llm_client.py`：复用最终payload构造；隐私保护之后、本地实际模型/角色选择之后执行准入。默认16384是输出上限，不是Context。
- `llm_gateway/main.py`：Provider适配后、槽位排队前准入；排队后发送前再次计数。Prime和规则请求各自经过该入口，缓存Token不扣Context。
- `llm_gateway/providers.py`：独立sender的最终HTTP兜底。正式LX0609没有发现绕过统一客户端直接发送模型HTTP的族内路径；首页抽取、ICD等其他产品调用不在本轮覆盖声明内。
- 严格客户端向Gateway发送`context_budget_required=true`。即使Gateway默认开关关闭，仍须按其真实Profile计量；旧Gateway会因不支持该控制字段拒绝请求。默认关闭时序列化省略该字段，既有云端请求体保持兼容。该字段不传给模型。客户端和Gateway都须安装匹配计量器，未安装的进程会拒绝，而不是相信另一进程的计数。
- 计数器未安装、能力未验证、目标身份不一致、输出预留不显式或总量超限，均不发送Provider请求、不网络重试、不转云端。输入计数未知不填零。
- 纯机械错误码集中在`llm_context_contract.py`，仅扩展技术失败原因白名单；不增加医学状态。Engine、Binding/Finalizer保留具体错误码，自动补跑将四类预算错误识别为确定性失败，不反复调度同一请求。
- 非检查族旧catch可能吞异常。族边界记录预算失败并沿现有执行器异常合同处理；相关冻结owner禁止写入失败事实。嵌套执行器也传递失败，防止变成临床资料不足/合规。其他独立族按现有执行引擎继续；没有新增任务或医学状态系统。

### 检查族

- 主抽取从完整全局投影按独立事件选择、探测和二分；保留事件映射、原窗口、比较目录及时间。不再先用32000字符预算把超大单事件归为临床材料不足。
- 主抽取没有实现同一事件多个病程的语义归并，因此同一事件仍超限时技术未完成；不能据局部输入判全窗口缺失。
- 06-01-04以配对为最小单元；新策略保留报告和病程全文，沿原稳定位置和引用拆批。必要比较目录始终保留，比较事件不增加待核任务。
- 只补核尚未成功配对，保留独立成功范围；全部必需配对覆盖后才允许完整否定。早期失败/晚期成功不制造超时；及时有效正面证据按原时间owner合同使用。
- 预算失败不采用主抽取回退制造临床结论，该规则进入技术失败；其他规则及独立成功事实保留。失败前已发送的专项用量保留。
- 请求预算在真实客户端每次HTTP尝试处扣款（含隐私包装器传输重试），不能只按外层generate次数计算。预探测沿相同隐私和temperature变换；整个检查族进入共同期限。
- 主抽取、专项与补核共享最多16个请求、8层深度、8次恢复、240秒总期限；06-01-04同时保留原8次调用上限。预规划最多32节点。取消停止后续派发，并在机械覆盖日志保留已完成/待核配对；不把取消当作临床结果。
- 新策略主抽取显式输出上限4096，并禁用客户端length加量重试；协议完整性校验及受控补核仍保留。不是通过减少引用校验或强行接受截断应答来塞入16K。
- 06-01-02/05沿用既有语义/窗口分批，仅复用总预算及拒绝语义；本轮没有完成两者所有Token二分策略。
- 新拆批与远程Prime组合暂拒绝：远程Prime尚不能共享进程内恢复计数，不能声称已受同一16请求上限保护。单独严格准入的Prime路径已用Mock验收。

### 冻结

`llm_experiment.experiment_store_dir`在现有A0/A1分区外添加Context策略/实际模型/Profile/能力版本分区。新旧策略、不同实际模型及能力不串用（含双模型路由候选Profile能力版本）；相同输入仍可热复用。不修改或删除旧文件。

新06-01-04完整比较输入进入主冻结键；比较报告内容或时间变化会失效，不仅比较目录ID变化才失效。预算拒绝、覆盖不完整、技术失败均不写完整成功冻结。

### 配置

沿用`LLM_GATEWAY_PROFILES_JSON`中现有Profile条目，增加可选`context_budget`对象，字段由`BudgetCapability`严格校验：

```json
{
  "profile": "strata_first_pass",
  "provider": "strata",
  "model": "实际部署模型名",
  "model_revision": "待DSH确认",
  "context_tokens": 16384,
  "safety_margin": 128,
  "tokenizer_id": "待DSH确认",
  "tokenizer_revision": "待DSH确认",
  "chat_template_id": "待DSH确认",
  "chat_template_revision": "待DSH确认",
  "counter_id": "待安装真实适配器",
  "counter_revision": "待DSH确认",
  "verified": false,
  "thinking_semantics": "unknown"
}
```

这是未验证配置示意，不可当作已交付的真实16K能力。`verified=true`仍不足以放行：必须安装同身份计量实现，且确认Thinking包含在输出上限内。

新增环境开关：`LLM_LOCAL_TOKEN_BUDGET_ENABLED=false`、`LX0609_TOKEN_SPLIT_ENABLED=false`；只接受true/false，错误值失败关闭。拆批需要严格准入；不新增前端配置或数据库迁移。

部分未改族仍默认预留16384输出，必然无法连同非空输入放入16K Context。这些请求会被明确拒绝，仍需后续分调用点核实输出预算或选更大Context，不能直接启用并宣称整引擎已适配16K。

### 观测

`llm_context_admission`日志包含准入状态/原因、Profile、实际模型、能力计量版本、输入、输出、Context、余量、计数耗时、阶段及可得调用归属；客户端附logical_call_id、attempt_no、role、executor和root_job_id，Gateway附request_id。无正文、凭据、接口地址或患者三坐标。

`exam_context_plan`及`exam_context_coverage`记录批次、配对覆盖、未完成位置及请求数；取消另记已完成/待核机械范围。发送前拒绝日志明确`provider_http_started=false`，客户端直接拒绝不会创建HTTP attempt。既有`total_calls`是逻辑调用计数，不能据其推算HTTP、事件或规则覆盖；实际请求须结合现有HTTP出口观测及Gateway发送结果，不能把一次准入的多层重查日志相加为请求数。没有扩展业务观测表。

## 验证记录

本轮核心用例先红后绿，包括边界准入、配对超限、长文不裁剪、嵌套吞异常和跨进程开关要求。所有后端测试通过`run_qc_scheduler_tests.py --profile offline`执行，主动阻断socket、dotenv、外部进程及非内存数据库。Mock counter只是工程夹具，不是真实Tokenizer。

- 新保护集包括总量等于上限及超1 Token、输出和Thinking、模型/模板身份、不可计数、direct拒绝不发HTTP、Gateway排队前/后、实际消息变化、Prime、控制字段默认兼容、不可拆配对、主事件映射、取消/预算、不同模型冻结，以及Mock拆批的正式保存读取。
- 正式链覆盖Native→Binding→Finalizer→Aggregator→Canonical内存SQLite；断言临床方向、规则/事件/引用、原因、展示事实与保存读取一致，并验证热冻结零调用。原有时间边界、跨事件、长文、超长/错误引文及升级失败保护集复用，不冒充新增真实病例。
- 前端完整类型检查通过；只读ESLint为0错误、3401项既有警告，未使用--fix修改源文件。没有前端改动，未运行全量前端单测。
- 两个私有报告回放入口在未显式提供原报告时跳过；不是模型或集成链路已通过。没有真实Tokenizer、真实模型、客户机、PG迁移、生产并发/服务启动验收。
- 新增CI离线suite `context-budget-p5b`及workflow入口；本轮不推送，远端CI尚未执行。

最终各套独立命令、通过及跳过数量见文末；不同suite有重复用例，数字不相加。

## 回滚和未完成范围

1. 关闭`LX0609_TOKEN_SPLIT_ENABLED`恢复旧检查分批，保留严格准入，不能靠旧截断让超限输入放行。
2. 若需恢复旧Provider调用路径，应先停用未验收的本地Profile；通过已有后台明确选择已验证Provider，不自动云端兜底。
3. 关闭Token准入后继续投递给16K部署不是安全回滚。
4. DSH须交付实际分词/聊天模板/特殊Token与Thinking预算合同、误差及余量依据，并安装计量器；单事件、单长文、完整比较目录无法装入时仍需更大Context或另行证明安全分片。
5. 分角色98a987aba不在基线，本轮不擅自并入；未来合入该功能时须复核真实目标客户端、Profile及冻结身份。
6. 本轮不提供完整病历或医学质量等价结论，不将历史云端Token当本地分词结果，不按成功请求数计算质控覆盖率。


## 最终验证命令与已知限制

工作目录均为本工作树的`apps/medqc-web/backend`，环境为Windows/Python 3.10。没有把多套结果相加为病例数量。

```powershell
python scripts/run_qc_scheduler_tests.py --profile offline --suite context-budget-p5b
python scripts/run_qc_scheduler_tests.py --profile offline --suite dual-model-exam
python scripts/run_qc_scheduler_tests.py --profile offline --suite strata-admission
python scripts/run_qc_scheduler_tests.py --profile offline --suite llm-request-audit
```

分别运行的既有保护范围曾得到dual-model-exam 254通过/2私有跳过、strata-admission 215通过、llm-request-audit 213通过。之后增加的控制码透传/重试分类由最终context-budget-p5b覆盖；这些数字不是最终全量CI结果。

扩大并集（上述suite、compatibility以及8个受装饰器影响的Native族文件）得到2487通过、2失败、2私有报告跳过。这两项不得隐去：

- `test_privacy_and_model_attribution_follow_actual_candidate`：组合导入app.main的INFO根日志使httpx打印合成地址，触发“不含地址”断言。在当前依赖环境，以Git对象e17ac959a61ec9586e6d72708f290483def76525的26个已改生产模块进行只读内存覆盖、显式重现相同app.main日志环境，仍失败；未改断言。单独dual-model-exam suite通过，不应把不同日志环境混称相同结果。本轮准入日志本身不记录地址；原httpx日志配置问题未修。
- `test_four_production_http_exits_share_one_global_peak_four`：并集出现一次峰值断言失败；当前源码单项复查和基线源码探针均通过。未确认波动根因，不能认定已修；本轮没有修改全局HTTP并发实现。复查还记录既有NumPy/SciPy版本警告，不能据警告认定失败根因。

基线探针只在测试内存中载入Git对象，不修改业务工作树或数据库。私有诊断脚本/日志在`.tmp/p5b-baseline-probe-private.*`，不提交；不是一次完整基线全仓回归。

所有改动Python文件的Ruff检查、完整前端类型检查和只读ESLint通过。映射模块原有一个未使用的纯字典局部赋值被移除以通过F841，不改变校验分支。编码检查用`node scripts/check-encoding.mjs`扫描暂存文本通过；一次npm包装启动失败后直接运行同一脚本通过。未运行全量前端单测、真实PG或真实模型验收。


最终P5-B离线入口：`python scripts/run_qc_scheduler_tests.py --profile offline --suite context-budget-p5b`，**428通过、0失败、0跳过**。包括四类预算原因经Engine/Binding/Finalizer透传、其他族成功保留及不自动补跑。两项扩大回归问题仍按上文分别保留，不把428通过写成全量CI绿。

计量扩展点目前为同步本地callback；真实适配器还须验证分词耗时上界和资源开销，未提供跨进程计量RPC或慢计量器取消验收。默认关闭且缺失DSH能力时失败关闭，不能据Mock时延承诺生产期限。


## 本地交付提交

- 实现与验收说明提交：`fa9e69e47217c0e28c3454b72a8522530b6ac5e3`。
- 实现差异：40个文件，1678行新增、106行删除（含保护测试和本报告，不是新增临床规则数）。
- 本节后的文档提交仅记录交付SHA；代码、医学合同和配置默认值不变。没有推送或远端CI结果。
