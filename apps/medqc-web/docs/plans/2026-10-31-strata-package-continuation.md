# 病例规则包连续优先调度实施计划

**Goal:** 保留Strata总请求≤2及同病例≤1，让已有病例/包的后续模型请求有界连续优先，公平让出并支持超时取消。

**Architecture:** 现有admission继续独占物理槽/病例/队列所有权；新增纯内存连续调度策略选择最早可执行等待者。
现有规则族executor和兼容pack_id生成匿名包键，只进入Gateway控制面。短暂等待后续请求时不分配物理lease。
不改变Prompt、Executor、包大小、事件/证据/状态合同，不实现Replica Router或健康探测。

**Tech Stack:** Python3.10 asyncio、Pydantic、原Gateway、ASGI/MockTransport及offline测试入口。

基线 `d1f709c08`；工作树 `C:/medqc-strata-case-cache-20261030`，分支 `codex/strata-case-cache-20261030`。

1. 新增纯调度策略及失败测试：优先同包，再同病例下一包；连续4次/30秒额度、30秒公平等待阈值、50毫秒间隙。
   没有匿名包键时保持最早可执行FIFO；包内补核、重试和Prime仍逐次计入额度，成功应答不重问。
2. admission复用一个有界队列，受控定时唤醒优先等待；取消/超时、暂停/降容、关闭/quarantine清理优先权和定时任务。
   其他病例已可执行时最多为后续包等待短间隙，不能空占模型槽或无限等待HIS/程序工作。
3. 按现有观测上下文和包作用域生成匿名package_key；缺身份不猜Prompt，不为调度重新分包。
   Native使用既有executor边界，兼容单规则/紧凑包使用既有rule_id/pack_id。保留原参数与字节内容。
4. 固定应答端到端验证三病例、同包连续/跨包继续、公平额度/时间片/老化、暂停恢复、取消、队满及两槽限制。
   对照开关两态Provider payload/调用数/usage/临床结果/Canonical保存读取，不将旧答案当真实医学金标准。
5. 一次扩大相关队列、Gateway、冻结、配置切换及保存/任务回归；编码、只读lint、相关Ruff及旧问题对照后本地提交。

默认启用但只对携带已知包身份的Strata请求生效；可独立关闭退回上一版病例串行FIFO。
软优先可因公平性和超时中断，不保证整包原子执行或Strata物理Replica亲和。
不改集成分支、不写业务库、不连接客户机或Strata、不调用真实模型、不重跑质控、不推送或合并。


## 实施结果

- `app/llm_gateway/continuation.py`：纯选择策略；优先同包，再同病例下一包。只保存有效容量以内的近期病例（当前最多2），不新建队列、不持有HTTP lease。
- `admission.py`：复用唯一有界等待队列；每次选择同时考虑连续额度、时间片和等待老化。短间隙用可撤销定时唤醒；第二个可用逻辑槽仍可接纳其他病例。
- `strata_scheduling.py`：Native沿用既有executor作用域，兼容链沿用已有紧凑包pack_id/单规则ID；匿名包键复用现有HMAC owner。显式作用域退出后，子任务继承的失效作用域不再授权连续优先。
- `qc_llm_client.py`及dispatch合同：仅给Strata控制面增加可选`package_key`。必须同时有`case_key`，两者均为64位匿名键；不传到Provider payload、不解析Prompt猜包、不生成额外模型请求。
- 原服务实例绑定、任务配置快照、两槽总量、同病例串行、剩余deadline、远端状态未知隔离及失败传播继续由原owner负责。Native执行器、医学输入、包成员/大小、规则与事件证据ID、结果合同未修改。

## Gateway配置与回滚

仅Gateway进程读取，不需要数据库迁移，不修改后台已保存的Provider配置：

| 配置 | 默认 | 范围/语义 |
| --- | --- | --- |
| `STRATA_CASE_CONTINUATION_ENABLED` | `true` | 只认true/false；false回到上一版同病例串行FIFO |
| `STRATA_CASE_BURST_REQUESTS` | `4` | 1–64；连续准入次数，原请求、补核、重试及可选Prime逐次计入 |
| `STRATA_CASE_TURN_SECONDS` | `30` | 0.01–300秒；到期后下一次选择让出，不中断在途HTTP |
| `STRATA_CASE_FAIR_WAIT_SECONDS` | `30` | 0.01–300秒；已可执行的老等待者不再被近期病例优先越过 |
| `STRATA_CASE_IDLE_GRACE_SECONDS` | `0.05` | 0–1秒，且不大于时间片/老化阈值；留给同包后续调用，不分配物理lease |

