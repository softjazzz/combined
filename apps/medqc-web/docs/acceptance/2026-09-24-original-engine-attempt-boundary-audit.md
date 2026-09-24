# LX0609 原始 Worker 执行尝试边界审计

## 结论与范围

本轮只核查原始 LX0609 批量 Worker 的取消、重新入队、重复领取及迟到完成。未修改生产代码，未访问客户数据库或模型。`backend/tests/unit/test_luxian_0609_attempt_boundary_audit.py` 是**修复前现状基线**：它固定已证实的缺口，不应作为修复后永久期望直接合入。

现有取消保护成立：取消事务先提交时，`complete_batch_job` 的条件更新不命中，Canonical Envelope 不写入。但同一任务 ID 被重新入队并进入 `running` 后，旧执行尝试没有身份可供区分；旧结果可以更新新尝试。当前 `mark_batch_job_running` 也接受已经 `running` 的任务，不能作为唯一领取门禁。

## 线上入口与执行路径

- `qc_sichuan.py:2765-2792` 的正式重试路由直接调用 `retry_batch_job`，随后以**同一个 job_id**提交后台任务。测试对已取消任务连续调用该路由两次，得到两个相同 job_id 的提交。`custom_qc_workspace_service.py:4140-4260` 对任务状态没有“仅终态可重试”的门禁，重新入队会复用同一行和同一 ID。
- `detached_task_runner.py:35-56` 按每次调用向线程池提交一个 Future，没有 job_id 去重；隔离测试对同一 ID 提交两次，两个 Future 均执行。没有发现正式路由之上的单任务锁。
- `sichuan_workspace_batch_worker.py:1240-1262` 按 job_id 读取并调用 `mark_batch_job_running`；`custom_qc_workspace_service.py:4284-4323` 对 `running` 返回成功，更新只按 ID。旧 worker 与新 worker 可同时通过。Worker 在多处 `await` 期间可能遇到取消/重试，并在 `:3750-3755` 用同一 ID 完成；取消轮询 `:1671-1685` 只看当前是否 `canceled`，重试后就不再识别旧尝试。
- `custom_qc_workspace_service.py:4432-4514` 的完成条件为同 ID 且 `status != canceled`，防止取消后的迟到写入，却不区分重新 `running` 的新尝试。进度更新和失败收尾也按当前行状态操作，需要在修复时一并绑定尝试身份。

## 隔离复现及边界

新审计测试使用内存 SQLite 中的一条原始 LX0609 任务行，并直接调用正式存储方法和重试路由：

1. `running → canceled` 后旧结果调用完成方法，状态保持 `canceled`。现有 `test_luxian_0609_result_persistence_contract.py::test_complete_batch_job_canceled_before_completion_does_not_write_envelopes` 还核对 Canonical Envelope 未写入；本轮也运行了它和取消/完成竞争测试。
2. 同一任务 `canceled → retry queued → mark running` 后，模拟旧尝试迟到的合法失败交付，状态变成 `failed`，覆盖了新尝试。此处是真实存储事务，但未运行两个完整 Worker，也未调用真实模型；线上可达性由正式重试路由、线程池无去重和 Worker 的代码路径共同支持。
3. 同一条 `running` 任务连续调用两次 `mark_batch_job_running`，两次均返回 `True`。测试证明存储领取不互斥；真实双 Worker 并发成本和发生频率尚未测量。

聚焦执行：新增审计测试 4 项，加既有取消交付两项，共 **6 passed**。`DATABASE_URL` 使用指向本机不可达端口的合成连接串以完成模块初始化；测试实际会话全部替换为内存 SQLite，未连接 PostgreSQL。

## 最小修复方向（尚未实施）

原始 0609 Worker 在任务由 `queued` 原子领取为 `running` 时取得该次 `started_at` 或现有执行代次，作为本次尝试身份。领取须用 `WHERE id=:id AND status='queued'` 的条件更新和 rowcount 判定，避免两个 worker 同时成功。随后进度、取消轮询、完成、失败和自动重试都要核对该身份，且只允许当前有效尝试提交。仅检查 `status='running'` 不足以阻挡旧 worker，因为新旧尝试均会看到 `running`。

正式重试入口还要避免对已 `queued/running` 的任务重复提交；旧 worker 的自动重试应要求它仍是当前完成尝试，不能把新尝试重新置为 `queued`。优先复用现有 `started_at`/执行代次和条件更新，不新增全局锁、租约框架或数据库列。改动要限定原始 LX0609 正式 Worker；0916 与其他通用任务入口须保持既有语义并单独验收。
