# QC Worker M2 运维边界

日期：2026-10-30

## 当前状态

当前默认仍为 `legacy`，未部署正式 MQ。已补 057 归档迁移、容量监测及 owned disposable
基础设施验收；真实执行只发生在 GitHub 临时 runner 新建的 PG/RabbitMQ 容器内。
本机/客户机库、业务 `.env`、Strata 和真实模型均未触碰。最新状态与证据见
[M2 收口记录](../plans/2026-10-30-m2-infra-retention-plan.md)。

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

归档默认关闭，CLI 默认只读预览。默认保留 30 天、每批 500 条；显式 `--apply` 和
`--interval` 同时提供才周期搬移。只处理终态一致、已 confirmed、无恢复标记的投递；
failed 还需有失败分类。复制与移出 active 同事务，不删除 archive、任务或结果。
pending、claimed、queued/running 或带恢复标记的记录保留。057 的 archive 身份用于
晚重投去重；禁止手工删除 archive 或 downgrade 丢弃审计历史。

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

以下原始 92/251 项记录保留为前一批合成证据；其中“尚未实现/尚未验收”描述的是当时
状态，已被收口记录更新。最新真实隔离入口：

```powershell
cd apps/medqc-web/backend
python -B scripts/run_qc_m2_infra.py --output-dir .tmp/m2-infra-results
```

需已有本地 Docker daemon；驱动不启动 Docker、不接触既有容器或手填 DSN，无宿主挂载。
只连接本轮随机账号/库/vhost/端口；退出仅清理本轮标签和精确 ID。缺 verified manifest
的 isolated-infra 仍拒绝执行。默认 offline 继续禁网络、dotenv 和普通子进程。

保留期入口（目标库部署须另行授权，本轮不对业务库执行）：

```powershell
python -m app.qc_publisher.maintenance
python -m app.qc_publisher.maintenance --interval 60
# 显式允许周期搬移；前两条仍是只读
python -m app.qc_publisher.maintenance --apply --interval 3600 --retention-days 30 --batch-limit 500
```

Publisher 自动只读监测容量。环境变量：`QC_OUTBOX_WARNING_ROWS` / `QC_OUTBOX_CRITICAL_ROWS`、
`QC_OUTBOX_WARNING_BYTES` / `QC_OUTBOX_CRITICAL_BYTES`、`QC_OUTBOX_WARNING_DUE_SECONDS` /
`QC_OUTBOX_CRITICAL_DUE_SECONDS`；默认 10万/100万行、32/256 MiB payload、300/1800 秒。
仅等级变化或恢复时输出结构化日志；读失败为 unknown，不报零。不发送外部通知。
payload bytes 不是表/索引磁盘占用或 WAL；生产扫描开销与阈值需现场校准。

### 前一批合成记录（历史状态）

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
