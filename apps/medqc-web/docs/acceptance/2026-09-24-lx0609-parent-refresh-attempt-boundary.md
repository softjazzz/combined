# P1-D01：父任务刷新不得跨执行代次回写

## 确证问题

`refresh_parent_batch_job` 先读取父任务及子任务并完成聚合，随后旧实现仅按父 ID、`status != canceled` 更新。隔离 SQLite 中通过真实 `CustomQCWorkspaceService.retry_batch_job` 在聚合与更新间提交同 ID 新代次：旧刷新把新 `queued` 父任务改成 `completed`，并进入 Envelope 写入口。父整单重试与单个子任务重试均可复现；这是存储竞争，不涉及规则医学判断。

## 最小修复

仅对正式 0609 父任务，刷新更新增加读取时父行的 `status`、原始 `filters_json` 与 `summary_json` 条件。UPDATE 未命中即回滚返回，Envelope 不写。父整单重试原本轮换内部 attempt UUID；子任务单独重试则在同一事务中轮换所属正式父任务的内部 UUID，使旧父聚合失效，保留全部业务筛选字段。两个父刷新乱序时，`summary_json` 条件防旧聚合盖过新聚合。非 0609 的原有刷新条件不变；没有新增列、锁框架或状态机。

## 红绿与限制

修前新增的父/子重试交错用例均红：父状态错误地恢复 `completed`，且触发 Envelope 写入口。修后父/子各在新父 `queued`、`running` 状态下拒绝旧刷新；两次刷新逆序保留较新子状态；无竞争正常完成写一次、父取消写零次。`test_luxian_0609_attempt_boundary_audit.py` 共 24 项通过，`ruff` 与 `compileall` 通过。

上述 SQLite 夹具执行真实 Service SQL 和同 ID retry，但使用进程内 SQLite 同线程连接的确定性交错；Envelope 写入口在这组测试中以捕获替身观察，未保存真实 Canonical Store，也未验证 PostgreSQL 独立连接的锁调度。另尝试运行三个旧测试文件：61 通过、48 失败、11 setup 错误；已确认其中 `test_qc_partial_failure_persistence.py` 的 setup 在 `DATABASE_URL=''` 时无法初始化服务，其余失败未逐项归因。不能把该批结果视为本次新增回归已通过；本次验收证据以隔离 SQLite 的 24 项聚焦测试为准。
