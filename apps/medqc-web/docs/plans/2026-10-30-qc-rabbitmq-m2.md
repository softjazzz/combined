# QC RabbitMQ M2 本地开发与验收说明

日期：2026-10-30

## 结论与证据等级

本轮在 `20e789287` 基线上实现 Task 5/6 的本地 M2 过渡链：持久化调度身份、
Transactional Outbox、RabbitMQ 传输适配器、Outbox publisher、整批独立 Worker
消费状态机，以及正式 LX0609 入口的持久化分流。现有任务默认保持 `legacy`；0916、
自定义规则和其他后台任务不迁移。

本轮验收只允许合成内存 SQLite、真实 Outbox 序列化/publisher/consumer owner、
FakeBroker delivery 和注入固定执行器。它证明进程内合同与状态转换，不证明真实
PostgreSQL、RabbitMQ、独立进程、ACK 超时或 Broker 重连恢复。

当前机器的 `docker.exe` 存在，但 Docker daemon named pipe 不可用；主 Python 环境
未安装 `aio-pika`。本轮没有启动/安装 Docker、RabbitMQ、服务或依赖，没有连接本机
PG/RabbitMQ 端口。真实隔离基础设施验收记为**未执行**，不能把 FakeBroker 或
SQLite 结果换写成真实 Broker/PG 通过。

## M2 范围

### 本轮包含

- 同一事务持久化任务调度身份和 Outbox；回滚后没有可发布消息；
- 消息只含 schema/message/job/generation 等不透明引用，不含姓名、病历正文、提示词、
  Provider 密钥或完整连接串；
- publisher confirm、不可路由、离线、确认未知和有界重试的状态转换；
- durable topology、persistent message、mandatory publish、manual ACK、`prefetch=1`；
- 首期队列类型固定为单节点 `classic`；它提供持久化，不提供节点级 HA；
- 一个消费者一次执行一个整批任务，批内病历并发最多 4；
- generation、任务 CAS/租约、结果提交、取消和 ACK 的先后保护；
- LX0609 样本、运行、终末正式入口按持久化 `dispatch_mode` 分流，新 MQ 任务不再提交
  Web detached task，legacy 仍走原路径；
- MQ `family_parent` 创建在写入 parent 前受控拒绝；本轮只接单个 LX0609 叶任务；
- 固定应答跨模块链与安全错误/日志边界。

### 本轮不包含

- 不执行 Alembic 迁移，不写业务 PG，不修改业务 `.env`；
- 不安装或启动真实 Broker，不做独立进程 kill/重启，不部署 Windows/Linux 服务；
- 不调用真实模型或 Strata，不重跑现有病历；
- 不实现 M3 病历子任务、规则级检查点、跨 Worker 聚合或 Exactly Once；
- Outbox 已有 due/job 查询索引，但自动归档、保留期、容量告警和清理作业尚未实现；
- 不改变现有任务默认模式，不自动回退成内存双执行；
- 不推送、合并、打包或部署。

## 关键合同

### 权威 owner

PG 任务/调度身份/Outbox 是可恢复状态的权威来源，RabbitMQ 只传引用。规则执行器仍是
临床状态、原因、事实和证据的唯一 owner；Worker/consumer/Gateway 不重判临床结论。
Canonical 保存和最新轮次选择继续由既有 owner 负责。

### 至少一次与 ACK

- 发布成功但 confirm 丢失允许重发；`message_id` 不能替代业务 generation/CAS。
- 结果事务提交后 ACK 失败，重投只读取持久状态并 ACK，不再次调用执行器。
- 重试 generation 必须先与新 Outbox 一起持久化，再 ACK 当前消息。
- DB 提交或恢复登记失败时不得 ACK 成功。
- 活跃重复投递先保留可恢复线索；不能立即 requeue 忙循环，也不能把领取失败当完成。
- 旧 generation、已完成和已取消消息安全结束，不执行模型。
- 无效/毒消息只记录固定错误码；不记录消息正文，也不把原文复制到应用层 dead 事件。

### 取消、失联与成功范围

