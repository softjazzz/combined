# V3.6 抽查任务到 workspace job 的运行关联

## 证据和边界

- 旧 `re-analyze` 只传 `record_id` 给演示式 `QCService.evaluate`，不产生 workspace job；现代场景继续返回 409。
- 四川批量入口在原路由内同时完成规则集/LX0609 来源门禁、病例三坐标匹配、快照、幂等、job 创建和 worker 派发。只调用底层 `create_batch_job` 会绕过这些校验，调用 HTTP 路由则无法与任务关联同事务。
- `qc_tasks` 由 SQLAlchemy 适配客户端按连接的 search_path 读写；split 默认 `public,qc,...`。任务抽样、运行关联不得硬编码 `qc`，否则双表部署会读写不同的任务。
- 运行/终末候选与抽样仍拒绝执行，门急诊规则集与 workspace 执行资料链缺失。本批只接通已保存、完整三坐标任务的 job 桥接，不宣称正常创建到真实结果的业务闭环。

## 本阶段实现

1. 将原批量入口的规则、来源、病例和 job 参数准备迁为独立的完整职责模块，约 470 行；原 endpoint 保留鉴权、运行中幂等复用、默认提交、worker 派发和原响应。无 task context 时保持原有 digest/filter 合同；task context 纳入 `task_id + run_number` 防跨任务复用。
2. 新增 `task_qc_runs`，按 `(task_id, run_number)` 保存 1:N 历史，job_id 唯一；job 状态和结果仍以 workspace 为唯一权威。迁移 49 支持现存 `qc`/`public` 任务表并拒绝漂移，不对动态 job 表建跨 schema 外键。
3. 创建人启动运行时锁任务，核对场景、规则集、抽样行数量与三坐标，再在同一事务插入 job 和关联，提交后派发 worker；活跃/未知状态拒绝重入，终态重跑产生新 job。派发失败显式标记 job 失败并返回其 ID。
4. 任务详情仅创建人读取运行历史，通过精确 job_id 查询原 workspace 详情；不复制或重新解释质控结论。收到任务的质控员暂不获得整批 job 读取权限；门急诊和历史任务不显示虚假的执行能力。

## 验收证据与剩余风险

- 隔离测试覆盖外部事务不自行提交、唯一约束/回滚、派发失败、权限、活跃重入、重跑、无效规则集零 workspace 初始化、旧批量端点关键合同和前端任务切换防旧结果。`npm run lint`、`type-check` 已通过；完整前端单测仍有既存 3 项失败。旧 LX0609 throughput 测试 2 项因 020 当前被规则总表标为 pending 而与旧期望不一致，原路由同样会失败。
- 尚未获得迁移 45–49 与业务写入授权；业务库仍为 revision 44。无运行/终末归档值域合同、门急诊规则集和正样本，不具备真实三场景验收。worker 派发成功但随后进程崩溃的队列恢复仍依赖既有 workspace 机制，未在本批重构。
