# 原始 LX0609 引擎整改：当前交付审计

固定集成提交：`db5ff481e11beb88422a2db8620c6804065d6bae`。从本机打包时的 `2d1d3730d` 到本提交，`backend/app`、`src` 和 `scripts` 没有生产文件差异；后续提交只补测试与验收记录。本文件按[主计划的“再收敛”退出条件](../plans/2026-09-23-lx0609-engine-boundary-refactor-master-plan.md)划分证据，不将新 CT、抢救内容、病理、0916 或源库同步计入原始引擎整改。

| 阶段 | 现行工程证据 | 尚不能签收的范围 |
| --- | --- | --- |
| A 一次发布与一致读取 | 正式 Aggregator 的 Canonical 模式不调用旧结果适配；任务详情、latest、反馈、病历详情和三格式导出已有同一保存结果的隔离 SQLite/PG、HTTP 与合成页面链测试；非法已发布事实及签章被受控拒绝。[交付证据](2026-09-24-original-engine-requirements-evidence.md)。原始 002/004/005/006/007 冻结来源回放 75/75 与各自基线全字典相等。[回放](2026-09-25-original-engine-five-rule-replay.md)。 | 75 例未覆盖模型调用分支及全部原始规则，也没有独立临床答案；浏览器证据用后端测试产物拦截 API，不是客户联机。保护候选 81 条均 pending，影子 900 条未签收，review20 无病例行。 |
| B 接纳计划与恢复 | 单病历、病历池、客户样本正式 API→Worker→Canonical 回读的串行、显式并发、默认并发集成测试 6/6；固定空资料和会诊模型桩结果跨入口一致。[三入口证据](2026-09-24-original-engine-requirements-evidence.md)。当前生产代码从干净源码用 PowerShell 5.1 打包并解压，包内排队任务跨进程恢复成功，异版在病例读取前受控拒绝。[发布包证据](2026-09-25-original-engine-package-restart.md)。 | 集成测试仅两份合成病例；客户启动脚本、客户 PostgreSQL 配置及真实模型任务未验。 |
| C 身份与执行协议 | 正式目录/编译器漂移拒绝、测试专用四段式规则经正式 Worker/保存/读取链通过；属性 owner 表已固定。[阶段 C 审计](2026-09-24-original-engine-phase-c-audit.md)。 | 工程合同已验收；不把它当作医学或客户部署签收。 |
| D 共享事实与有效代次 | 固定输入下同源模型请求 2→1，归约/发布结果不变；隔离 PostgreSQL 双进程争领、取消进度与 Token 保留、旧代次拒写及正式 Worker 提交共 11/11。[PG 事务证据](2026-09-25-original-engine-isolated-pg-attempts.md)。 | 取消后模型未返回时，提供方实际费用不可由本系统凭空确定；客户部署中的模型中断与 PG 配置未验。 |

旧路径处理：正式执行在 `luxian_0609/execution.py` 显式传入 Canonical 交付模式，`luxian_0609_result_aggregator.py` 仅在显式 `legacy_compatible` 模式调用 `adapt_luxian_0609_legacy_customer_result`；原始正式结果不再从病历详情的批量 `items_json` 回退。`build_luxian_0609_legacy_executor_registry` 虽名为 legacy，仍为 11 个现役规则族函数提供正式 Engine 回调，没有已实现的替代链，因此保留；按名称直接删除会切断执行。没有为此新增注册框架。

当前结论：**工程代码可交只读审查，整体 goal 尚未达到退出条件。** 下一步需要独立临床复核并签收原始保护集，覆盖明确合规/不合规、资料不足、多事件及模型调用分支；还需要授权操作员在客户环境核对相同构建的前后端、PostgreSQL 和一份正式任务从结果到页面/导出的同源交付。客户数据库写入不由本任务执行，患者原文也不写入此文档。实际模型取消费用若无法从提供方获取，应保留“观测未知”而非伪造零值。
