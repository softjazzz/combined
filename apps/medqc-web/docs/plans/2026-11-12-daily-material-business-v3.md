# 日常病程补充业务适配：实现与本机验证

状态：本地候选，独立复审中；没有推送、合并、部署或现场联验。基线 `06c2fd4fa`，同步固定 `d7dc325b7dee82dcc2215b9b68dfbb797f57dea5`，判定合同 `daily-material-r2-v3`。

## 边界与入口

`daily_material_readonly.py` 随业务交付固定合同的19个函数/类及两张固定目标投影。没有连接工厂、poll/reconcile/set_policy/publish/migration。源定义SHA256随模块保存，合成测试校验；独立审阅已逐定义AST与原固定源比对。仅 stdlib 和调用者 DBAPI，无外部源码路径依赖。

`daily_material_projection.py` 为唯一业务选择 owner。SQLAlchemy 当前 connection 的 driver_connection 只借用；不调用 engine.raw_connection，不提交、回滚或关闭借用连接。先通过 cache native三键对应的 case_binding 唯一绑定批准 policy，校验 policy.native_cases，再读同事务manifest；canonical三键允许与native不同。完整批准policy、native绑定与reader版本随manifest冻结。RR/read-only/独立数据库校验失败即拒绝。

开关 `QC_DAILY_MATERIAL_ENABLED=true` 才启用，默认关闭，本次不改env。任务 capture 在原同一个 RR 事务开始后读取一次manifest；普通 current view 在临时同RR上下文中组装。独立 CDM 未配置、绑定不唯一、错误事务、未捕获上下文均拒绝静默回退。PDF物化、旧任务无扩展字段按既有协议。

| 入口 | 落点与行为 |
| --- | --- |
| Bundle/目录 | assembly正式事实仅selected且rule_usable；current_view目录保留全部版本、冲突和待核状态 |
| Snapshot/native Provider | source_evidence_reader沿固定批准字段投影，另带版本定位metadata；原raw/native字段留完整manifest |
| course_round_timeline | daily用同owner，senior仍原批准源 |
| 程序化证据 | capture_programmatic_sources同owner；programmatic_timeline透传material_scope，目录daily不能混入正式集合 |
| 详情/摘要/HTML | detail_service、emr_view摘要保留版本身份；full doc使用完整doc_key，不以同号原document_id猜版本 |
| 客户证据定位 | MaterialStore文书ref包含版本元数据的行摘要；enrichment将匹配版本key交给既有source_document_id签名链；HTML使用同key生成source_ref |
| UI | EMRViewer仅版本文书传doc_key，旧文书仍传原id |

## 供给scope与实际判定

查询complete/truncated含义保持不变，空成功查询可为complete。独立material_scope在SnapshotSourceRows、文件编码、MaterialStore身份中固定；Store.scope从自身冻结材料取得，不查当前全局上下文。can_judge_clinical_absence严格为true才能作新daily全集缺失推断；旧scope缺省保持旧协议。未在保存层或全族注册表统一改状态。

| 消费者 | 新供给前提 | 保留的可靠证据 |
| --- | --- | --- |
| basic首次查房、007/008/009、旧programmatic round/稳定间隔 | 未找到、超时首次、缺天/间隔需完整供给 | 已有时限内查房 |
| handbook CT、native exam/lab、record check | 每事件无记录、超时且可能有遗漏、空窗口需scope；批次和恢复保留scope | 已观察到的满足/独立事件事实 |
| 输血047、肿瘤化疗 | 日常病程中缺评价/缺处置推断需scope | 已确认评价/明确事件不一致 |
| 正式会诊episode和旧会诊 | daily候选保留，source_complete_keys合取scope | 可定位会诊执行候选 |
| 手术急诊例外 | 无阳性且未知供给为unknown | 阳性急诊介入例外 |
| 预防抗菌延长 | 24–48h缺理由需scope | >48h已确定时长违规 |
| 扩展054/055/057、疑难、术后04-05-01、出院前/许可、交接、074 | 逐缺失分支合取scope | 已有满足记录/独立证据优先；不扩大至仅senior的04-05-02、仅first_course的077或植入025可选daily |

