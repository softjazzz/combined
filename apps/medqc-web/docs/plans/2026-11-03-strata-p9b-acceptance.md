# Strata P9-B兼容：实现、隔离验收与交付限制

日期：2026-11-03。状态：应用层实现完成，等待DSH真实合同后再做端到端集成；未打包、推送或部署。

## 固定基线与范围

- 来源：`codex/business-agent-integration`，`d063761e544b4bb6d95892c9802f2edf84f47203`（已含PR29/P5-B与PR30）。
- 独立工作树：`C:\medqc-strata-p9b-20261103`。
- 独立分支：`codex/strata-p9b-compat-20261103`。本轮未改集成工作树及其6项未跟踪材料。
- 不改医学Prompt、候选材料、事件ID、时限、Executor判据或业务结果合同；前端源码和迁移无改动。
- 后续用户明确要求：真实计量及身份材料交付前，只完成Mock实现，不生成未经验证的正式测试包。本轮没有构建包、启动服务、读取患者材料、连接业务库/模型/客户机或运行病历质控。

## 已实施

| 边界 | 实现与行为 |
| --- | --- |
| 最终Strata请求 | `strata_protocol.prepare_request`固定temperature=0、top_k=1、top_p=1、presence_penalty=0、frequency_penalty=0、repetition_penalty=1；只发送nested `chat_template_kwargs.enable_thinking=false`，移除Thinking预算和其他思考开关。原Prompt及输出预算不变。 |
| Direct/Gateway | 正式client及Gateway共用协议；白名单仅为Strata增加top_k/repetition_penalty，非法字段/数值拒绝。Direct与Gateway均用真实HTTP封装＋MockTransport检查最终payload。 |
| 身份 | 复用部署Profile登记目录，新增可选`model_identity`合同。缺失、不可信、模型/版本/端点不匹配即拒绝；收到HTTP200还必须精确匹配响应model。不能以服务端回显证明权重身份。 |
| 最终预算 | Strata无论全局P5-B开关是否开启，都必须通过既有精确计量准入；开关默认值及其他Provider行为不变。无计量器、模板或消息形态未经验证、预算不足均不发HTTP。Gateway排队前及真正发送前复核；缓存Prime与后续消息也按最终形态计量。 |
| 输出预算 | 保留既有明确上限。Strata配置不足以提供调用点要求时拒绝，不以min缩小必要输出；非法/超硬上限配置拒绝，不沿用原“扩大Thinking预算”启发式。其他Provider保留旧处理。 |
| Context/length | Context已知错误码和finish=length映射到既有技术失败通道，不增大预算、截输入或原样反复重发，不让失败回退为确定临床结论。 |
| 502受控恢复 | 仅固定错误码structured_output_failed、且原请求有response_format时，最多一次移除服务端格式约束后补问。原文、模型、证据、输出上限与下游严格解析不变；每次仍受计量/超时/取消/请求预算约束。第二次失败终止；没有format可移除时不重发。 |
| 隐藏重试 | Strata Direct关闭底层“无响应断线再发一次”，Gateway原本也不内部重试。BaiLian保留既有连接池断线重试。恢复和失败尝试由现有观测记录，不隐式切云端。 |
| 冻结 | P9-B协议、有效Greedy/Thinking、Profile模型/计量身份和身份合同进入原冻结隔离；旧协议、不同模型/模板/证明不能串用。终止性错误阻止冻结，成功恢复不被首个可恢复错误污染。保留同族已成功结果。 |
| Windows存储 | 保留完整隔离摘要，冻结owner使用Windows扩展路径读写，避免嵌套隔离目录超过260字符而使已成功执行崩溃；不删除/覆盖旧冻结。 |
| draft探针 | `strata_probe.run_fixed_probe`只发固定虚构探针，仍走正式客户端和全部准入；业务`draft_n=0`只是观测。探针可显式要求非零活动，缺字段/格式异常不冒充验证通过；它不会自动在业务调用中执行。 |

## DSH必须交付的能力

已知模型ID `qwen3.6-35b-a3b`、Context16384、隧道18084均来自用户；当前不是本机真实验证结论。

1. `/v1/models`、`/health`、`/props`脱敏原始响应及其身份对应关系；不猜结构或新API。
2. 模型权重/Tokenizer/聊天模板的版本和可获取哈希、最终Provider合同（含P5-A2），以及文件路径。
3. Windows可执行计量组件、依赖、安装位置、调用接口和支持的完整消息形态。
4. 20/20计量测试向量及期望输入Token；单User通过不能授权多消息Prime。
5. `timings.draft_n`实际语义。正式业务监控不以单次0否定临床结果。

### 应用侧对接接口（不是对DSH现有JSON结构的猜测）

