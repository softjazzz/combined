# 原始 LX0609 批量任务重试入口归属修复

## 问题与边界

通用 `/api/v1/custom-qc/workspace/batch-jobs/{id}/retry` 原先可将正式 LX0609 任务重新入队，并调度通用 Worker。该 Worker 将任务标记为运行中后，尝试读取不存在的四川规则库伪草稿；正式任务的无代次失败写入被拒绝，任务可能停留在运行中。本次只修改通用入口的接纳边界，不改变正式 Worker、医学判据、0916 任务或 40 槽位并发。

正式 LX0609 的权威身份是任务筛选中的 `rule_set_key=luxian_0609_qc_v1`。`draft_id=sichuan-rule-library` 且缺少 `rule_set_key` 的记录属于规则集身份缺口，也不得交给通用 Worker 猜测执行。其余有明确不同规则集身份的任务维持原有入口行为。

## 修复

- 通用重试入口先读取归属，再进行写入。正式 LX0609 或身份缺口任务返回 HTTP 409，不修改原任务，也不安排后台执行。
- 通用 Worker 在领取前进行相同检查，防止旧后台队列或直接调度绕过路由。
- 正式 LX0609 仍由 `/api/v1/qc/sichuan/workspace/batch-jobs/{id}/retry` 接纳和调度。

这两处检查属于通用任务入口和 Worker 自身的完整接纳职责，留在既有路由模块，没有新建转发层。没有改存储、结果或规则合同。入口读后到重试写入间未新建独立事务锁；正式任务的 `rule_set_key` 在现有同 ID 重试中保持不变，因此本次按既有持久化身份判定。

## 验证

`test_custom_qc_wrong_batch_owner.py` 使用隔离 SQLite 和真实 `CustomQCWorkspaceService`。覆盖正式任务处于取消、完成、排队时通用入口均无写入/无后台提交；旧通用 Worker 不领取；伪草稿缺少规则集身份时受控拒绝；普通草稿与其他规则集保留既有接纳；正式入口仍重新入队并提交专用 Worker。

此测试直接调用路由函数并使用 Starlette `BackgroundTasks` 检查提交，没有启动 HTTP 鉴权服务，也没有执行真实模型或客户数据库。正式链的完整执行与 Canonical 持久化由独立阶段测试验收，不能用本报告替代。
