# 质控队列管理机制 PRD v1.0

> v1.0 | 2026-03-14 | 面向 PG + Mongo + LLM 质控链路

---

## 1. 背景与目标

### 1.1 背景

当前质控链路存在两类资源瓶颈：

1. 数据库侧：高并发任务写入与统计查询会放大 PostgreSQL I/O。
2. 模型侧：算力紧张时，LLM 推理并发容易积压并触发超时重试风暴。

现状缺少统一的排队、限流、重试、死信和可观测机制，导致瓶颈在 PG 与 LLM 间来回转移。

### 1.2 目标

建立统一队列机制，实现以下目标：

1. 对 PG 与 LLM 双端削峰填谷，避免“爆仓”。
2. 支持任务状态机、幂等、重试退避、死信与人工重放。
3. 支持优先级调度与多租户公平性。
4. 提供完整监控告警与容量治理能力。

### 1.3 非目标

1. 本期不做跨地域多活。
2. 本期不替换现有全部业务表，只新增队列控制层。

---

## 2. 总体方案

### 2.1 分阶段策略

采用“两阶段”实施，控制风险：

1. Phase A（立即落地）：PostgreSQL 队列表 + Worker（`FOR UPDATE SKIP LOCKED`）。
2. Phase B（按需升级）：迁移到独立 MQ（RabbitMQ/Kafka），状态机与业务接口不变。

### 2.2 架构分层

```
API层
  -> 编排层（任务拆分/合并）
    -> 队列层（qc_job_queue / qc_job_items）
      -> 执行层（dispatcher + llm workers）
        -> 结果层（qc_results / qc_defects / remediation）
```

### 2.3 双队列模型

1. `qc_job_queue`：质控主任务队列（病历批次级）。
2. `qc_job_items`：LLM 子任务队列（单病历或单文书级）。

主任务负责流程与聚合，子任务负责并发执行与重试隔离。

---

## 3. 状态机设计

### 3.1 主任务状态机（`qc_job_queue.status`）

`created -> queued -> dispatching -> running -> succeeded`

异常路径：

1. `running -> failed -> retrying -> queued`
2. `failed(超重试上限) -> dead_letter`
3. `queued/running -> cancelled`
4. `running -> partial_succeeded`（部分成功，允许补偿重跑）

### 3.2 子任务状态机（`qc_job_items.status`）

`queued -> claimed -> running -> succeeded`

异常路径：

1. `running -> failed -> retrying -> queued`
2. `failed(超重试上限) -> dead_letter`
3. `queued/claimed/running -> cancelled`

### 3.3 状态转换约束

1. 不允许跨级跳转（如 `queued -> succeeded`）。
2. 仅 Worker 可将 `claimed/running` 写入终态。
3. 取消后不可自动恢复，需显式重放。

---

## 4. 数据模型（Phase A）

### 4.1 `qc_job_queue`（主任务）

关键字段：

1. `id` UUID PK
2. `job_type`（`task_qc` / `manual_qc` / `recheck`）
3. `priority`（0=最高，9=最低）
4. `status`
5. `source_task_id`（关联 `qc_tasks.id`）
6. `payload`（JSON，任务参数）
7. `idempotency_key`（唯一）
8. `retry_count` / `max_retries`
9. `next_run_at`
10. `claimed_by` / `claimed_at`
11. `error_code` / `error_message`
12. `created_at` / `updated_at` / `finished_at`

索引：

1. `(status, priority, next_run_at, created_at)`
2. `idempotency_key UNIQUE`
3. `(source_task_id, status)`

### 4.2 `qc_job_items`（子任务）

关键字段：

1. `id` UUID PK
2. `job_id` FK -> `qc_job_queue.id`
3. `record_id`
4. `document_type`
5. `model_provider` / `model_name`
6. `status`
7. `priority`
8. `attempt` / `max_attempts`
9. `next_run_at`
10. `timeout_seconds`
11. `payload` / `result`（JSON）
12. `error_code` / `error_message`
13. `claimed_by` / `claimed_at`
14. `created_at` / `updated_at` / `finished_at`

索引：

1. `(status, priority, next_run_at, created_at)`
2. `(job_id, status)`
3. `(record_id, status)`

### 4.3 `qc_job_events`（审计事件，建议）

记录状态流转、重试、取消、死信、人工重放操作，便于审计与追踪。

### 4.4 `qc_dead_letter`（死信表，建议）

超重试上限或不可恢复错误任务沉淀区，支持人工筛选重放。

---

## 5. 调度与限流机制

### 5.1 Claim 策略

使用事务 + 行级锁：

