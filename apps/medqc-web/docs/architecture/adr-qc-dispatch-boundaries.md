# ADR：QC 调度与模型 Gateway 边界

> 更新：本文件保留各阶段决策与当时证据。M2 后续增加了 057 archive、容量监测及
> owned disposable PG/RabbitMQ 验收，当前状态以
> [M2 收口记录](../plans/2026-10-30-m2-infra-retention-plan.md) 为准。
> 后文“isolated-infra 拒绝/归档未实现/真实基础设施未验收”是前一阶段状态，不代表
> 当前入口；默认 offline 护栏未放宽，正式 MQ 仍未启用。

- 状态：M0/M1 接受；M2 本地实现与合成验收，真实基础设施待验收
- 日期：2026-10-29（M2 增补：2026-10-30）
- 审查基线：`cedb9c10a017c30b767e7ed449b8c9b90e356a54`
- 实施分支：`codex/qc-gateway-m0-m1-20261029`
- 工作树：`C:/medqc-qc-gateway-m0-m1-20261029`
- 基线 Alembic head：`20261026_000055`

## 背景与证据边界

本 ADR 只决定 M0 离线验收和 M1 模型 Gateway seam，不表示 RabbitMQ、独立
QC Worker、Outbox、病历子任务或增量检查点已经实现。审查固定在上述 SHA；协调
阶段未找到可确认的同名远端 integration ref，ref fetch 失败，因此本文不把基线称为
“最新远端”。后续合并前必须重新核对实际集成 HEAD 与迁移 heads。

本轮没有读取新增患者材料，没有连接业务 PG、RabbitMQ、真实 Provider 或 Strata，
也没有修改业务 `.env`。

## 现有真实调用者

| 调用者 | 当前提交方式 | M1 适配范围 |
| --- | --- | --- |
| `app/routers/qc_sample_pools.py` | LX0609 样本验收创建父/叶任务后调用 `submit_detached_task(..., _run_sichuan_workspace_batch_job, job_id)` | 仅 LX0609 样本正式入口的模型传输 seam；任务提交方式不变 |
| `app/routers/qc_sichuan.py` | LX0609 运行/终末工作区创建、重启恢复、手动重试均提交 `_run_sichuan_workspace_batch_job` | 仅 LX0609 正式运行与终末入口；恢复和重试仍沿用现有 CAS |
| `app/routers/qc_sichuan.py:_run_sichuan_workspace_batch_job` | LX0609 调 `run_sichuan_workspace_batch_job`；0916 明确分支到 `run_luxian_0916_batch_job` | 0916 不适配，保留旧模式 |
| `app/routers/custom_qc.py` | FastAPI `BackgroundTasks.add_task(_run_workspace_batch_job, ...)` | 自定义规则不适配，保留旧模式 |
| 前页抽取、编码、字段映射、Agent、演示等其他 LLM 调用者 | 既有直连客户端/共享 HTTP 出口 | 不适配，保留旧模式和旧限流 |

适用范围必须写成“LX0609 样本、运行、终末正式入口”，不能简写成全站 QC 或全部
LLM 已迁移。M1 不改变任务存储、Web 进程内后台提交或应用启动恢复行为。

## 保留的权威 owner

### 调度和写入保护

- `CustomQCWorkspaceService.mark_batch_job_running` 是领取 CAS owner。LX0609 领取时把
  `_lx0609_attempt_id` 与 `_lx0609_lease_v1` 固定进任务过滤器。
- `renew_luxian_0609_batch_job_lease` 只在 job、running 状态和完整 attempt 过滤器均
  匹配时续约；批量 worker 以 30 秒心跳线程调用它。
- `_batch_job_write_scope` 是进度、完成和失败写回的 attempt/fencing 范围。取消、失租
  或旧 attempt 不能只凭 job id 覆盖新一轮。
- `is_batch_job_canceled_or_missing` 只读轻量状态与 attempt 身份，避免取消轮询加载大
  结果 JSON。
