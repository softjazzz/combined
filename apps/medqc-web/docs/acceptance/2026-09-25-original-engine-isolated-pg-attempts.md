# 原始 LX0609：隔离 PostgreSQL 双进程执行代次验证

## 环境与边界

在本机临时目录独立初始化 PostgreSQL 18 集群，只监听 `127.0.0.1:15432`。测试通过 `MEDQC_LX0609_ISOLATED_PG_URL` 显式启用；未设置时跳过，地址不是本机 15432 时在建立连接前拒绝。现有 5432 服务、客户数据库和患者资料均未参与。每轮只在该独立集群中新建随机 schema，结束时删除该 schema。

复现命令（在 `backend` 目录，先启动独立测试集群）：

```powershell
$env:MEDQC_LX0609_ISOLATED_PG_URL = 'postgresql+psycopg2://medqc_test@127.0.0.1:15432/postgres'
py -3.10 -m pytest tests/integration/test_luxian_0609_isolated_postgres_attempts.py -q
```

## 验证结果

- 两个独立 Python 进程在同一开始信号后对同一正式任务行争领，三轮均恰有一方取得 LX0609 执行代次。
- 取消并重试后，旧代次的 `complete_batch_job` 被拒绝，Canonical Envelope 行数保持 0；新代次提交后仅有 1 行。公开读取回到原始 `LX0609-01-01-01/compliant`。
- 三轮 **3/3 通过**。无专用环境变量时 **3/3 跳过**；误指向 5432 时 **3/3 在连接前拒绝**。

随后增加正式 Worker 的纵向用例：通过实际 `CustomQCWorkspaceService.create_batch_job` 在随机测试 schema 中保存冻结的原始 `LX0609-01-01-01` 任务，再由独立 Python 进程运行 `run_sichuan_workspace_batch_job`，不手工调用 `complete_batch_job`。合成空来源让该规则确定性返回 `data_gap`，进程内明确禁止模型调用；任务状态为 `completed`，任务项与同一 PG 的 Canonical Envelope 均为一条 `data_gap`，保存 Token 为 0，Envelope 表恰有一行。与上述并发用例合跑 **4/4 通过**；不指定隔离库时 **4/4 跳过**。Ruff、前端 lint/type-check 与单测 **1066/1066** 通过。

测试使用合成任务、固定合法结果或合成空病例来源，没有调用模型或读取真实病历；它证明本机 PostgreSQL 的实际双进程领取、正式 Worker 原始规则执行、事务条件更新和结果提交边界，不证明客户机安装包中断恢复、客户 PostgreSQL 的部署配置或真实模型费用。B/D 仍按主计划保留这些外部验收项。