## 冻结、故障与历史

复用 `case-material-v1` 文件协议，与daily判定v3分别版本化。完整manifest、confirmation_basis、confirmation/proof、原文、native_fields、选择与publication/coverage字段均进入原不可变对象；0与false不丢失。先原子写内容对象，再原子建立任务引用，再由既有任务执行路径激活；捕获事务已释放。对象写完引用失败允许孤立对象但不执行；重试必须找到原root引用，缺失/损坏/绑定不符拒绝重新查询。引用已建立后的失败重试读原对象。并发原子引用、损坏和任务顺序复用原快照36例保护。新cache等价材料只影响新任务选择，旧任务仍回放原版本。

## 验证记录

全部后端从 backend 运行 `python -B scripts/run_pr8_offline_tests.py <下列文件> -p no:cacheprovider`，入口屏蔽env/网络。只合成材料、固定应答和纯程序判定，无真实模型/规则HTTP服务/现场任务。各组有交集，不合计为总验收数量。

- 新 `test_daily_material_projection.py` 与 `test_daily_material_scope_execution.py`、原 `test_case_material_snapshot.py`：77 passed/4 warnings，exit 0；随后新增4项只读漂移/错误事务/缺policy保护，其中源hash测试修正decorator计入方式后单测1 passed，其余21例前一轮通过。产品源码未因夹具修正变更。
- `test_luxian_0609_evidence_snapshot_provider.py test_bundle_emr_view.py test_current_document_view.py test_emr_render_performance_contract.py`：173 passed，exit 0。
- `test_luxian_0609_native_basic_timeliness.py test_luxian_0609_course_quality_freeze.py test_luxian_0609_native_extended_document_execution.py test_luxian_0609_native_exam_lab_execution.py test_luxian_0609_native_tumor_pathology_execution.py`：896 passed，exit 0。
- 补充程序化/检查完整性/会诊/手术/输血定向集合798例：首次788 passed/10 failed，失败为旧手术RowsOnly替身无scope方法；旧协议兼容修复后 `test_luxian_0609_native_surgery_document_execution.py test_sample_programmatic_evidence.py test_daily_material_scope_execution.py` 186 passed，exit 0。
- `node node_modules/vitest/vitest.mjs run tests/unit/components/EMRViewer.spec.ts --cache=false`：9 passed，exit 0。只复用同package-lock SHA256的既有工具依赖junction，无全局安装。旧版本Vitest不支持试用的--configLoader参数，去掉后标准命令成功。已有Browserslist陈旧提示，未更新依赖。
- `git diff --check`：exit 0。warnings为已有Pydantic/Starlette弃用提示。

独立真实PG16.15验证：新tempcluster，随机数据库 `delivery_cdm_586a331d1938`，高端口61150，已停止且pid移除。真实SQLAlchemy RR先读正文+manifest，另一连接修改目标，同RR仍同版本，新RR fresh=false；借用连接之后仍可SELECT；native与canonical不同正确绑定。fixture为合成已发布target+receipt+material，不声称调用实际同步publish。结果记录：`C:/Users/Coldplay/AppData/Local/Temp/daily-business-owned-pg-chx8_fu1/result.json`；脚本：`C:/Users/Coldplay/AppData/Local/Temp/MedQC-daily-business-pg-review/probe_rr.py`。它们仅验证证据，不是产品运行依赖。

## 最小权限草案（未执行）

以下仅新增读取模块所需权限；原CDM其余批准业务字段权限继续单独管理。不得用表级ALL替代列授权，不授写入、CREATE、SET ROLE或同步管理能力；部署者应核对实际角色名及既有直接/继承权限。

