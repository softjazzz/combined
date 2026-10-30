# QC Worker M2 运维边界

日期：2026-10-30

## 当前状态

这是 M2 代码评审与后续隔离环境验收入口，不是已部署声明。当前默认配置仍为
`legacy`；未执行迁移、未安装 RabbitMQ/aio-pika、未启动 publisher/Worker、未修改
`.env`，也没有连接真实 PG、Broker、Provider 或 Strata。

## 受支持的首期拓扑

- 一个 Web/API 进程组只负责接纳并在同一事务写任务与 Outbox；
- 一个 Outbox publisher 角色负责短事务 claim、等待 confirm 和回写发布状态；
- 一个整批 QC consumer，`prefetch=1`，批内病历并发最多 4；
- 一个单节点持久 `classic` 队列；它不提供节点级 HA；
- 一个活动 LLM Gateway 作为全部已迁移角色的资源 owner；Strata 容量 2；
- PG 是状态权威，RabbitMQ 只传安全引用，Broker 不保存病历正文或提示词。

不得横向启动多个各自带 40 个 Provider 位置的 Worker/Gateway。首期整批 consumer 不是
HA 或公平调度方案；多进程/病历子任务属于后续独立设计。

MQ 首期只接单个 LX0609 叶任务；`family_parent` 在创建 parent 前受控拒绝，不能通过
手工改 filters 绕过。0916、自定义规则和旧任务继续 legacy。

## 启用前门槛

1. 在一次性 PG/RabbitMQ 环境通过 M2 真实基础设施矩阵；
2. 基于实际 integration HEAD 分配并执行增量 Alembic revision，核对 heads/schema；
3. 安装并锁定 `requirements-qc-worker.txt` 中的 Worker 专用依赖，验证 Python 与
   RabbitMQ/Erlang 组合；Web 基础依赖不因可选 Worker 传输被隐式升级；
4. 为测试/生产分别创建显式 vhost、最小权限账号、持久 exchange/queue/dead queue；
5. 验证 Gateway 单活动 sentinel、服务身份、端点 allowlist 和 unknown-inflight 恢复；
6. 明确选择新任务 `dispatch_mode`，保持旧任务 `legacy`，禁止自动双投递；
7. 配置 Outbox 容量告警，并评审保留期与可审计归档/清理作业；
8. 备份业务 PG 并验证可读。没有以上证据时保持新模式关闭。

M2 开发期 Outbox 全量保留，不自动删除。部署前的清理/归档只能选择终态任务中已
`confirmed`、没有恢复标记的历史投递；`pending`、`claimed`、当前 queued/running 或
仍带恢复标记的记录一律保留。当前只提供 due/job 查询索引，保留期作业和容量告警尚未
实现，本轮也没有执行任何清理或业务库动作。

## 启停顺序

启动建议顺序：PG/迁移就绪 → RabbitMQ/vhost 就绪 → Gateway 就绪 → publisher →
单 consumer → Web 开放新模式接纳。停止时先禁止新模式接纳，再停 consumer 新领取，
等待当前代次提交或进入受控失败，然后停 publisher/Gateway/Broker。

本轮没有实际执行这些操作；现场命令、服务账号和数据目录必须在部署授权后按目标
Windows/Linux 环境补齐，不能从开发机路径照抄。

## 故障处置

### Broker 不可用

API 已提交的任务保持“待发布”；Outbox 不丢弃，不降级为 Web 内存线程执行。恢复
Broker 后由 publisher 重新 claim。若发布结果未知，等待 claim lease 后重试，依赖
consumer generation/CAS 去重，不能手工把记录标成 confirmed。

### consumer/ACK 异常

结果已提交而 ACK 失败时，让 Broker 重投；consumer 读取完成状态后直接 ACK，禁止
重算。DB/恢复登记未提交时不得 ACK。活跃重复投递没有持久恢复登记时保持未确认并
关闭当前 channel，由 Broker 后续重投，禁止 immediate requeue 忙循环。

### 取消、失租与崩溃

取消后不再开始新的模型调用；旧代次晚结果由 fencing 拒绝。已提交成功范围保留。
M2 无法证明崩溃缺失范围时，标记安全失败并走受控恢复；不得清空整批结果后自动重跑。
如果已有成功项但失败范围未知，必须人工核定恢复范围；M3 检查点未实现前不能自动把
“未见成功”解释为“可以重跑”。

### 毒消息与 dead 事件

日志只写固定 code、message_id/job_id 等安全引用，不写消息 body、患者标识、提示词、
密钥、完整 DSN 或异常连接串。无法解析的原始 body 不由应用层原样发布到 dead queue；
人工诊断使用安全摘要和 PG 权威状态。

## 回滚

回滚先关闭新任务接纳和新 consumer，不删除 Outbox/调度身份/成功结果，也不把 MQ 任务
重新交给 legacy 扫描器。旧任务继续按其持久化模式恢复。若旧版本无法识别新模式，
显示受控不可执行并保留数据，等待修复版本；禁止删除记录或修改 generation 逃过门禁。

## 验收入口

离线合成入口：

```powershell
cd apps/medqc-web/backend
python -B scripts/run_qc_scheduler_tests.py --profile m2-synthetic --suite m2-release
```

该命令不连接真实 Broker/PG。后续真实基础设施入口在 `isolated-infra` 实现并获授权前
必须保持拒绝；不得临时删除 socket/DSN 护栏来完成现场验收。

2026-10-30 本地最终结果：`m2-release` 为 `92 passed, 3 warnings in 6.90s`；
`compatibility` 加 M0/M1 显式保护文件为 `251 passed, 72 warnings in 17.14s`。两者分别
报告，不相加。真实 PG/RabbitMQ、独立进程 kill/reconnect、ACK timeout、迁移执行和
本轮跨进程 restart 均未验收；自动 Outbox 归档也未实现。
