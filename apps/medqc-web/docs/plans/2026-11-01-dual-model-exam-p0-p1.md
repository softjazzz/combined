# 06-01-04 双模型调用点 P0／P1 实施与验收

**基线：** PR22 Head `86315b7467df14aaa856fb1e0feaeca124339301`。工作树 `C:/medqc-dual-model-exam-20261101`，分支 `codex/dual-model-exam-p0-p1-20261101`。

**首轮隔离开发边界：** 只改应用层，指定检查结果记录核验调用点；原 Prompt、候选、事件／证据 ID、解析、临床映射、保存和 MQ 协议不变。不改 PR22 或集成分支，不写业务库或运行患者质控。首轮没有连接模型服务；后续用户明确授权的百炼合成POC见文末。

## 实施顺序

1. 通过单一部署配置 `LLM_EXAM_RESULT_ROUTING` 选择 off／shadow／cascade，默认空配置即 off；非 off 必须提供实验标签、候选模型／profile／部署版本和参考部署版本。任务接纳身份包含策略指纹，配置变化拒绝旧任务。
2. 增加明确的 `local_openai` 本地 OpenAI 兼容 profile，仅 Gateway 模式可用。地址／凭据归 Gateway 部署配置；独立有界资源首期最多1请求，复用现有排队、超时、取消。保持 Strata 原安全约束，不将 Strata 专用参数发送给候选服务。
3. P0 shadow 只记录拟分流与实际基线调用，不构造候选客户端、不附加候选请求；隔离实验分区首次未命中仍会按原流程调用参考，不能宣称比基线热缓存零额外成本。观测包含匿名病例、调用点、策略、覆盖数、Token、耗时、冻结命中。未知覆盖保留未知，不以 JSON 合法推断医学正确。
4. P1 cascade 在核验原请求先使用候选客户端。接纳必须通过原解析、引文与完整覆盖校验；首次协议错误／截断可升级一次，参考模型使用原始 Prompt，不使用候选答案／补核摘要。之后同一规则核验保持参考模型。服务／超时错误不伪装资料不足、不自动切云；取消直接传播。
5. 候选、升级及原补核共享既有 CallBudget（最多8次逻辑 generate）；每批仍最多2次，Gateway 传输重试沿用原预算。先 await 候选请求终止后才申请参考资源，不持有两个资源。
6. 在检查整族冻结读取之前进入路由实验作用域，覆盖主抽取、专项核验和外层存储；策略、模型部署版本、参数和原客户端身份参与分区。独立调用核验也建立同样作用域，嵌套不重复分区，其他规则调用不路由。

## 文件边界

- 新增 `backend/app/services/exam_result_model_route.py`：纯配置、请求路由会话、客户端构造、脱敏观测、实验作用域；不做医学判定。
- 修改 `exam_result_record_check.py`：现有调用循环选择客户端及有界升级；解析／apply／事件聚合保持。
- 修改 `native_exam_lab_execution.py`：只包裹整族冻结入口，不改临床算法。
- 修改 Settings、Gateway／Provider 身份与任务运行身份；不增加数据表、迁移或 UI。
- 新增固定应答保护，接入现有严格 offline suite 和 CI。

## 验收

全部测试经 `scripts/run_qc_scheduler_tests.py --profile offline`，拦截网络／DNS／业务 DB／dotenv／普通子进程。使用合成输入、Null 观测存储、临时冻结目录、真实客户端＋ASGI Gateway＋MockTransport。

覆盖 off 等价、shadow 零额外调用、候选成功、原始输入升级、引文／覆盖错误、截断、预算、取消、服务失败、无隐式云回退、单资源互斥、有界排队；覆盖整族冻结先命中、参数／部署／策略变化、并发上下文隔离；验证正式 Native→Binding→Finalizer／内存保存的规则／事件／证据及状态不丢失。

固定应答只能证明调度和合同，不能证明35B质量或真实加速；真实模型对照另行授权。没有实际成本日志时，只报告拟分流逻辑调用数，不推算病历／小时或 GPU 收益。

## 实际交付

### 配置及回滚

默认 `LLM_EXAM_RESULT_ROUTING={}`，也可显式设 `{"mode":"off"}`。关闭时不构造候选、不新增请求、不改变原冻结目录或任务运行身份形状。

以下仅为未来授权实验的配置示例，本轮没有安装或启用：

```ini
LLM_EXAM_RESULT_ROUTING={"mode":"shadow","experiment":"A1-exam-run01","candidate_profile":"local_openai_exam","candidate_model":"served-35b-model-name","candidate_revision":"weights-quant-template-v1","reference_revision":"flash-deployment-v1","candidate_parameters":{"temperature":0.0,"top_p":0.9}}
```

