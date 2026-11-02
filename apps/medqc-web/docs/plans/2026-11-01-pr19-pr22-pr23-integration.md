# PR19、PR22、PR23按顺序集成记录

## 授权与固定输入

用户授权合入`codex/business-agent-integration`，不部署、不写业务库、不调用模型或重跑病例。远端开始提交为`63b57c1c231412208d39a9a0cb89c382834737bd`。

- PR19来源`aad41b044`，原4项CI成功，实际先合并为`d6d0fa5151571d8b7e2e54de24c64b8459459240`。
- PR22来源`86315b746`，包含PR20的`af914704f`及PR21的`100c44360`。独立分支同步上述业务提交，无文本冲突，适配提交`99b3b6d07`，说明文件格式修正后为`7ce44eaf6`。
- PR23远端原来停在`c3eaf08f4`；本地新增7提交至`ae8cdeda3`，包含C01逐配对恢复、局部晚期保护、新比较输入、跨次矛盾定位及35B后台选择。必须把这些提交推送后验收，不合并缺少已确认修复的旧远端版本。

本机旧integration工作树另有3个未推送的同步工具提交及6组未跟踪资料。已建立独立备份分支、校验增量Git bundle及48文件私有快照，嵌套工作树留在原处。该工作树与本地内容不改动、不混入本次功能PR。

## 冲突和成果保护

PR22同步PR19时，PR19的30个变更文件中28个与来源逐字一致；只有`custom_qc_workspace_service.py`和`test_qc_partial_failure_persistence.py`同时保留原MQ生命周期和新失败轮次保护。

PR23同步新PR22时，双方分别42、31个差异文件，唯一共同修改是`PROJECT_ROLLING_TODO.md`；按时间保留双方记录后消除冲突，其余各自文件均逐字保留来源，不采用整文件覆盖丢弃另一方。

V7.1保护逐字核对7个文件：Layout、配置导航、全局助手、确认框、图标、tokens及main.ts，与已合入PR19的业务来源相同。迁移只继承PR22的056/057，未执行任何业务PG升级。

## 必要验证

两组有重叠，不相加为模型质量或病例数量：

1. PR22同步后：`--profile m2-synthetic --suite m2-release tests/unit/test_qc_partial_failure_persistence.py tests/unit/test_luxian_0609_remaining_fact_freeze.py`，233项通过。使用FakeBroker、内存SQLite和固定执行回调。
2. PR23合成后：`--profile offline --suite dual-model-exam tests/unit/test_strata_admin_configuration.py tests/unit/test_llm_config_loader.py tests/unit/test_llm_config_permissions.py tests/unit/test_luxian_0609_remaining_fact_freeze.py tests/unit/test_latest_full_record_result.py`，342项通过、2项跳过。跳过项为需显式传入私有原应答的入口，之前本地私有回放结果在对应专题记录保留，不冒充本轮重复执行。

相关Ruff通过；共享投影及会诊大测试中已记录的起点问题不夹带清理。编码、凭据、空白及只读ESLint按本次提交核对，未放宽网络/DNS/部署环境/业务数据库/子进程护栏。

新Head的GitHub CI通过才继续对应合并，旧来源提交的绿灯不替代新Head。PR22的一次性基础设施CI使用其自建PG/RabbitMQ，不访问客户或本机业务数据库。实际PR合并提交及最终状态以GitHub元数据为准，本文件不预先宣称远端CI或后续合并已成功。

## 合入后的默认行为

MQ仍`legacy`、模型分发仍`direct`；缓存、观测、双模型实验默认关闭，比较输入默认legacy。手动后台选择百炼35B是普通可选模型配置，不会自动启用06-01-04级联，也没有预先修改持久配置。原医学执行器、证据ID、时限、结果及保存owner保持。

真实模型替换质量、两个会诊跨进程回放、完整客户迁移和生产服务联调仍按专题限制保留，不以本次合并或固定应答通过代替。没有新增真实模型请求、患者任务、结果覆盖、打包、部署或业务库写入。