- `luxian_0609.record_result_read_model.select_latest_authoritative_record_result_job` 继续
  拥有最新权威轮次选择；完整轮次、局部补跑和已保存部分失败不得由 Gateway 重排。
- `resume_queued_luxian_0609_workspace_jobs` 与失联巡检仍是 legacy 调度恢复 owner。
  新 MQ 协议只有 M2 持久化身份完成后才可分流。

### 临床语义

规则执行器是状态、原因、事实与证据判定的唯一 owner。Binding 将执行器决定投影到
合同，Renderer 只写受控文案，Finalizer 只做合同校验/失败关闭，Canonical store 只
保存和读取已校验结果。Gateway 只做资源准入和传输，不得生成 `RuleDecision`、解释
临床失败、修改证据或把容量不足映射为资料不足。

协议补核仍归规则执行器；Gateway 只能重试有限的传输/拥塞错误；持久任务恢复属于
后续调度器。三层不得对同一个错误各自无界重试。

## 决策

### 1. M1 是 HTTP Gateway seam，不是 MQ 调度

M1 允许客户端依据冻结的 dispatch mode 在 `direct` 与 `gateway` 之间选择。Gateway
请求携带不透明请求身份、固定 profile/resource、绝对期限和原 Provider 参数；响应
保留现有解析所需字段。患者正文不会因 M1 进入 RabbitMQ；M1 根本不创建 RabbitMQ
消息。

未来消息粒度另行决定：M2 过渡期仅能投递整批 job 引用，M3 完成病历检查点与聚合
后才可投递 record task 引用。任何消息都不能携带患者姓名、正文、提示词或密钥。

### 2. Gateway 默认关闭且失败关闭

默认 `LLM_DISPATCH_MODE=direct`。只有显式选择 gateway 且 URL、服务 token、profile
完整合法时才启用；profile 缺失、别名冲突、本地端点错配、显式云角色凭据缺失或角色覆盖违规必须失败，
不得自动回退百炼。M1 代码存在不等于 Gateway 已部署或流量已切换。

未知或未注册 role 名称继续按旧兼容合同忽略，不改变主模型；已知显式 role 缺少
API key、profile 或配置格式错误时失败关闭，不静默沿用主模型或回退其他 Provider。

当前一审/二审默认模型保持 `qwen3.8-flash`。已知部署 `.env` 的思考开关为 true；
本轮不把所有调用强制改为 false。调用点已有的严格结构化输出等显式关闭仍保留，
Gateway 透传冻结参数，不做模型参数实验。

### 3. 单活动资源 owner

同一物理 Provider 实例或配额账户只映射一个 `resource_id`。模型别名、角色、一审/
二审和 URL 别名不能拆成多个预算。首期只允许一个活动 Gateway admission owner；
增加副本不能各自重新计数并声称 HA。

单活动保护的 sentinel 只在同一主机、同一显式 `state_dir` 内成立，不是跨主机锁，
不提供多机协调、自动恢复或 HA。

Strata 的容量 2 只进入配置与合成 FakeTransport 验证。未访问 Strata，未证明真实
在途上限、取消回收、吞吐或可用性，也未启用本地 profile。容量 4 必须等待部署团队
证据与独立验收。

### 4. 有界异步准入与取消语义

请求只有取得资源位置后才能创建下游 HTTP 调用。排队必须异步、有限、可取消，并
在实际发送前以绝对 deadline 重算剩余时间。排队取消保证“从未发送”；Provider 已
接受请求后的客户端取消不能等同 GPU 已停止。Gateway 重启或连接中断后若旧请求
状态未知，应保守阻塞/降容到最大执行期限或外部证据明确，不能清空内存计数后满额
放行。

