# M2 真实隔离验收与 Outbox 生命周期收口

基线：`e8133f91b`，分支 `codex/qc-gateway-m0-m1-20261029`。
用户授权一次性 PG/RabbitMQ、合成任务与固定应答；不连接业务库、Strata 或真实模型，
不运行现有病历、不修改集成分支。继续保持 Draft 与 legacy 默认。

## 设计选择

1. 保留当前 strict offline；新增 isolated-infra 必须有本轮 Docker owner manifest。
   驱动只新建带随机 run_id 标签的两个容器，随机 loopback 端口、随机账号/库/vhost，
   不使用宿主挂载、现有 DSN 或业务 .env。连接前再次 inspect 容器标签与端口；清理只
   处理同一 owner 的精确容器 ID。默认拒绝手填的业务地址、端口或缺失 manifest。
2. 本机 daemon 不可用，使用 GitHub 临时 Linux runner 执行真实容器验收。镜像版本
   固定，记录实际 digest/服务版本；不自动启动本机 Docker 或已有数据库。
3. 归档采用同库独立 archive 表，保留全部安全投递字段及归档时间；不删任务和结果。
   默认保留 30 天、每批最多 500；CLI 默认预览，显式 apply 才搬移。只搬移已 confirmed、
   所属 job/dispatch 均终态且无恢复标记的记录。锁序与业务写入一致；复制与移出同事务。
   archive 保留 message_id 和 job/generation/target 身份，晚重投不能另造同代投递。
4. 容量只读统计 active 行数、payload bytes、pending/claimed、最老待发布年龄和过期
   claim；结构化告警只写等级、固定 code 和计数，状态变化/恢复才输出。数据库失败为
   unknown，不能当成零。Publisher 接入监测；归档作业独立，默认不自动启用写入。
5. 新增 057，接在当前唯一 head 056 后；实际升级仅在本轮新建 PG。迁移验证以真实
   Alembic Operations 从合成 055 owner fixture 执行 056/057，不用 stamp 冒充历史升级。
   这不宣称 001–055 全历史迁移链已验收。

## 实施顺序与验收

- 生命周期：archive schema/057、归档与查询保护、容量监测/CLI，先跑内存反例。
- isolated-infra：容器驱动/manifest/网络与进程白名单，保留默认拒绝测试。
- 真实 PG：single/split 的 056/057、FK/索引、回滚、并发 claim、归档与重试竞争。
- 真实 RabbitMQ：mandatory/confirm、channel 重建、实际 ACK/重投与旧代去重。
- 独立进程：Publisher 在 Broker confirm 后、DB 标记前崩溃；Worker 在提交前和提交后
  ACK 前崩溃；取消/失租拒绝晚写、保留 Canonical 成功，不扩成 M3 任意缺项恢复。
- 固定结果沿真实 Workspace/Canonical owner 保存读取；模型调用必须为零。
- 提交前定向 Ruff/AST/编码/隔离保护；推送同一 Draft PR 后核对真实基础设施 CI。

## 不扩展

不做多 Worker/HA/quorum、病历子任务或临床规则改造；不发送外部通知，不安装客户机
服务，不启用正式 MQ，不写业务数据库，不删除原始病历或已有质控结果。