```sql
GRANT USAGE ON SCHEMA sync_material, sync_delivery, cdm TO business_reader;
GRANT SELECT (case_id, source_namespace, native_case_hash) ON sync_material.case_binding TO business_reader;
GRANT SELECT (case_id, policy_hash) ON sync_material.case_policy TO business_reader;
GRANT SELECT (policy_hash, policy_json) ON sync_material.policy_version TO business_reader;
GRANT SELECT (source_namespace, native_case_hash, version_id) ON sync_material.document_head TO business_reader;
GRANT SELECT (version_id, material_json) ON sync_material.document_version TO business_reader;
GRANT SELECT (case_id, source_namespace, coverage_json) ON sync_material.coverage TO business_reader;
GRANT SELECT (case_id, decision_id) ON sync_material.selection_head TO business_reader;
GRANT SELECT (decision_id, result_json) ON sync_material.decision TO business_reader;
GRANT SELECT (generation, mapping_hash, activation, interface_name, source_epoch, source_key_hash) ON sync_delivery.receipt TO business_reader;
GRANT SELECT (interface_name, source_epoch, mapping_hash, activation) ON sync_delivery.contract TO business_reader;
GRANT SELECT (institute_id, patient_id, visit_id, visit_type, name, sex, inpat_no, mr_no, document_id, document_title, document_status, submitter, submitter_id, submit_datetime, record_content, last_modifier, last_modifier_id, last_modified_datetime, update_time, record_datetime, age_year, physician_sign, physician_sign_datetime) ON cdm.daily_course_record TO business_reader;
GRANT SELECT (institute_id, patient_id, visit_id, document_id, document_title, record_content, record_time, submit_time, modified_time, source_status, source_payload) ON sync_material.clinical_daily_current TO business_reader;
```

仍需现场批准身份/类型/等价/覆盖policy、账号权限核对、捕获窗口、固定同步版本部署及只读联验；本次没有连接既有数据库、源接口或服务器，没有重跑27份/1026，未执行GRANT或开启部署开关。本地通过不能替代现场上线验收。


## 独立复审补修（60085728d之后）

固定本地工作树 `D:/MedQC-worktrees/daily-material-business-v3-20261112`，分支 `codex/daily-material-business-v3-20261112`。基线06c2fd4fa包含尚未合入PR57的反馈安全补修，本任务不修改、推送或合并PR57。

- 源状态只按冻结business_binding.policy.status_rules解释：明确valid才可进入正式daily事实；cancelled排除；未映射或当前不支持的意义待核并阻断全集缺失推断，不猜Save等原字符串，不把SEMANTICS_APPROVED本身当作有效。完整原判定、field_availability、原状态仍留目录/快照。真实basic首次查房反例验证未知/取消不能成为合规阳性，valid阳性及旁侧独立valid证据保留。
- 同RR追加固定23列base观察，与原items.target_payload作typed canonical精确比较；未匹配当前行进入business_base_inventory，只用于目录，不进入原selection/rule集合。观察身份为内容寻址observed版本，source_revision=UNCONFIRMED，不冒充发布版本。无prior也可见正文，历史任务观察内容仍不可变。
- 全局开关启用但病例零binding：正式捕获仍拒绝；仅live目录捕获MissingDailyBinding，显示同连接base观察及“补充来源尚未批准关联”。多binding、错绑、坏policy、缺权不降级，不自动改用旧规则输入。
- 目录摘要与全文metadata加入安全来源/状态/是否正式/覆盖待核提示，不重复发送raw证明。EMRViewer真实Vue组件模板挂载测试验证全文顶部提示；受控workspace空目录转fallback也保留提示。没有运行浏览器截图或现场页面，本轮UI证据是Vitest+jsdom组件DOM。

补修必要验证：backend同禁env/network入口，`test_daily_material_projection.py test_daily_material_scope_execution.py test_bundle_emr_view.py test_current_document_view.py test_emr_render_performance_contract.py` 116 passed、3既有warnings、exit0。EMRViewer 11 passed、RecordDetailWorkspace.panel 4 passed，均exit0。前者新增两例先RED再GREEN。父级在60085728d独立81 passed；不把它当作补修后全量复跑。

