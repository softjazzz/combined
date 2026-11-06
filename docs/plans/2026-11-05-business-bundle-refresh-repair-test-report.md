# 业务刷新表与自建病例修复：隔离验收报告

## 基线与交付身份

- Base：fa314c6c251fc5dd02eda96a7d30d70642cc1eb0。
- 工作树：D:/MedQC-worktrees/business-bundle-refresh-repair-20261105。
- 分支：codex/business-bundle-refresh-repair-20261105。
- 实现及测试提交：0126b3964cef3b7a0c6ff6a95313e17e841cb9bb；报告后的提交仅补交付说明，不改变业务实现。
- 候选为复审用源码覆盖/差异ZIP，不是可直接安装的完整Linux应用包；显式依赖上述Base。没有自动部署、数据库迁移、授权或真实模型执行器。

## 已修复的边界

1. 新增063正式迁移：两个刷新审计表、完整v1合同、真实owner计划、唯一键/默认/排序索引、历史数据与序列保留、歧义/不兼容失败及事务回滚。新合同不等于已证明全部历史DDL兼容。
2. 所有刷新读写显式限定每张表的实际schema；取消全局已检查缓存。运行时检查USAGE、DML和生成ID实际依赖的序列（含显式nextval）；不做自动DDL或授权。
3. 自建病例严格反射业务本地cdm(split)/public(single)，材料/pool/item初始事务原子提交；缺表、字段、权限和DML错误返回受控503，不再跳过正文后伪报synced。
4. 自建入口强制legacy来源并恢复原上下文；Bundle按同一显式业务schema取材并保存既有public Bundle。visit_index只验证既有表，不在该入口尝试DDL。
5. 检查/检验report_time和会诊record_time保留原输入时刻。材料提交后刷新异常保留材料，返回pending/安全错误；同病例可以刷新恢复，不需要重建。
6. normal服务器预检要求063并校验刷新表；acceptance附加相同刷新合同，原有规则验证专用表要求未删除。新候选PACKAGE明确database_migrations_required=true。

## 实际测试及护栏

本机定向：108通过、0失败、0跳过（包括新合同、API503、来源恢复、旧预检和迁移图）。pytest有既有Pydantic弃用/名称冲突警告。

```powershell
python -s -B apps/medqc-web/backend/scripts/run_qc_scheduler_tests.py --profile offline tests/unit/test_bundle_refresh_storage.py tests/unit/test_customer_test_record_storage_schema.py tests/unit/test_acceptance_startup.py tests/unit/test_linux_server_startup.py tests/unit/test_frontpage_qc_v2_migration_graph.py tests/unit/test_qc_sample_pools_router.py::test_create_test_record_should_forward_source_metadata tests/unit/test_test_case_evaluation_date.py tests/unit/test_bundle_refresh_lx0609_material_contract.py
```

Ruff检查通过，git diff --check通过；npm run check:encoding通过，npm run lint通过。lint自动修复产生的无关前端格式变动已逐一撤销；最终前端源码及同步服务目录相对Base零差异。未执行全量前端类型/单测，无前端修改。

GitHub原生PG16.15（Ubuntu24.04 runner），108项定向隔离测试通过（4.43秒）；27项真实PG测试全部通过、0失败、0跳过（11.68秒）。候选构建、SHA256及解压环境helper自检均通过。

CI证据：https://github.com/softjazzz/combined/actions/runs/42042889824 。该运行固定代码0126b3964，隔离PG使用本轮新目录、62997及medqc_sync_control_synthetic集群身份。SHA清单校验、模型deny与来源拒绝器全部生效。

另外自动触发的调度隔离和全量零模型质量门另见分支CI；本报告的108+27来自直接核实的定向任务，不能充当全量质量门数字。

PG16的运行命令见backend/scripts/run_bundle_refresh_pg_ci.sh及.github/workflows/business-refresh-repair.yml。它由独立网络命名空间运行：仅loopback62997；新建owned数据目录，核对cluster_name及data_directory后才加载业务模块。继承数据库/模型环境和dotenv读取均被隔离；业务代码不能连接本机5432、现场库、其他PG或真实HTTP。测试的模型deny计数断言0；独立CDM engine被替换为拒绝器，成功链要求未触发它。未访问患者数据、现场凭据、PDF、1026或同步服务运行目录。