取消后不再发起新模型调用；失租或旧 generation 的晚结果、进度和通知均被 fencing
拒绝。已提交成功范围保留；若 Worker 崩溃时尚未形成可证明的失败/检查点范围，M2
不能自动清空整批重跑，只能保留安全 `failed` 状态并进入受控恢复。M2 不声称可以像
M3 一样只恢复任意缺失规则或病历。已有成功项但失败范围未知时必须人工收口，不能
假设“剩余全部”就是安全补跑范围。

### 容量

M2 过渡期只运行一个整批 consumer，RabbitMQ `prefetch=1`，批内病历并发最多 4。
模型 Gateway 仍是单活动资源 owner；Strata 初始容量只允许 2。不得通过增加 Worker
进程让每个进程各自获得 40 个 MQ/Provider 位置；百炼 40 是单一共享资源预算且仍待
部署校准。

## 离线 runner

从 `apps/medqc-web/backend` 运行：

```powershell
python -B scripts/run_qc_scheduler_tests.py --profile offline --suite m0-isolation
python -B scripts/run_qc_scheduler_tests.py --profile m2-synthetic --suite m2-outbox
python -B scripts/run_qc_scheduler_tests.py --profile m2-synthetic --suite m2-transport
python -B scripts/run_qc_scheduler_tests.py --profile m2-synthetic --suite m2-worker
python -B scripts/run_qc_scheduler_tests.py --profile m2-synthetic --suite m2-entrypoints
python -B scripts/run_qc_scheduler_tests.py --profile m2-synthetic --suite m2-release
```

`m2-synthetic` 只是证据标签：它复用与 `offline` 相同的 dotenv、DNS/socket、非合成
内存 SQLite 和普通子进程禁令，并额外标记本次结果来自 FakeBroker/合成事务。它不
开放 loopback、不允许任意磁盘 SQLite、不允许启动 aio-pika 连接。只有 M2 显式 suite
可选该 profile；清单缺任何文件时收集前硬失败，不以 skip 凑绿。

`isolated-infra` 当前继续明确拒绝。既有 `compatibility-restart` 的固定脚本 hash、当前
Python、backend cwd、登记临时 SQLite 和显式 flag 例外保持原样，M2 不扩大该例外。

## 合成验收矩阵

| 场景 | 本轮必须观察到的结果 | 证据限制 |
| --- | --- | --- |
| 任务事务回滚 | 无 Outbox/消息 | 合成 SQLAlchemy 事务 |
| MQ 离线 | Outbox 保持待发布/可重试 | FakeBroker，不是断真实 Broker |
| confirm 丢失 | 可重发；只一个有效执行 generation | Fake confirm 故障 |
| 不同 generation | 旧消息 ACK，执行器调用 0 | 真实 consumer 状态机 |
| 结果提交后 ACK 失败 | 重投不重算 | FakeDelivery ACK 故障 |
| 持久重试 | 新 generation/Outbox 先提交，再 ACK | 真实 repository + consumer |
| DB 提交失败 | 不 ACK | 合成事务故障注入 |
| live 重复 | 先有持久恢复登记才 ACK，否则保留重投线索 | 真实 consumer 状态机 |
| 失联 | 保留成功范围；未知范围转安全 failed/受控恢复 | 不宣称 M3 任意缺项恢复 |
| 取消/晚结果 | 不再发模型；旧代次写回被 fenced | 固定执行器调用计数 |
| dead/poison | 只含安全引用/错误码，不记录或原样转存正文 | 日志捕获与消息检查 |

本轮跨模块固定流实际经过 repository → Outbox serialization → publisher → FakeBroker
delivery → BatchConsumer → 正式纯程序固定结果 → Workspace `mark_batch_job_running` /
`complete_batch_job` → Canonical 读取。它没有从 HTTP 开始：当前 HTTP 合成测试使用
FakeWorkspace 验证鉴权/配置/分流，若接到固定流会 mock 掉核心任务事务，不能据此声称
纵向联调。后续只有在 HTTP 可注入同一真实合成 workspace owner 时，才补 HTTP 起点。

## 验证记录