- `mode=shadow`：走原参考客户端，只记录拟路由及实验冻结；可以先盘点调用点，不能证明35B质量或加速。
- `mode=cascade`：在此调用点实际选择候选，要求参考是显式的 Strata Gateway。参考主抽取仍用原客户端。
- `experiment`：必须是既有合法 `A0[-run]`／`A1[-run]` 标签；改变实验运行条件应使用新标签。
- 候选 model／profile 必须与应用的 `LLM_GATEWAY_PROFILES` 以及 Gateway 注册一致。例如应用映射含 `"local_openai":{"served-35b-model-name":"local_openai_exam"}`；不会自动猜测 profile。
- 候选 `local_openai` 是明确的本地 OpenAI 兼容传输身份，不假冒 Ollama／Strata。地址、凭据和 allowed_hosts 归 Gateway 注册；独立 `local_openai` 资源首期1槽、有界队列，不能与另一Provider虚构为同一资源。
- reference／candidate revision 是部署团队提供的模型权重、量化和模板版本声明，应用不访问服务端探测它们。服务版本变化须同步声明，不声称已验证真实权重。
- candidate_parameters 首期只允许 temperature／top_p；输出上限沿原调用点及参考客户端预算。不传未知 Thinking、Strata prefix 或聊天模板扩展，因此候选服务端实际 Thinking 状态仍未知。
- 双模型实验拒绝同时启用 `STRATA_CASE_CACHE_MODE=prefix`，保持原请求消息。普通 off／observe 不更改Prompt。
- 开启／更改／关闭路由都会改变已接纳任务的运行身份；旧任务按原有身份门禁拒绝漂移，不把新配置套进旧任务或修改已有成功结果。
- 回滚只需把 mode 设回 off，按既有方式重载应用配置；实验冻结留存，基线冻结不删除。没有本次数据库迁移或数据回滚。

### 路由、失败与冻结合同

- 每批候选首次协议／引文／覆盖错误或截断，可以用同一份原始Prompt升级。升级使用原参考客户端，**不将候选应答作为参考输入**；此后该次规则核验保持参考路径。
- 同一批最多2次、整次专项仍最多8次逻辑 generate；升级和原补核共用预算。底层HTTP／Gateway重试仍由原 owner 和剩余时间预算控制，不把逻辑调用数伪装成HTTP请求数。
- 输入已触及既有报告／病程投影长度上限时，首期保守地走原参考路径，观测 `input_projection_limit`，不将该批计为安全可分流。不扩大输入、不改原Prompt或临床结论；原投影上限的医学充分性不在本次验收内。
- 传输故障／超时不触发语义升级，也不生成临床事实；取消继续传播。实际请求终止后才申请另一模型资源，未知远端状态保留原Gateway quarantine。
- 作用域在原 `_extract_exam_lab_batch` 的整族冻结读取之前建立，并覆盖专项与存储。完整策略指纹包含路由版本、模型／部署声明、参数、参考客户端配置及外层实验；Windows目录使用缩短摘要，完整指纹在任务接纳和观测中保留。
- 路由、参数、候选或参考部署版本变化不会读取旧策略分区；off、shadow、cascade 与基线互不串用。其他调用点不会被选到候选模型。

### P0观测

结构化日志 `exam_result_model_route` 沿用已有匿名病例上下文，记录调用点、策略／分区、拟选及实际模型、输入是否触及投影上限、预期／已覆盖／实际记录配对数、升级原因、逻辑调用数、响应Token和耗时、整族冻结命中。正常模型请求仍经过现有attempt／Gateway参数观测；没有新增业务库表或写入接口。

`covered_pairs` 表示协议完整覆盖的配对数；`recorded_pairs` 表示其中被判为已记录的配对数，二者不能混用。错误消息、Prompt、响应正文、端点、凭据和原始患者坐标不进入路由日志；旁路观测失败不改变结果。失败请求没有Token数据时保持未上报，不能当作没有消耗。

### 固定应答验收

- 实际客户端 → ASGI Gateway → MockTransport，覆盖候选接纳、错误引文／跨事件／错误引用、漏覆盖、JSON错误、截断升级、一次升级后保持参考、共享调用预算、超时／取消、资源释放、有界队列及无云回退。
- 整族缓存先命中反例：基线、shadow、cascade、模型／部署／参数变化分别冷读一次、同策略再热命中；并发病例作用域隔离。
- 正式 Native 主抽取仍走参考；专项按策略选择。四组固定应答实际经过 Native → Binding → Finalizer → Aggregator → Canonical内存SQLite保存读取，状态、原因、事实、规则／事件／证据和保存展示相等；实验各自热命中不再请求。
- 新suite `dual-model-exam` 已加入既有调度隔离CI必跑步骤，原网络／DB／普通进程护栏保持，没有skip或新增网络白名单。

本轮各集合存在重叠，不相加：