- `LLM_GATEWAY_PROFILES_JSON`继续登记受控model、profile、api_endpoint及原`context_budget`。
- 新`model_identity`由`StrataModelIdentity`校验：model、model_revision、endpoint_sha256、evidence_sha256、verified（默认false）。evidence_sha256是经人工核对的DSH身份交付文件哈希，不能凭HTTP200填写已验证；endpoint_sha256使用`endpoint_identity()`对部署基址归一化后计算。
- `BudgetCapability`沿用P5-B全部模型/计量器/聊天模板身份及`verified_message_shapes`；默认verified=false、thinking_semantics=unknown，不修改默认值来通过准入。
- DSH真实组件必须通过`llm_token_budget.register_counter(counter_id, counter_revision, CounterIdentity(...), count_payload)`注册；回调接收最终payload，返回实际输入Token整数。函数名、组件加载方式及依赖待交付后适配，本轮没有可用于生产的Tokenizer实现。
- 当前新增`model_identity`只是应用接口，尚未与DSH真实Provider JSON完成字段映射。测试中的合成revision/hash/verified仅位于tests，不可用于部署。

## 隔离验证

所有后端测试经`run_qc_scheduler_tests.py --profile offline`：剥离凭据/连接环境、禁止dotenv/socket/非白名单子进程、仅允许合成内存SQLite。未放宽隔离工具。

先添加回归，复现缺参数、输出预算缩小和身份缺失等问题，再实现协议及失败通道。旧Strata夹具补齐显式合成身份/计量合同；新拒绝测试不通过Mock授权绕过准入。旧“允许Thinking或隐藏重试”断言改为本轮明确要求，同时保留原文与成功事实断言。

```powershell
Set-Location C:\medqc-strata-p9b-20261103\apps\medqc-web\backend
python -B scripts/run_qc_scheduler_tests.py --profile offline --suite strata-p9b
python -B scripts/run_qc_scheduler_tests.py --profile offline --suite context-budget-p5b
python -B scripts/run_qc_scheduler_tests.py --profile offline --suite strata-admission tests/unit/test_strata_p9b.py tests/unit/test_shared_http_client.py
python -B scripts/run_qc_scheduler_tests.py --profile offline --suite llm-request-audit
python -B scripts/run_qc_scheduler_tests.py --profile offline --suite dual-model-exam
```

最终去重联合回归：**981通过、2跳过、0失败**，43.87秒。集合为上述五组加`test_shared_http_client.py`，按文件去重；不是981份病历。P9-B独立集合198通过，P5-B集合458通过，重复结果不相加。

2项跳过是需要显式提供私有原报告的已有应答回放（`test_exam_poc_acceptance.py`、`test_exam_hard_poc.py`）；本轮未读取患者目录或复制这些产物。公开可重建固定应答与完整结果链均已执行。

静态检查：全部改动Python的Ruff通过，完整前端类型检查通过，只读ESLint为0错误/3403既有警告，编码和`git diff --check`通过。未跑全部前端单测（无前端源码变更），也未声称全后端回归。去重联合命令：

```python
# 在backend目录通过 python -B 执行；仍由原Runner建立完整offline隔离。
from scripts.run_qc_scheduler_tests import SUITES, main
names = ('strata-p9b', 'context-budget-p5b', 'strata-admission', 'llm-request-audit', 'dual-model-exam')
requested = [p for name in names for p in SUITES[name]] + ['tests/unit/test_shared_http_client.py']
full = {p for p in requested if '::' not in p}
selected = list(dict.fromkeys(p for p in requested if '::' not in p or p.split('::', 1)[0] not in full))
raise SystemExit(main(['--profile', 'offline', *selected]))
```

验证包含同族两项成功＋一项技术失败的Engine/Binding/Finalizer/Canonical内存保存读取；技术失败不保存为临床合规/资料不足，已成功结果身份/原因不丢失。另包含原及时证据保护、双事件保存和成功冻结分区。

## 启用、回滚及限制

- 不新增自动连接或启用本地模型的开关；默认Provider不改变。原后台本地模型选择仍要求Gateway。低层Direct只保留既有受控调用能力，两条路径同受P9-B保护。
- 选择Strata却缺少可信身份、已注册真实计量器或足够Context时，当前实现会明确拒绝；不能关闭全局P5-B开关来绕过此保护。
- 当前16K不能承载“必要输出上限16384＋任何正输入”。原未显式降预算的调用点仍可能不兼容；本轮没有批量改输出上限，也没有宣称全引擎16K可运行。检查族继续复用既有、需显式开启的P5-B安全拆批，不能安全拆的调用仍为技术未完成。
- 无迁移新增，既有基线迁移为062；本轮没有执行迁移。未来DSH包应先使用虚构材料和内存/独立测试存储，不覆盖客户机正式目录或连接正式业务库。
- 回滚是停用本轮隔离代码或切回原版本；业务模型切换使用既有人工配置流程，不提供模型失败自动转云端。回滚不是关闭安全检查后强行请求本地模型。
- 未执行真实Token计量、真实模型身份验证、draft/MTP服务端验收、医学准确性回归、Strata完整业务链冒烟、Windows发布构建或客户部署。Mock证明应用处理和保存合同，不证明模型质量、服务端实际Thinking行为或吞吐。