- 主协调最终统一 M2 集：

  ```powershell
  python -B scripts/run_qc_scheduler_tests.py --profile m2-synthetic --suite m2-release
  ```

  结果：`92 passed, 3 warnings in 6.90s`。该集合已包含 Outbox、transport/publisher、
  Worker/recovery、entrypoints 和 4 项跨模块固定流；不得再把各 owner 的定向数字或
  `4 passed` 相加。

- 主协调最终兼容集在 `compatibility` 上显式追加 M0 isolation 与 M1 六个文件：

  ```powershell
  $qcM2CompatibilityExtraTests = @(
    "tests/unit/test_qc_scheduler_isolation.py"
    "tests/unit/test_llm_gateway_admission.py"
    "tests/unit/test_llm_gateway_cancellation.py"
    "tests/unit/test_llm_gateway_api.py"
    "tests/unit/test_qc_scheduler_execution_policy.py"
    "tests/unit/test_llm_dispatch_routing.py"
    "tests/unit/test_llm_dispatch_runtime_identity.py"
  )
  python -B scripts/run_qc_scheduler_tests.py --profile offline --suite compatibility @qcM2CompatibilityExtraTests
  ```

  结果：`251 passed, 72 warnings in 17.14s`。与 `m2-release` 分别报告，不合并成一个
  “总通过数”。

- 早期 runner 保护定向运行 `20 passed`，固定流定向运行 `4 passed, 1 warning`，均已
  被上述最终集合覆盖，只作为开发过程记录，不重复计数。
- 37 个变更文件中 33 个 Python 文件通过 Python 3.10 AST、UTF-8 无 BOM 与 LF 检查；
  `git diff --check` 通过。迁移 head 静态核对唯一为 `20261030_000056`，但没有执行迁移。
- Ruff：除 `app/main.py` 67 条 E402 外其余 32 个 Python 文件零问题；这 67 条的 code、
  message、行列与 `20e789287` 基线逐条一致，本轮没有新增 Ruff 问题。
- 单独旧节点
  `tests/unit/test_qc_sichuan_batch_throughput.py::test_create_workspace_batch_job_freezes_full_visit_filter_scope`
  曾观察到夹具缺 `LUXIAN_0609_RULE_DECISION_007_ENABLED`；它未纳入上述最终集合，且
  本轮没有在 `20e789287` 同条件复现以证明基线归属，因此只记为既有夹具/开关口径待
  单独核实，不改旧预期凑绿，也不宣称全仓通过。
- 真实隔离 PG/RabbitMQ：未执行（daemon/依赖/授权条件不满足）。
- 真实模型/Strata：未执行且不在本轮授权范围。
- `compatibility-restart` 跨进程受控重启集本轮未重跑；M0/M1 的 2026-10-29 记录不能
  冒充 M2 独立 Worker/Broker 跨进程证据。
- integration HEAD、当前分支和起点已有的 6 个无关 untracked 文件未改变；本轮未
  fetch/merge/push。

最终数字按实际命令分别报告；`m2-release` 已包含各子 suite，不再把子 suite 通过数与
release 相加。继承失败、未安装依赖和未运行真实基础设施如上单列。

## 后续发布门槛

1. 在一次性 PostgreSQL 执行实际增量迁移并核对当时 Alembic heads，不使用 stamp；
2. 在一次性 RabbitMQ vhost 验证真实 confirm/mandatory/unroutable、ACK 超时、断线重连、
   channel 重建和单节点 classic 队列参数一致性；如需节点 HA，须另行设计/验收 quorum
   或集群方案，不能把本轮 classic 队列称为 HA；
3. 用独立 Web/publisher/Worker 进程复现事务、confirm、ACK、fencing 和进程 kill 矩阵；
4. 复跑旧结果读取、取消、失败补跑、最新完整轮次、Canonical 与权限保护；
5. 只有上述证据通过后，才可讨论显式开启新任务模式。M3 仍需独立评审，不能由 M2
   整批过渡链推断病历级分布式恢复已经完成；
6. 部署前确定 Outbox 保留期、容量告警和可审计归档/清理作业。只允许处理终态任务中
   已 confirmed、无恢复标记的历史投递；`pending`、`claimed`、当前 queued/running 或
   仍有恢复标记的记录不得清理。本轮没有执行任何删除或归档。
