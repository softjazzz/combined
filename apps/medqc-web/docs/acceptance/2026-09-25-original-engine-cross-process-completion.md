# 原始 LX0609：跨启动任务完成与 Canonical 读回

将一条原始 `LX0609-01-01-01` 规则任务由第一个 Python 进程通过正式 `CustomQCWorkspaceService.create_batch_job` 写入隔离 SQLite 文件，持久化当前构建/模型/设置快照及单病例规则范围。第二个独立 Python 进程分别通过两条路径处理同一冻结形状的任务：直接调用正式 Worker，以及启动扫描已排队任务后提交正式 Worker。

两条路径都领取了新的执行代次，用合成住院记录执行至 `completed`；原始 001 的无来源输入形成 `data_gap`。任务结果与同一 SQLite 文件中的 Canonical Envelope 读回均为一条 `data_gap`，持久化 Token 数为 0。探针禁止模型调用，并替换了病例收集、bundle 与 Source Reader 数据读取，因此没有连接客户库或模型服务。此前只在身份门禁处主动截断的探针仍保留，以验证同版/异版及配置漂移拒绝。

`test_luxian_0609_task_restart_persistence.py` 整份 **17/17 通过**。这将 B 阶段本机技术证据从“新进程通过门禁”推进到“新进程完成一次原始规则执行和事务保存”，但尚未验证客户 PostgreSQL 双进程争锁、真实安装包中断恢复、非空真实病例或临床判定准确性。不能据此宣布 B/D 阶段完成。