测试角色分别为owned集群建库管理员、合成库DDL owner及非超级用户medqc_job_api。正常读写用后者，DDL实际拒绝；权限故障不会借用管理员执行运行路径。合成库中只按对象逐个授所需DML/序列权限，未授ALL TABLES/ALL SEQUENCES或DDL。

## PG矩阵证明范围

- 新建两表、public-only、qc-only、单表缺失跟随owner、两个历史owner不同：实际063迁移与真实jobs/failures生命周期。
- 双表同名（一空一非空／双方非空不同历史）阻断，062版本及旧内容不变；search_path变化仍解析到同一OID。
- 缺列、缺唯一键、缺默认、额外NOT NULL列、表DML/USAGE/序列权限、显式nextval序列、不可ON CONFLICT的延迟唯一约束及错误排序索引均拒绝。
- single/split各1例5份文书：入院、首程、检查、日常病程、会诊。实际三坐标、正文SHA256及记录/报告时刻与输入相同。运行Bundle含其应包含的临床文书；检查原始正文/ID/report_time在既有course域structured_context.documents中保存，不强行改变原Bundle格式。
- 进程内真实FastAPI端点+PG：缺材料表、缺SELECT、缺INSERT、缺记录时钟及注入中途DML错误返回503，pool/item及初始材料没有半提交。
- 提交后刷新异常：材料存在、pending/error真实，恢复同一病例不重复创建。
- 基线红灯：提取fa314c6c2的真实_ensure_tables函数执行，qc-only时复现public gate失败；新实现同场景成功。此前测试暴露的诊断表非正文字段和各文书时钟差异已按实际合同校准；没有改库或医疗规则凑绿。

## 必须保留的限制

1. PG环境为Ubuntu24 runner的原生PG16，不是现场Ubuntu22/PG16.13。使用明确声明的062合成结构，再执行真实063迁移；未宣称000001到063全历史空库迁移已验收。
2. 本轮没有现场对象/权限/历史DDL，未知存量不兼容会阻断，不能直接代替现场审核。063不自动DROP/ALTER历史表，downgrade明确拒绝删除审计数据。
3. 某些既有文书表只有submit_datetime，没有独立记录时刻列（如senior_course_record、discharge_record、surgery_record、presurg_discussion、surgery_inform_consent、anesthesia_record）。本入口遇到无法保存记录时刻的结构明确失败，不用提交时间冒充记录时间；本轮没有扩改临床表或同步合同。此类材料的全面接入仍需另外确认，不能宣称任意文书均ready。
4. 既有检查目录格式化使用结构化检查字段，不自动把仅粘贴的整段record_content改成检查所见。原始正文已在材料表和course域原始documents验证；未更改医学字段/判定，也未验证代理模型正式质控链。独立CDM0连接的验证不等于其业务链经过本次验收。
5. 初始扩大执行整个test_qc_sample_pools_router.py曾出现6失败：旧规则数量79与当前85等断言、以及离线环境阻断规则目录读取Git子进程。本轮不改规则集合/暂停规则口径；不把该批失败计入108定向通过，也未把全文件称为通过。有关规则模块相对Base未改动，未独立复跑完整Base文件。
6. 未执行现场迁移、授权、应用重启、包安装、真实API、真实质控或1026重跑。现场旧Key已暴露，应由持有人轮换；候选无Key、无患者资料。

## 候选自检与回退

构建入口scripts/build_refresh_repair_candidate.py限定9个运行文件、新迁移、说明、DIFF.patch、PACKAGE.json和内部CHECKSUMS.sha256。候选解压后运行python -B self-check.py，逐文件校验SHA256、全部运行Python语法并从包内导入两个新helper，不访问工作树外隐式资源、DB或网络；既有Base应用及SQLAlchemy依赖是明确前置，不包含在此源码候选中。

完整正式Linux升级包应在复审后另行制作，不把源码覆盖ZIP当成直接部署授权。未来预检、批准后迁移/逐对象授权及保留审计表的回退步骤见主方案。代码回退不自动撤销063，更不覆盖新业务结果或清理历史。
