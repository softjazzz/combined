# 0916索引结构修复与023正式验证 Implementation Plan

> 用户2026-10-06明确授权数据库结构修复；沿用此前两新副本、一次正式任务、最多八模型调用预算。使用本机writing-plans/executing-plans工作流。

**Goal:** 只补实际visit_index三个缺字段，恢复已批准的验收启动门禁，再完成023两个麻醉记录存在性正例的正式交付验证。

**Architecture:** 在既有Alembic链追加单条可重入迁移，不改正常同步或质控判据。主协调使用应用连接的短事务、明确qc对象和SQL白名单执行该迁移及必要版本登记；正式验收另开无DDL护栏，两阶段权限不可混用。

**Tech Stack:** PostgreSQL18.3、SQLAlchemy、Alembic、pytest、正常FastAPI/Worker/认证浏览器入口。

## 证据、假设与范围

主协调当前只读PG核对：应用DB_SEARCH_PATH=qc,sys,cdm,public,legacy，实际解析qc.visit_index(OID199967)，不是public同名表。qc约15行、public1行；两表不能由名称混同，不更改public。实际schema及OID须在写事务内再次确认，不只靠既有产物。当前public.alembic_version唯一20261003_000046，仓库最新也是该版本。

visit_index_service.py:26–36现有合同定义latest_mirror_success_time为TIMESTAMP NULL、mirror_delay_base_minutes及sync_interval_minutes为INTEGER NOT NULL DEFAULT30，当前qc缺这三列。现有九列、三坐标主键/索引正常；scene_history已有[]默认，无需新增字段或改变其默认。实际无用户触发器/检查约束/RLS。只读元数据是已观测证据，待证伪假设：该增量迁移可恢复现有写入合同，且不改变原列/原值、约束、索引和资料所有者。

## 白名单与事务