| 集合 | 结果 |
| --- | --- |
| 最终 `offline / dual-model-exam`（6文件） | **150通过**，9.15秒；含35项新路由保护、原补核／整族冻结／任务身份／固定保存链 |
| `offline / m1-admission` 加后台Provider／权限／Thinking预算 | **133通过**，31.56秒 |
| `offline / compatibility` | **260通过**，24.45秒 |
| `offline / llm-request-audit` 加网络及DB隔离护栏 | **238通过**，19.93秒；原受控冷启动保持 |
| 相关12个Python文件 Ruff | 通过 |
| 全src只读ESLint | 0错误，3401项既有warning；未fix |

没有前端产品代码变化，未重复跑全量前端类型／单测。没有运行全仓回归或真实基础设施；远端CI尚未执行，本轮未推送。编码、AST及最终diff在本地提交前检查。

### 首轮P0／P1验证限制（后续授权见下一节）

没有访问客户机、连接任一模型服务、调用真实模型、运行患者质控或重跑27例；只执行合成材料固定应答测试，Canonical写入仅存在于一次性内存SQLite。

没有医学金标准或两模型真实应答对照，不能据此接纳35B医学质量、服务端Thinking控制、缓存性能或实际吞吐。后台仍默认关闭；P2真实质量对照及启用另行授权。没有修改集成分支、PR22、MQ协议、前端页面、数据库迁移或正式结果合同。

## 后续授权：百炼双模型合成POC

用户明确要求“现在先用阿里云百炼的api调用这2个模型”。本次仅授权实际调用百炼两个模型，不修改正式运行配置，不发送现有患者材料。

### 显式Provider组合

- 新增可选 `candidate_provider="alibaba"`，参考和候选必须都为百炼Gateway客户端；默认仍为原 local_openai＋Strata，不把本地错误隐式回退云端。
- 百炼两个模型各有明确profile与model映射。调用点、Prompt、解析、升级次数、预算、冻结与任务身份合同沿用；路由版本升为v2，使旧实验分区不串用。
- 当前使用 `qwen3.6-35b-a3b` 和 `qwen3.8-flash`。模型名称分别核对[百炼35B文档](https://help.aliyun.com/zh/model-studio/qwen3-6-35b-a3b)、[Flash文档](https://help.aliyun.com/zh/model-studio/qwen3-8-flash)，并在真实响应中得到相同model标识。

### 独立执行入口

`backend/scripts/run_bailian_exam_poc.py` 默认只预览；必须显式 `--run-real` 才读取指定backend/.env中的百炼凭据。脚本进程清空业务DSN并阻止数据库连接，使用Null观测存储和进程内ASGI Gateway，不启动Web服务、不创建质控任务、不写业务库。

实际网络出口只允许显式百炼HTTPS文本接口与这两个model，最多12次HTTP，禁止工具／流式／Strata扩展，固定发送enable_thinking=false且输出上限4096。代理与重定向关闭；401／403后停止继续发送。记录合成答案以供复用，不记录headers、凭据或reasoning_content。

复现入口（需另有真实模型调用授权；正常隔离测试不运行此命令）：

```powershell
py -3.10 scripts/run_bailian_exam_poc.py --run-real --env-file '<现有backend/.env绝对路径>' --cases 3
```

当前执行只发送三条无患者身份的合成场景，各运行Flash参考和35B按需升级两组：

| 合成场景 | Flash | 35B路径 |
| --- | --- | --- |
| 本次报告结果的语义转述 | 已记录，符合预期 | 已记录，符合预期 |
| 只写拟完善检查 | 未记录，符合预期 | 未记录，符合预期 |
| 仅引用外院既往检查，本次待回报 | 未记录，符合预期 | 未记录，符合预期 |

真实请求共6次（每模型3次），全部HTTP200及协议ready，6/6符合合成预期，无升级或传输重试。Flash合计2000 Token，35B合计1964 Token，总计3964 Token。不能由三条合成短文推算真实病历质量、费用节省或稳定提速。

报告及可复用合成应答位于本机 `.tmp/bailian-exam-poc/bailian-exam-poc-20261101T071228Z-private.json`，不提交。请求均实际发送enable_thinking=false，但响应没有统一明确的reasoning_tokens，不能据此声称已独立证明服务端Thinking行为。

本轮真实调用未触发升级，真实服务上的升级路径仍只具备固定应答证明；真实病例医学质量、长文、多事件和完整病历吞吐尚未验收。无已有患者资料上传、业务库写入、整例质控或27例重跑。

新增百炼显式组合、本地到云端混用拒绝、预览零调用、offline不能被real标志绕过、精确出口及12次预算等隔离测试。原offline护栏不修改；`test_bailian_exam_poc.py`加入现有双模型CI套件，不会在CI调用真实API。
