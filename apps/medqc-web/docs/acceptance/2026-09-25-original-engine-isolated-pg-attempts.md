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

测试使用合成任务和固定合法结果，没有调用模型或读取病历；它证明本机 PostgreSQL 的实际双进程领取、事务条件更新和结果提交边界，不证明客户机安装包中断恢复、客户 PostgreSQL 的部署配置或真实模型费用。B/D 仍按主计划保留这些外部验收项。
