# homology 医嘱与检验同步实施记录

**目标：** 在集成工作树直接改造同步代码，医嘱、检验可从 homology 读取，其余表继续使用现有数据源。

**方案：** 在客户样本和常规同步共用的 CaseSetSyncService 按表选择来源。沿用现有源 PG 的主机、端口和凭据，仅覆盖数据库及 schema；显式配置本客户的机构映射。默认关闭，启用后所选五张表只读 homology，不以空结果或异常触发隐式来源切换。整次住院替换本地快照，避免保留旧来源独有的医嘱。

**技术栈：** Python、psycopg2、SQLAlchemy、Alembic、pytest。

## 已确认输入

- homology.graph3_homology 的机构值为“机构号”，客户本地为“泸县人民医院”；患者号、就诊号一致。映射必须按部署显式绑定。
- C23 上游有 121 条医嘱，下游两张医嘱表均为 0。C25 存在标识和状态差异，不能跨源拼接后去重。
- C11/C13/C14/C25/C27 上游检验结果明细合计 1453 条，结果非空 1077 条；原本地归档明细均为 0。空结果行保留，不合成正常结果。

## 决策

选择按表路由，避免全局换库影响其他文书。继续修治理不能及时满足本次同步需求；按空结果回退或混合两库会引入范围和状态歧义，均不采用。此次不建设通用多源平台或前端配置页面。

## 步骤与验收

1. 新增受控 homology 来源适配：五张表白名单、显式机构映射、连接复用、完整三坐标校验、按源字段保存状态和时间。
2. 接入共用同步和预检，目录补入 labtest_item，五张表在切源时强制整次住院重载。来源不全时不生成已完成 Bundle。
3. 为医嘱补执行/撤销/审核时间，为检验结果补报告状态；迁移只增加可空列，兼容 public/cdm，不在本轮执行共享数据库迁移。
4. 检验结果用 test_id + print_order_id 构造稳定文档标识，test_item_id 映射到项目 ID；覆盖同一项目多条结果及跨申请相同打印序号，防止覆盖丢行。
5. 合成数据验证路由、错院拒绝、源只读、空表替换、重复标识拒绝、字段落库、旧配置兼容及预检来源。运行现有同步/样本回归、编码/Lint等检查。

## 部署边界

本轮只改代码及本地离线测试，不连接医院库、不写业务库、不调用真实模型、不打包、不推送。客户环境需先升级数据库，再显式启用 homology 同步并重新同步目标病例。真实数据到本地再到质控的验收尚待客户执行。

## 部署配置

在目标部署的 `backend/.env` 中明确配置（现有源 PG 连接仍指向 clinical_data）：

```dotenv
HOMOLOGY_SYNC_ENABLED=true
HOMOLOGY_DATABASE=homology
HOMOLOGY_SCHEMA=graph3_homology
HOMOLOGY_SOURCE_INSTITUTE_ID=机构号
HOMOLOGY_TARGET_INSTITUTE_ID=泸县人民医院
```

先备份并升级目标本地库至 `20261016_000049`，再重启后端。旧配置的部署默认不启用 homology；直接替换整个源数据库配置会影响其他文书，不属于本方案。修改 `.env` 不会自动执行数据库迁移。

同步预检对这五张表显示 `homology.graph3_homology.<表名>`，同时检查新证据列是否存在。客户样本、常规同步及一键质控的资料同步共用该路径，不需另外维护一套入口。切换前的历史已保存质控结果不会自动重算。

部署后的定向验收：先重新同步 C22/C23/C25 的医嘱及 C11/C13/C14/C25/C27 的检验；检查明细数量、结果非空数量、原状态和时间。实际源数据可能继续更新，不把本次计数写成永久判定阈值。需在同步完成且 Bundle 刷新后，再运行依赖这些资料的质控点。

## 本地验证

- 核心路由、迁移和同步/客户样本/Bundle 相关后端回归：522 项通过。
- 用完全合成的数据复用五份样本的行数形状，经适配与真实 UPSERT 投影后仍为 1453 行、1077 行结果非空，没有以项目名称或重复项目 ID 覆盖结果。
- Ruff 检查通过；Alembic 离线读取 head 为 `20261016_000049`。迁移 SQL 编译验证覆盖 cdm/public、已存在列和缺失表，无真实数据库迁移。
- 暂存区编码检查通过；最终不自动修复的 Lint 为 0 错误、1361 条既有警告，检查后没有前端文件差异。
- 前端类型检查通过。全量单测首轮为 1329 通过、5 失败，失败分布在四个文件，涉及当地时区断言和两个路由用例在全量负载下超时。设置 `TZ=Asia/Shanghai` 后单独复跑这四个文件，37 项全部通过；未宣称全量复跑通过。本轮不修改前端，Lint 自动产生的格式化已单独撤销。

限制：医院 homology 的实际稳定标识唯一性、源字段值长度及最终同步效果仍须部署后只读预检和定向同步确认。重复或缺少稳定标识会在替换本表旧快照前报错；不丢弃无法落库的明细。每张表按既有事务替换，本次并未改为跨库或跨表原子事务。

### 后端回归命令

在 `apps/medqc-web` 目录执行，避免两个脚本测试的 `backend` 包导入路径问题；不使用 xdist。

```powershell
$env:PYTHONPATH = 'backend;.'
$tests = @(
    'test_homology_sync.py', 'test_homology_evidence_migration.py',
    'test_case_set_sync_service.py', 'test_sync_consistency.py',
    'test_death_record_sync_content.py', 'test_pathology_eye_findings_migration.py',
    'test_benchmark_customer_sample_sync.py', 'test_custom_qc_sample_pool_service.py',
    'test_customer_sample_validation_e2e.py', 'test_sync_router.py',
    'test_sync_templates.py', 'test_auth_sync_contract.py',
    'test_sample_sync_incremental_capability_audit.py', 'test_sample_sync_cursor_repository.py',
    'test_sync_idempotency.py', 'test_sync_idempotency_migration.py',
    'test_sample_source_coverage_audit.py', 'test_running_final_bundle_orchestrated.py',
    'test_domain_bundle_assembly.py'
)
$testPaths = $tests | ForEach-Object { 'backend/tests/unit/' + $_ }
py -3.10 -m pytest @testPaths -q --tb=short -o addopts='' --disable-warnings
```
