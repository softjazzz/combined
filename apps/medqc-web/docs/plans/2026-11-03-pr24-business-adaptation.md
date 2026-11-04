# PR24 业务线适配计划与验收

基线 a77c77e56，来源 bb44fa43f；独立分支 codex/pr24-business-adapt-20261103。

1. 保留双方工作记录，核对系统配置页自动合并，保留页面加载与本地模型设置。
2. 先复现 infra_runtime.new_job 未携带真实模型运行快照；沿正式 capture_luxian_0609_task_runtime 生成合成客户端身份，保持创建前授权校验。
3. 保留无身份／Direct／热切换拒绝用例；补真实PG开关切换及旧任务持久化模式、ACK、重试、崩溃恢复。
4. 仅使用 owner 校验的一次性Docker PG/RabbitMQ；固定应答和网络白名单。基础设施不可用时不绕过隔离，不称通过。
5. 定向前后端、完整类型、只读lint与编码检查；本地提交，先不推送、不合并、不部署。

默认关闭、环境兼容及管理员权限不改变，不改医学合同、不连接业务库或模型。

## 实施结论

- 来源提交以 0ecbe501d 引入；唯一显式冲突是 PROJECT_ROLLING_TODO.md 顶部记录，保留双方。
- 正式运行/终末入口 qc_sichuan.py 与客户样本入口 qc_sample_pools.py 已使用 capture_luxian_0609_task_runtime；创建事务前的实际 Gateway 校验保持不变。
- 根因是 infra_runtime.new_job 漏传 lx0609_task_runtime。新增隔离反例先复现同一创建失败，再使用真实 SichuanQCLLMClient 的 Gateway 属性经正式 capture 函数生成合成身份；不调用 generate，不填任意64位占位哈希，不删除授权检查。
- 一次性基础设施的开关状态目录绑定 run_id 与 manifest 所在临时目录，防止读取工作树里的历史配置。
- 增加缺身份、Direct、空Profile、空端点身份均拒绝且任务/dispatch/outbox均为空的反例。
- 新增真实基础设施用例：缺身份事务不落库；开关关闭→开启→关闭，只有中间任务进入MQ，关闭后原任务仍经Publisher/Worker完成并保存。连同原10项迁移、ACK、重投、重试、取消、崩溃恢复、归档共12项，待基础设施恢复后执行。
- V7.1外壳/导航/主题/图标、P9-D源码和迁移没有差异。系统配置页保留最新科室静默加载，并让质控运行页签不等待同步初始化。

## 实际验证与限制

在 apps/medqc-web/backend：

```powershell
python -B scripts/run_qc_scheduler_tests.py --profile m2-synthetic --suite m2-release tests/unit/test_qc_scheduler_isolation.py tests/unit/test_qc_infra_isolation.py
python -B scripts/run_qc_scheduler_tests.py --profile offline tests/unit/test_qc_dispatch_outbox.py tests/unit/test_qc_runtime_settings.py tests/unit/test_luxian_0609_task_runtime_identity.py
python -B scripts/run_qc_m2_infra.py --output-dir .tmp/pr24-infra-20261103
```

- 首轮联合227通过；补齐4个拒绝反例后定向74通过，二者交叠，不相加。
- 前端2文件34通过，覆盖开关、账号切换、撤权、晚响应和合并后的系统配置页面。完整vue-tsc通过；相关只读ESLint 0错误/107警告；相关Ruff与diff检查通过。
- 真实基础设施命令确实执行，但Docker Desktop初始化不稳定，报告 isolated_infra_failed / RuntimeError，complete=false。启动日志显示 dockerInference 本地套接字不可访问而退出；第二次启动同样失败。未修改Docker配置或删除套接字，不将此记为PG/RabbitMQ测试通过。
- 本轮报告 .tmp/pr24-infra-20261103/m2-infra-result.json：owned_containers_removed=true，business_database_writes=0，real_model_calls=0。尚未取得这12项真实PG/RabbitMQ验收结果。
- 完整前端/全仓后端未重跑，GitHub CI未触发；未推送、合并、部署、写业务库、连接模型或重跑患者质控。原PR24的9项基础设施失败不能据本地离线通过宣称已全部转绿。

剩余收口仅为：Docker Desktop恢复可用后，原命令在新的输出目录重跑12项一次性基础设施验收，并复核结果；不要绕过owner/network隔离或删Gateway校验。本分支仍不适合直接宣布验收完成。