初期 Gateway 网络重试次数固定为 0；旧客户端也不得在 Gateway 外层重复相同传输
重试。请求一旦已发送，若发生超时、断连或无法证明服务端已停止的取消，资源进入
quarantine，并保留 unknown-inflight sentinel；正常请求槽释放不能顺带清除
sentinel。当前不定义按超时自动清除或自动恢复容量：只有人工核实服务端工作已结束
后才能恢复。服务重启若不能恢复 sentinel，仍须保持该资源隔离，不能把未知工作当成
空闲容量。

M1 只验收单进程单活动 owner、有限队列和资源上限，不声称交互/批量混合优先级公平
调度或多机 HA 已完成。两者需要独立饥饿测试、共享状态与部署故障证据。

### 5. 现有族并发缺口与 M1 闭环

基线已有 `LUXIAN_0609_FAMILY_MAX_CONCURRENCY`、病历并发和进程 HTTP 上限，但正式
二审经运行参数复制、隐私包装进入 Engine 时，族预算缺少端到端实际重叠证据，配置
值存在不等于 Engine 真按该值执行。M1 通过显式执行上下文固定并传递策略，并须用
Event/Barrier 证明配置为 2 时实际同时启动的族不超过 2；只断言客户端属性不算验收。

此修复不提高默认单病历预算，也不取消旧直连流量的共享 HTTP 限流。任务领取后冻结
病历/族执行策略并注入隔离 runtime；任务创建时则已固定非敏感 Provider/model/思考、
dispatch 身份、规则范围和材料身份。创建到领取之间允许使用领取时有效的病历/族
预算，紧急降容不能因预算与创建时不同而触发模型身份校验失败。

`http_max_concurrency` 会被捕获为执行策略参数，但旧 direct 流量实际仍使用可由服务
热重配的进程级 global HTTP gate；M1 没有新增 task-local HTTP semaphore，因此不承诺
每任务 HTTP 硬上限在领取后不可变。迁移到 Gateway 的新流量由单活动 resource owner
管理在途容量，不再同时获取旧 direct HTTP gate，避免双重准入。管理员热更新不得
改变已固定的模型或 dispatch 语义。

## M2 明确不在本轮范围

以下均为 M2 或以后，本轮不安装、不迁移、不演练，也不声称完成：

- Transactional Outbox、RabbitMQ publisher/consumer、独立 QC Worker；
- AMQP 客户端选型与确切版本锁定；仓库已有 Celery 依赖不代表选用 Celery；
- RabbitMQ/Erlang 版本、队列类型、publisher confirm、prefetch、ACK/死信策略；
- Broker 故障、confirm 丢失、消费者 ACK 超时和进程杀死恢复演练；
- PG schema/Alembic 迁移、病历级任务、增量检查点与批次聚合。

模型 Gateway 复用仓库现有 Python 依赖版本：FastAPI 0.104.1、Uvicorn 0.24.0、
Pydantic 2.5.0、pydantic-settings 2.1.0、HTTPX 0.25.2、aiohttp 3.9.1 和
OpenAI 1.76.0。本轮只记录版本，不安装或升级依赖。最终离线验收环境实际为
HTTPX 0.28.1、Pydantic 2.13.4，未在锁定旧版独立环境再次复跑；发布前必须补齐该
版本组合验证，不能把当前结果当作旧锁定版本证据。

## 离线验证边界

`scripts/run_qc_scheduler_tests.py` 的 offline profile 在 pytest 进程内清除业务 DSN、
Provider/Gateway 配置和凭据，屏蔽 dotenv、DNS、普通 TCP/UDP socket、非 SQLite
SQLAlchemy 连接和通用子进程创建。唯一进程白名单是既有跨进程重启持久化 probe：
它固定当前 Python、已审查脚本 hash、backend cwd、系统临时目录中的 `.sqlite` 文件和
既定 mode，且必须显式传入 `--allow-reviewed-restart-probe`；默认 offline 仍完全禁止
子进程。create/create-full 只能新建并登记不存在的临时 SQLite，后续 mode 只能使用
本次 runner 已登记的同一路径。子进程重新清理环境并在脚本外层重装同一
`OfflineIsolation`；固定入口使用 Python isolated mode，并拒绝可改写 Popen 目标的
额外 kwargs；其他
`Popen`/`run`/spawn/exec/os.system 仍拒绝。唯一 socket 例外绑定到标准库 `socket.socketpair`
函数自身的调用帧，以支持 Windows asyncio；不按 localhost 地址泛化放行。