新增读层后独立PG再次验证通过：PG16.15，高端口63147，数据库delivery_cdm_c554c088a96f，已finally停止。结果`C:/Users/Coldplay/AppData/Local/Temp/daily-business-owned-pg-0nzx1skg/result.json`；同一外部probe_rr.py已补assert：正式project_rows两份、同RR观察集合不变、新RR变化正文仅目录/不正式、无selection_head时base可见/正式空。JSON未逐项列出新增assert，具体证据在脚本。依然是保真已发布fixture，不是实际同步发布。

## 后续只读预检清单（仅准备，未执行）

1. 由负责人确认目标独立CDM、捕获窗口、实际角色与CONNECT目标库权限，逐列核对上述SELECT草案；检查角色继承、对象所有权及组合后有效权限，确认无写权/建库建schema能力/SET ROLE绕过。此清单不执行GRANT，也不开启开关。
2. 同步方须提供批准的身份、类型、status_rules有效/无效语义与覆盖范围；未知状态意义不能成为正式事实。明确补充状态字段的批准语义，不以字符串外观推断。
3. 快照目录置于release目录外；核对应用账号读写权限、同任务实例共享路径、备份与原子恢复流程，验证内容对象及任务引用一起恢复、绑定一致；缺失/损坏不能回查最新替代。
4. 获准后才进行现场只读联验：批准病例的同RR目标/manifest/目录一致性、实际字段权限、冻结后重试和历史定位。无关联普通病例应显示基础观察和未批准提示；新正式执行仍要求有效绑定。当前没有创建现场任务或启用开关。


## 独立Bundle入口闭合（ac8e8b201之后）

实际调用包括clinical_completeness→load_or_assemble_scene_bundle，以及CaseSetSyncService→refresh_all_bundle_variants_for_rows。公共scene/domain组装owner和load/cache入口建立严格的daily上下文；已有捕获/冻结上下文复用并校验身份，底层_select_records不创建新连接。直接domain loader/index/render也在manifest存在时从同材料组装，不返回旧缓存；旧任务无manifest继续旧协议。无外部上下文却传入的material_snapshot不复用，新manifest的daily行始终由owner投影。

统一刷新和domain-only刷新每病例一个上下文覆盖其variants，不能跨病例复用。捕获拒绝仅使该病例的variants计为failed，并沿原scene失败记录；continue_on_error继续后续病例，不把拒绝变成空材料成功。continue_on_error=false仍显式失败。正式Bundle不允许零binding目录降级，只有current_view明确allow_unbound_view=True。

元数据读取同样复用recording.connection：_get_table_columns在受控录制中inspect当前SQLAlchemy连接并缓存本次列，不inspect engine或使用跨请求元数据缓存；历史缺列仍拒绝。

新增独立scene/domain、直接loader/index/render、每病例多variant、列inspect同连接、旧临时snapshot、单病例捕获失败不影响另一病例共10例。前6例和批次失败2例先RED再GREEN。必要组 `test_daily_material_projection.py test_bundle_refresh_storage.py test_bundle_refresh_lx0609_material_contract.py test_domain_bundle_assembly.py test_current_document_view.py` 94 passed/3既有warnings/exit0；其后仅批次隔离与相关新入口10例通过。没有运行实际刷新任务、没有写既有库，upsert和失败记录均测试替身。


补充限制：隔离PG使用自有临时集群测试账号及READ ONLY事务，不是最小列授权角色验收。SQLAlchemy连接所有权保留不等于数据库对象所有权/继承角色只读验收；权限草案来自实际SQL静态提取，仍需后续获准的只读预检，本轮不执行GRANT。全局daily开关开启时，PDF短路不得清空已有material_snapshot；此边界新增一例先失败再修复通过。