`STRATA_CASE_MODEL_SEQUENTIAL=true`仍须保留。单独关闭连续开关不影响资源上限2及同病例串行；无包身份的旧客户端保持最早可执行FIFO。云Provider不产生包元数据，不启用这项优先策略。不改现有Prompt/前缀开关；`STRATA_CASE_CACHE_MODE=off`仍保留旧单消息路径。

这是软优先，不是整包原子调度或严格病例完成优先：一个包请求数较多或耗时较长时必须让出。30秒不是从排队到完成的硬SLA；在途HTTP、同病例前驱仍受原请求deadline约束。50毫秒也不是对空闲GPU的保留许可，网关不保证Strata实际Replica亲和。

本轮未修改部署env、未启动服务、未推送。未来部署只需同步升级Worker/backend控制面合同与Gateway、重启读取配置；若需回滚优先策略，Gateway设`STRATA_CASE_CONTINUATION_ENABLED=false`并重启。旧Gateway拒绝未知控制字段，不能先只升级发送端后继续使用旧Gateway。

## 固定应答与隔离验证

执行命令（backend目录，所有测试使用offline护栏阻断真实网络、dotenv与业务数据库）：

```powershell
py -3.10 scripts/run_qc_scheduler_tests.py --profile offline tests/unit/test_strata_package_continuation.py
py -3.10 scripts/run_qc_scheduler_tests.py --profile offline --suite strata-admission <相关兼容测试文件>
```

最终扩大保护集：**550通过，242项warning，50.09秒**。测试清单与完整命令保存于本机`.tmp/strata-continuation-final.log`及本轮执行记录，不提交日志。范围为strata-admission内13文件，加21个既有配置、观测、HTTP、Worker恢复、失败补跑、最新结果选轮、Canonical保存/导出、任务取消、并发及检查核验文件，合计34文件；不是全仓回归，也不是医学金标准验收。

新增28个调度/身份/生命周期边界用例；另在既有fixed-flow文件增加1项完整client→ASGI Gateway→MockTransport对照：3病例各3包，开关两态发送9次相同旧Prompt，两态结果、规则/事件/证据ID及Provider payload一致，最高2请求，同病例不重叠。没有Prime或新增请求。既有真实执行/Canonical内存SQLite保存读取保护集也在550项中通过，但本轮未新增真实病历验收或新Prompt医学回归。

已覆盖：同包/跨包优先、额度/时间片/老化让出、缺后续短间隙、空闲第二槽、FIFO回滚、匿名身份失效、配置失败关闭、队列满、取消（包括授予未领取窗口）、超时、关闭、远端未知隔离、0→1→2恢复、双profile共享限制、旧Prompt/缓存/执行链及保存读取兼容。

最初2项字段数断言失败，是旧测试尚未允许新增控制字段；只更新对应合同断言，未放宽Prompt、前缀预算或医学结果。新端到端夹具首次少列了原有top_p/stream/chat_template_kwargs，导致Mock断言失败并触发真实隔离保护；修正夹具后通过，没有改生产失败处理。

未执行：真实Strata/百炼调用、客户机部署、Replica健康协议、缓存命中或吞吐实测、27例或单例真实质控。不能据固定应答宣称实际提速、缓存改善或双Replica亲和。未运行全量前端单测/类型检查（无前端与TS变更，遵循最小必要检查），保留编码和ESLint检查；相关Python Ruff通过，服务大文件原有Ruff问题单独与基线比较。


最终检查：编码脚本扫描暂存区14个文本文件通过（另显式核对15个任务文件均UTF-8无BOM/LF）；只读ESLint 0错误、3401项既有warning。任务Python文件Ruff通过；`sichuan_qc_service.py`原有7项Ruff问题已按code/message与HEAD逐项比较，完全一致。最终Diff复核去掉一处无必要的应答字段清理后，再跑dispatch routing/runtime identity与fixed-flow共36项全部通过；这36项与550项有重叠，不相加。

`npm run lint`包含仓库既有`--fix`，曾产生无关前端格式化改动；已仅还原本轮该命令产生的前端改动，再用`--no-fix`核验。最终不含任何前端文件差异。业务集成线仍为`cedb9c10a017c30b767e7ed449b8c9b90e356a54`，原6项未跟踪材料未改动。