允许的替身只有合成内存 SQLite、HTTPX Mock/FakeTransport 和不启动主应用 lifespan
的 ASGITransport。只有上述显式重启 probe 可使用精确登记的临时磁盘 SQLite。该
runner 是测试进程护栏，不是操作系统沙箱；它不能替代 M2/M4
的临时 PG、RabbitMQ、独立进程和真实故障注入验收。

旧 `app.database.demo_db` 在 import 时会硬编码创建 `data/demo_feedbacks.db`。runner
在 pytest 收集前只为这一无关 legacy demo 依赖注入合成内存 engine/session seam，
不导入其生产模块、不创建 demo 表，也不替换本轮 QC workspace、Canonical 或保存
owner。其他任意磁盘 SQLite 仍由默认护栏拒绝。

runner 以显式 pytest plugin 提供兼容保护集需要的 `client` fixture。fixture 直接构造
`TestClient(create_app())`，不进入 context manager，因而不运行主应用 lifespan；真实
路由、授权依赖以及测试自身注入的保存/选轮 owner 保持不变。

`isolated-infra` 尚未实现时必须明确拒绝，不得尝试连接本机端口。

## 授权与后续门槛

当前授权仅限本地开发与离线合成测试。未授权推送、合并、部署、业务库写入、真实
模型调用、Strata 访问、RabbitMQ 安装或 `.env` 修改。后续至少需要：

1. 在最新集成 HEAD 复核调用者、迁移 heads 和未合并依赖；
2. M1 固定应答下验证状态、原因、事实、证据与旧链一致；
3. 部署前验证 Gateway 服务身份、端点 allowlist、未知在途恢复和真实 Provider 合同；
4. M2 在一次性 PG/Broker/FakeProvider 环境完成事务、confirm、ACK、fencing 和恢复矩阵；
5. 真实 Strata 容量、取消和吞吐只在另行授权后验收。

## M2 增补决定（2026-10-30）

本节在用户明确授权 M2 本地开发后增补，取代上文“`M2 明确不在本轮范围`”对当前
开发轮次的描述；上文仍保留为 M0/M1 当时的真实边界和历史记录。M2 代码存在不等于
已迁移、已部署或已通过真实 RabbitMQ/PostgreSQL 验收。

### 1. PG 状态权威与 Transactional Outbox

任务的 dispatch mode、协议版本、generation 和可恢复状态保存在任务事务内；同一
事务写 Outbox。RabbitMQ 只收到安全引用，不成为任务状态权威。事务回滚不能留下可
发布消息；Broker 离线不能导致 API 静默回退到 Web detached task 或另一份内存队列。

Outbox 记录以 `message_id` 唯一，并保留发布尝试、claim token/lease、可用时间、
confirm 和失败码。publisher 必须先用短事务 claim，释放 DB 后等待 Broker confirm，
再用原 claim token 条件回写。confirm 未知允许 lease 到期后重发；消息重复由
generation、任务 CAS 和持久状态消除重复有效执行，不能声称模型 Exactly Once。

### 2. M2 消息和日志最小化

整批过渡消息只包含 schema version、message id、job id、dispatch generation 等不透明
身份。患者姓名、院内三坐标原值、visit id、病历正文、引文、提示词、Provider 密钥、
服务 token 和完整 DSN 均不进入 body/header/dead 事件或异常文本。

无效/毒消息只记录固定 code 和安全引用。应用层不得为方便诊断把无法解析的原始 body
原样再发布到 dead queue；真实 Broker 是否配置 DLX 及其保留策略必须在后续隔离环境
单独验收。

### 3. RabbitMQ 与整批 consumer

