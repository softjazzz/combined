# 工作区元数据GET与临床来源解耦

## 基线与根因

基于远端 `codex/business-agent-integration` 的 `6ad6817b1b66c21b7c94542772a8452215250de5`，在独立工作树和分支 `codex/workspace-metadata-readonly-20261106` 实施。保留原预览工作树及其未提交材料，不切换正在运行的服务。

认证后 `prepare_request` 按整个 workspace 前缀检查临床源，规则目录与历史任务列表也因此在CDM停用时返回 `409 clinical_source_disabled`。规则目录来自静态配置，任务列表来自业务库，两者不需要临床源连通。此外，任务列表原先默认初始化写服务，可能在缺列或索引时执行条件DDL。

## 最小修改与保留边界

- 仅精确匹配两个GET：`/api/v1/qc/sichuan/workspace/rule-sets`、`/api/v1/qc/sichuan/workspace/batch-jobs`。不检查CDM启用或凭据，不读取临床材料；业务上下文沿用已有业务库标记，这不是临床取材失败后的旧库回退。
- 保留来源header/query不一致及未知来源的拒绝；认证仍由原全局依赖执行，后续权限检查不跳过。
- 历史任务列表（含overview）调用已有 `CustomQCWorkspaceService(readonly=True)`，只构造表定义，不建表、补列或建索引。创建/执行及其它入口默认行为不变。
- 当前账号的全局历史列表继续按原 `created_by` 筛选、计数和分页；不扩展为双源并读或新增来源切换。任务冻结来源、历史详情、病例身份、结果安全投影及材料快照校验均保持原实现。
- 前端两个HTTP封装传递真实method，只有上述精确GET不自动附加临床来源。POST、近似路径、实际病例读取继续采用固定东华来源及失败关闭保护。
- 不修改前端页面、医学规则、结果合同、数据库结构或部署配置。CDM、自动调度和模型开关均未启用。

## 必要隔离验证

后端全部使用 `python -B scripts/run_pr8_offline_tests.py`：禁止dotenv、网络及非SQLite连接，不加载应用生命周期。

- 新增核心文件 `test_workspace_metadata_readonly.py`：17项通过。覆盖CDM停用下两个实际handler的HTTP读取、401、来源冲突/未知来源、两种列表视图的账号隔离与分页、真实只读构造不执行DDL、正常读取仅SELECT、POST及近似路径不能借豁免放行。
- `test_batch_job_overview.py`：9项通过。内存SQLite夹具改用StaticPool，支持HTTP请求的线程池读取；原筛选、分页及敏感大字段保护保留。
- 额外4项通过：历史损坏结果不影响其他列表项、历史文书使用原任务来源并校验病例/账号、登记自建历史仍检查权限、缺材料快照不得回查当前CDM。来自 `test_qc_sichuan_result_review.py`、`test_clinical_sources.py`、`test_single_donghua_source.py` 的指定用例。
- 后端合计30个不同用例；核心17项在隔离表定义缓存后复核通过，不累计重复执行数量。

前端用预加载 `scripts/frontpage-v2-no-network.cjs` 的Vitest入口，仅运行：

```text
src/utils/__tests__/single-donghua-source.spec.ts
tests/unit/services/workspace-metadata-routing.spec.ts
```

共14项通过；后者以固定Axios adapter验证两个真实请求拦截器的GET/POST区别及认证header保留，未发送HTTP。定向TypeScript、改动Python的Ruff、相关前端ESLint及diff检查通过。

## 限制与回滚

本轮未连接业务PG、独立CDM或模型服务，未创建业务任务、运行质控、重算历史、执行迁移或部署；未重复全量测试、构建或现网浏览器验收。仍运行原版本的本机服务不会自动获得这次修复，切换版本须另行安排。

回滚本提交即可恢复旧行为；没有数据、配置或迁移回滚操作。源码仅本地提交，未推送、合并或打包。