```sql
SELECT id
FROM qc_job_items
WHERE status = 'queued'
  AND next_run_at <= NOW()
ORDER BY priority ASC, created_at ASC
FOR UPDATE SKIP LOCKED
LIMIT :batch_size;
```

### 5.2 并发上限

1. 全局并发：`MAX_WORKERS`
2. 每模型并发：`MAX_CONCURRENCY_PER_MODEL`
3. 每租户并发：`MAX_CONCURRENCY_PER_TENANT`

### 5.3 速率控制

1. LLM 调用：按 provider/model 做 QPS/TPM 限制。
2. PG 写入：批量写 + flush 周期控制（例如 200 条/批）。

### 5.4 反压策略

触发条件（任一命中）：

1. 队列积压长度超过阈值。
2. 平均等待时长超过阈值。
3. LLM 超时率/错误率超过阈值。

动作：

1. 暂停低优先级任务入队。
2. 降低每模型并发。
3. 前端返回“排队中”状态，不再同步执行。

---

## 6. 重试、超时与幂等

### 6.1 错误分类

1. 可重试：网络超时、429、5xx、暂时性连接失败。
2. 不可重试：参数错误、鉴权错误、数据校验失败。

### 6.2 重试策略

1. 指数退避 + 抖动：`delay = base * 2^attempt + jitter`
2. 达到 `max_retries/max_attempts` 后转死信。

### 6.3 超时控制

1. 子任务执行超时后置为 `failed` 并进入重试或死信。
2. 主任务设置总超时窗口，超窗后转 `partial_succeeded` 或 `failed`。

### 6.4 幂等策略

1. 主任务以 `idempotency_key` 去重。
2. 子任务以 `(job_id, record_id, document_type)` 做幂等约束。
3. 结果写入采用 UPSERT，避免重复扣分/重复缺陷。

---

## 7. API 设计

### 7.1 入队与查询

1. `POST /api/v1/qc/jobs`：创建主任务并返回 `job_id`。
2. `GET /api/v1/qc/jobs/{job_id}`：查询主任务状态与进度。
3. `GET /api/v1/qc/jobs/{job_id}/items`：查询子任务明细。

### 7.2 控制与补偿

1. `POST /api/v1/qc/jobs/{job_id}/cancel`：取消任务。
2. `POST /api/v1/qc/jobs/{job_id}/retry`：重试失败子任务。
3. `POST /api/v1/qc/dead-letter/{id}/replay`：重放死信任务。

---

## 8. 监控与告警

### 8.1 核心指标

1. 队列长度（主任务/子任务）
2. 队列等待时长 P50/P95/P99
3. 执行成功率、重试率、死信率
4. LLM 调用耗时与错误率
5. PG 写入 TPS、慢查询数、锁等待

### 8.2 告警阈值（初始）

1. 子任务积压 > 10,000 持续 5 分钟
2. 子任务 P95 等待 > 120 秒持续 5 分钟
3. LLM 5xx/超时率 > 10% 持续 3 分钟
4. 死信新增速率 > 100/小时

---

## 9. 安全与审计

1. 所有状态变更写 `qc_job_events`。
2. 管理员操作（取消/重放）必须记录操作人和原因。
3. `payload/result` 中敏感字段脱敏落库。

---

## 10. 实施计划

### D1-D2

1. 建表：`qc_job_queue`、`qc_job_items`、`qc_job_events`、`qc_dead_letter`
2. 完成基础入队/查询 API

### D3-D4

1. 实现 Worker（claim、执行、重试、死信）
2. 接入 `qc_results`/`qc_defects` 写回

### D5

1. 接入反压与限流参数
2. 接入监控告警
3. 压测与故障演练

### D6（可选）

1. 增加 `qc_assignee_workload` 等统计异步刷新任务
2. 评估是否迁移独立 MQ

---

## 11. 验收标准

1. 高峰期任务进入队列后 API 响应时间 < 300ms（不含实际质控完成时间）。
2. 队列机制启用后，PG 无明显锁风暴与连接耗尽。
3. LLM 侧超时/失败不会引发同步雪崩，系统可自动重试并可观测。
4. 失败任务可进入死信并支持人工重放。
5. 任务状态机转换 100% 可追踪（事件审计完整）。

---

## 12. 待确认决策

1. Phase B 独立 MQ 选型：RabbitMQ 还是 Kafka。
2. 单任务允许最大子任务数（防止超大批次长期占用）。
3. 低优先级任务在高峰期是否允许自动降级到离峰窗口执行。
4. 是否需要多租户配额策略（按科室/机构）。