首期要求 durable direct exchange/queue、persistent message、publisher confirms、
mandatory routing、manual ACK 和显式 `prefetch=1`。一个 consumer 一次只执行一个整批
任务，批内病历并发最多 4。该拓扑是 M2 过渡链，不是多批公平调度、HA 或病历级并行。

consumer 必须使用正式任务 CAS/租约与 generation：

- 已完成、已取消和旧 generation 消息安全 ACK，执行器调用为 0；
- 结果已提交但 ACK 失败，重投只读取持久完成状态，不重新计算；
- 持久化重试必须先提交新 generation 与 Outbox，再 ACK 当前消息；
- DB/恢复登记失败不得 ACK；活跃重复没有持久恢复线索时保留交付给 Broker 重投，禁止
  immediate requeue 忙循环；
- 取消后不发新模型请求，失租/旧代次晚结果、进度和通知均由 fencing 拒绝。

合法临床不合规或资料不足是正常结果，不 NACK、不转成技术重试。临床 executor 继续是
状态、原因、事实与证据的唯一 owner。

### 4. 恢复边界

已提交成功范围必须保留。若 Worker 崩溃时尚未形成可证明的失败/检查点范围，M2 不得
清空整批并自动重跑；安全结果是保留既有成功、把未知范围置为受控 failed，等待人工或
后续明确范围的恢复。任意病历/规则缺项恢复、独立检查点与聚合属于 M3，不能从 M2
整批链推断完成。

### 5. 入口分流与兼容

只有正式 LX0609 样本、运行和终末入口可依据持久化 mode 进入新链。新 MQ 任务只写
Outbox，不提交 Web detached task；Web 启动扫描与租约巡检只处理 legacy。0916、
自定义规则和其他后台调用继续走旧模式。现有任务与默认配置保持 legacy；没有迁移或
运行配置修改时，生产行为不应变化。

### 6. 容量与部署边界

模型 Gateway 保持单活动资源 owner；Strata 初始共享容量为 2。MQ/Worker 数量不得把
同一 Provider 预算复制为“每进程 40”；百炼 40 仍是共享且待校准的资源上限。M2 没有
授权多 Worker、多 Gateway、HA 或真实 Strata 验收。

### 7. 合成证据与发布阻断项

`m2-synthetic` 复用 offline 的 dotenv、DNS/socket、非合成内存 SQLite 和普通子进程
禁令，只为 FakeBroker/合成事务结果增加证据标签。它不开放 loopback、任意磁盘库或
aio-pika 网络连接；`isolated-infra` 继续拒绝。清单缺文件时必须硬失败。

当前 Docker daemon 不可用，主环境未安装 aio-pika；本轮不启动或安装它们。SQLite +
FakeBroker 可以验收真实 repository/outbox serialization/publisher/consumer 状态机与固定
执行器联调，但不能证明实际 PostgreSQL 锁语义、RabbitMQ confirm/ACK timeout、断线重连、
独立进程 kill 或拓扑参数兼容。发布前必须在一次性 PG/RabbitMQ vhost 补齐这些证据，
并核对当时 Alembic heads；不得使用业务库、stamp 或现有患者病历来补证。

Outbox 当前只有发布所需的 due/job 索引，不包含自动保留/归档作业或容量告警。开发期
全量保留。未来只能归档终态任务中已 confirmed 且无恢复标记的历史投递；pending、
claimed、当前 queued/running 或仍有恢复标记的记录不得清理。该策略与作业实现是部署
门槛，本轮不执行删除，也不据现有索引宣称生命周期治理完成。

本地最终合成验收为 `m2-release: 92 passed, 3 warnings in 6.90s`；兼容集合加 M0/M1
显式保护文件为 `251 passed, 72 warnings in 17.14s`。两组分别报告，不相加。迁移 head
静态核对唯一为 `20261030_000056`，但未执行迁移；真实 PG/RabbitMQ、独立进程故障和
本轮跨进程 restart 仍未验收。