- 新增backend/alembic/versions/20261006_000047_visit_index_sync_fields.py，down_revision=20261003_000046；现有split模式仅qc，single模式按旧迁移惯例public。本次执行只允许split/qc。
- 新增backend/tests/unit/test_visit_index_sync_fields_migration.py，只验证该迁移公开upgrade：三类型/空值/default30、已有合法列不重复DDL、类型/空值/默认错误拒绝、缺表失败；downgrade拒绝自动删既有字段，参照000043。
- 两生产门禁模块不再修改，main/env/巨型创建服务/其他规则一律不改。迁移为现有结构版本责任，预计不足100行，不构建新平台或新增事实owner。
- root私有执行及formal脚本仅.tmp/0910-full-audit/*-private；原文/标识/过程日志不提交。长期仅本文及统一进度表。

执行前冻结源/目标版本/列合同并审查。真实事务设置lock_timeout=5s、statement_timeout=30s；仅锁qc.visit_index，列出最多101原行的原九字段，超过100即停止不扩大读取。在锁内核实际OID/schema及现有列，执行最多三条ADD COLUMN，绝不ALTER原列/UPDATE病例/创建表或索引。新增列提供两个30默认，使旧行读到新字段默认值；这属于获准结构增量，不冒称新字段从原业务数据回填。原九字段前后逐值相同，行数/OID/filenode及原列/约束/索引不变，然后在同连接校验现有验收合同。

唯一额外技术写入为public.alembic_version从唯一46登记到47；通过既有Alembic MigrationContext/Operations执行单条迁移和stamp，不运行upgrade head的未知链，不改其他版本或业务表。所有步骤同事务，失败回滚；提交后另连接只读重新检查三列及公共启动门禁。实际SQL只允许这三ADD、目标锁、元数据SELECT/SET及该版本登记，其他DDL/DML立即停止。没有授权DROP/DELETE/旧病例或结果更新。

## 并发分工与验收

实现cost_fix_offline_20261006负责迁移/测试两路径，禁止自行PG/HTTP/模型/提交。prepare_018_offline_20261006独立离线审查修复合同/事务脚本，仅其树私有产物。cost_review_010012_20261006准备023正常运行私有脚本及完整身份/写入/调用护栏，0执行；root亲自审核后运行。均复用现存Sol6.1 medium，不新增工作树，保护他人修改。

先迁移公共入口红→绿、SQL编译/独立证伪，再root实际受控迁移和原值保护。修复后验收阶段重新恢复零DDL：正常lifespan/auth、新副本test-records、对应Bundle及工程预期、新023 run/leaf、PG/API/逐例页面。两DTO保留原麻醉文书，假名元数据不代表原患者，独立工程预期仍非clinical/gold批准。

正式阶段预算最多两副本创建POST、两新工程答案PUT、一次run POST、八generate/attempt/HTTP（所有重试合计，018Stage2禁止）。先核实际族调用路径是否可落预算；任何超量、越界、源漂移、非目标旧对象更新、DDL或模型失败均保存产物停止，不重新提交任务或改预期。若两副本整包，64计划对须恰好各一个合法结果或执行失败；023目标须与冻结存在性状态/原因/事实/证据/建议一致，其他失败不伪造临床结论。

PG/正常认证API逐值核公开字段，页面逐例验证；不得以其他病例页面代替缺结果。真实调用参数/Token/API秒/任务墙钟分开记录，未知成本保留不完整。023只验存在性，不声称独立触发/真实缺记录/局麻边界或完整临床验收。临床签认、启用、上线批准均不写。

## 风险与停止

结构ADD持短独占锁；超时/目标漂移则回滚，不扩权限。既有qc/public同名表未收敛，但当前读取明确qc；本批不扩到跨来源治理。原行比较仅qc索引原列，不声称全库冻结。外部并发事务在提交后可改变表/源码，正式执行前后重新核；不能改他人8001或旧任务恢复。

编码/lint、聚焦Python回归后只提交本任务四路径；他人两暂存文档保持，必要时关闭本次Husky并手动补门槛，理由写提交说明。有限闭环结束报告并停止，不迁下族、不调首程Prompt/运行018模型。

## 结构修复实际结果

迁移公开upgrade先红23失败/7通过（空实现），最终33项通过；主协调独立合并门禁/同步共117项通过（pytest1.18秒）、ruff通过。root首次使用confcutdir排除应用conftest后漏PYTHONPATH，收集出现2个ModuleNotFoundError；补正确backend导入路径后通过，没有为此改生产代码或测试判据。

独立审查定位root事务脚本初稿未锚定预期OID、提交后只检查字段存在而没检查type/default。主协调反查自己的初稿及共享门禁只读取column.name的实际实现确认后，在任何DDL前补OID199967锚、提交后独立只读连接复用migration.upgrade完整合同及幂等检查。另补拒绝DDL事件触发器及版本表用户DML触发器/规则。安装Alembic的stamp/update源码和实际编译SQL经root亲读，确认外部事务中只执行唯一版本UPDATE，不自行提交或运行其他迁移。

root受控实际事务成功提交：3ADD仅qc.visit_index，1UPDATE仅public.alembic_version的46→47，5秒锁等待/30秒语句超时。该执行探针统计77 SELECT/4 SET/1 LOCK/3 ALTER/1 UPDATE；不是此前全部元数据读取量。原九字段的列元数据与15原行逐值完全相同，主键、索引、检查/外键、OID及filenode均不变。旧行仅新两字段读到默认30，时间字段NULL；没有业务回填、旧病例/预期/结果更新。没有修同名public.visit_index。

提交后独立只读连接核三列type/null/default并重入upgrade无新DDL、版本47；公共启动门禁passed。root另外一进程重新解析原/后JSON确认保护集合相同，再新连接核实际三列及版本仍47。当前只关闭结构合同缺口，不能算023已运行或临床通过。正式阶段尚未执行，权限恢复零DDL。

023存在性工程预期另确认：root亲读input_context.py:190–228及surgery_consent_rules.py:153–184/264–275，023判定只看event/presence；024有效逐项抽取可改变运输的completeness/docID/evidence，不能用它倒填023人工质量预期。POST前冻结核心存在性结果及条件证据定位合同，全部实际公开字段PG/API逐值比较，不修改H22旧预期，不把024质量算023临床验收。

私有证据：[受控事务及原值](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-schema-repair-root-private.json)、[实现红绿](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-visit-index-schema-repair-implementation-private.md)。患者标识/原行及过程脚本不提交。

独立[迁移与事务审查](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-schema-repair-review-result-private.md)未发现剩余阻断。root另外解析其原JSON核迁移源码逐字绑定，8不兼容反例全在DDL前拒绝，3ADD+1版本UPDATE编译精确，外部事务true/框架自身commit0。独立离线探针root源码冻结早于最后两个版本触发器/规则SELECT；代理及root对最后增量另亲读核定，未把较早探针写成完整最终源码执行。实际迁移及回读由root真实PG产物证明。

提交前只检查lint已通过；编码手动补跑。因暂存区有他人两文档，本次仅4路径限定提交并关闭本地Husky，避免lint-staged改写他人文件，理由写提交说明；不改CI。完整前端type-check/test:unit未跑，使用仓库允许的编码/lint及117聚焦Python回归。
