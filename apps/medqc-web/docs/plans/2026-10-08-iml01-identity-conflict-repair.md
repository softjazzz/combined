# IML-01 检查检验台账身份冲突修复

## 范围与固定证据

修复工作树 `F:/MedQC-worktrees/qc-fix-ledger-20261008`，基线 `6930540f27e9c279241d35ac05d1c1c6e9134f82`。首轮生产改动为 `backend/app/services/luxian_0609/handbook_exam_lab.py`；独立复核后二次修订另获授权在 `source_evidence_reader.py` 只补三个指定身份字段白名单；新增专属回归文件 `backend/tests/unit/test_luxian_0609_handbook_identity_conflict_closure.py`。不改投影执行器、Renderer、Finalizer、保存层、规则目录和启用范围。

继承审计交接 `docs/acceptance/engine-audit-20261008/imaging-laboratory.md` 的 IML-01 及冻结 `expected.json`（SHA256 `907902ea92c3c7bdc9e1724a2d322b80bec35f7d686aaa70a3af5768a5bc10c3`）。四个确认反例为 CT主/DR报告、DR主/CT报告、CT主/无名称但超声科报告、培养主/血常规报告。新增测试给影像反例补同键CT医嘱与合法病程，验证两条台账消费者；不将取消主记录与正式报告的状态争议 IML-D01 纳入关闭。

业务范围按正式目录及 2026-09-22 手册扩展实施证明确认：06-01-03、06-03-02 为手册新增报告完整性规则，不套用原001–049条款；06-01-01消费共用台账。缺关联交付资料不足，不定性临床漏报。

## 身份设计与权威边界

原台账只需合并行中任一名称属于目标，就把同键非目标报告作为正式报告。修复先保留目标候选事件全部主/报告/医嘱引用，再核查身份；明确反证或混合身份设置 `association_resolved=False`。两个消费者已有的关联缺口分支负责交付，06-01-01在该事件上停止语义调用。不是删除冲突行后默认合规。

不新增第二套非目标词表。直接复用 `exam_lab_fact_extraction` 的 `_EXPLICIT_NON_TARGET_EXAM_PATTERN` 与 `_EXPLICIT_NON_TARGET_CULTURE_PATTERN`；影像耗材口径复用本模块已有 `_SUPPLY`。该模块依赖 evidence_material、source_evidence_reader、imaging_report_scope、exam_lab_course_time，均不回导 handbook，静态依赖未形成循环。

逐权威字段作 target / non_target / unknown 判定。影像独立核查 modality、exam_type、order_name、exam_name、exam_item_name、item_name，名称/类型为空才回退 performed_dept。培养核查 lab_type、test_type、order_name、labtest_subject；主记录保留 lab_item_name/item_name 既有来源，报告下游 lab_item_name/item_name 不参与身份裁定。独立字段 DR 反证不能被另一字段 CT 名称覆盖。只有目标或只有明确非目标才能确定相应身份；兼含两者属于 unknown，不能确认为同一目标，保留关联缺口。

正文、结果和诊断建议不参与身份核查。没有已识别身份的项目、菌名和药敏明细本身不提供目标或非目标证明；在同键已有明确目标且没有反证时，继承既有未命名明细合同。未知行永远不能清除同键其他行的明确反证，也不能仅凭正文中的 CT 建议创建目标事件。

不扩大 `imaging_report_scope` 的纯引导豁免；报告完整性继续允许有权威CT模态的引导穿刺/CTA项目，并保护既有精确身份 `CT引导下操作`；不声称所有含 CT/超声的复合项目都合法。模糊的 CT与超声联合名称、血常规建议培养名称保持关联缺口。共享投影现有整串混合身份处理仍在原所有者范围内，本次不改变其语义。

## 验证记录

隔离 runner 继承原审计基础设施，位于未提交 `.tmp/iml01/run_tests.py`。使用 `--confcutdir=tests/unit`、禁缓存与字节码；dotenv替换及审计钩子阻止 `.env`、外网和数据库访问，asyncio只允许本地socketpair控制通道。SQLite验证仅使用 `sqlite://` 内存库。没有真实病例、PG、网络或真实模型调用。

修复前新增18项测试：**8 failed / 10 passed**，正式归约状态为 compliant，触发精确的 data_gap 预期失败。初版修复新增22项通过、原五组保护集 **364 passed / 1 warning / 6.46s**；后续身份设计修订后新增35项及既有342项保护共 **377 passed / 1 warning / 9.08s**。最终日志为 `.tmp/iml01/green-final.txt`，红测日志为 `.tmp/iml01/red.txt`。最终覆盖正式typed入口→Reducer→Finalizer和CT/培养内存SQLite保存/安全回读；四个确认反例均资料不足、保留主/报告/医嘱引用，固定客户端调用与Token为0。正常CT正例固定客户端1次，正常培养0次。06-01-01沿用 `required_field_missing` 原因码，报告规则为 `association_failed`，两者事实均为 `association_unresolved`。

针对两个Python文件的 `python -m ruff check` 已通过；`git diff --check` 已通过。提交前门禁已尝试：暂存前 `npm run check:encoding` 仅报告无暂存文本，不能作为本次编码验收；lint、type-check、test:unit分别因F树缺 eslint、vue-tsc、vitest 未执行成功。后续经协调者授权，在F任务树建Junction只读复用F集成树现有依赖，未安装依赖或修改D盘依赖。`npm run lint -- --no-fix` 已通过，0 errors / 1214 warnings，原有前端警告不作本问题改动。暂存后三个本任务文本的 `npm run check:encoding` 通过（3 text files scanned）。

F树初始没有 node*modules 和配置的 `.husky/*/pre-commit`生成入口；已获协调者授权只读复用F集成树依赖，并复制D主树标准`.husky/\_` 启动器到F本树，未改D文件或common配置。提交使用本树标准Husky钩子，不设置 HUSKY=0、不更改钩子配置；实际钩子结果随提交回执交付。共享重型验证期间一次PowerShell启动因内存不足失败；测试槽释放后最终聚焦验证成功。完整前端type-check/test:unit由IML02唯一执行，避免重复全量和资源竞争；本报告未收到其最终结果，不声称完整前端门禁通过。

## 独立复核阻断与二次修订

首轮提交 `11211cc42becaa03d0f5b36056bdc3e17a31842a` 的独立冻结文件位于 `F:/MedQC-worktrees/review-artifacts/iml01-closure/expected.json`（SHA256 `dbda7a2d78a57e7114ec72879b4300c7a682ae8fa2da35335e737e2fbf2ac05c`），AST轻量复核16例为13通过、3偏离。原冻结预期及产物未覆盖。确认阻断两项：培养的 `生化鉴定` 报告明细被“生化”反证误排；CT主项与同键 `modality=US` 报告仍合规。另一个 CT/MRI 同键不一致预期由审计者补正为联合事件合同争议，不将其冒充已确认P1。

培养修订按来源角色限定：调用方明确传入报告引用集合，只将报告下游 `item_name/lab_item_name` 排除出整个检验身份裁定；主项只有 `item_name=血培养` 仍按原口径保留候选。独立的报告 `labtest_subject/lab_type/test_type` 反证继续生效。避免用“生化鉴定”等自然语言白名单逐项开例外。

结构化 `modality/exam_type` 整值代码归一化 CT、MR/MRI、US、DR；MR/MRI为同义规范值，US/DR为明确非目标。分类“介入/其他”与未知代码不当模态反证。本文不宣称完整影像代码字典覆盖。不新增 CT/MRI 差异判定或新的 `^` 联合豁免：现有业务键归并和 `resolve_exam_master_order_ids` 的显式多医嘱关联保护保留；尚未找到单一普通exam_id跨CT/MRI联合报告的批准合同，原独立预期继续开放。

默认字段链已核对：`source_evidence_reader._NATIVE_SOURCE_FIELDS` 的两影像来源原未列modality，`_SNAPSHOT_SOURCE_FIELDS`继承该表；默认 `read_luxian_0609_snapshot_source_rows` 仅对实际存在的批准字段形成SELECT，再生成 `SnapshotSourceRows`；`evidence_snapshot_provider.build_luxian_0609_evidence_read_session` 默认使用该reader，写入材料仓，台账才读取材料。报告labtest_subject原也不在检验明细白名单。首轮typed测试自行注入字段，不能证明这条默认SQL链已读取模态反证。

协调者批准的源扩展仅3行：exam_master/exam_item_report各补modality，labtest_item_report补labtest_subject；继续复用列存在检查，不加查询、迁移或正文范围。准备的5项默认reader→正式snapshot→ledger测试仅模拟数据库列目录/SELECT结果，既测试字段存在时保留反证，也测试缺列时不猜字段、不认定已完成模态核查；有明确主项而报告身份字段缺列时，既有未命名明细合同保留，不能将此对照声称冲突目标已经验证。

本次新增13项（确认阻断、MR/MRI别名、主项item_name来源、默认读链及查询次数合同），新增文件累计48项。红测入口 `.tmp/iml01/run_revision_red.py` 在新进程中装载11211cc42固定的台账/来源reader源码，继承原离线隔离，不替换生产文件。固定11211cc42代码运行当前48项：**7 failed / 41 passed / 1 warning / 2.28s**；当前48项加既有342项保护：**390 passed / 1 warning / 4.94s**。有列时US/普通检验报告身份反证保留到材料并得到data_gap；缺列时SELECT与材料均不含该字段，既有未命名明细合同保留；培养生化鉴定明细正常。查询合同在父提交和当前均通过：主项1、报告1、同一医嘱物理表的既有通用与检查检验过滤来源各1，共4次，字段扩展未增查询。

首轮连同完整provider文件为489 passed / 6 failed：4项为本次探针错误预期3次查询，已按真实既有来源合同修正；2项为既有目录漂移。既有 `test_all_79_registered_rules_query_each_bounded_source_once_and_never_query_legacy` 与 `test_bloodtrans_snapshot_projection_has_explicit_identity_version` 使用相同两个nodeid分别在固定11211cc42台账/reader及当前代码复测，均2 failed，原因分别为79预期/实际85与v33预期/实际v34。没有修改这两个既有测试。该基线失败单列，不宣称全部provider保护通过。

日志保留在 `.tmp/iml01/`：`red-revision-final.txt` SHA256 `F54A221F49DB7DD4E5F3285C9CF9B173037DC3E22696DFC5B893639FC4B0C9D7`；`green-revision-final.txt` SHA256 `5A9B22508B9D0A8D24DD9C079F90DFEEDB390F3F5FB84DDC53939E8D07FE8ED0`；旧断言父对照 `provider-baseline-112.txt` SHA256 `CC0AF74C3B366212169D4E35EB756E74A649E626C181084D7860E1E93151DA23`，当前对照 `provider-current.txt` SHA256 `04B1AE9C769648CAF303D252A35CF11E7A6AE4A8590E697B3F02EAB078775ECD`。原首轮红绿日志、独立冻结文件和原112提交保留。默认SQL验证是列目录及返回值合成模拟，未连接PG，不推断真实数据库已同步这些可选字段。三Python文件Ruff及diff检查通过。二次提交前staged encoding扫描4个文本通过，`npm run lint -- --no-fix` 再次通过（0 errors / 1214既有warnings；日志`.tmp/iml01/lint-revision.txt`）。依协调者资源调度，本次仍不重复完整前端type-check/test:unit，由IML02唯一负责；本文未取得该门禁结果，未宣称通过。实际Husky钩子执行结果随提交回执披露。

## 未关闭边界

非目标识别仍受既有权威模式覆盖限制，未识别身份保留unknown，不宣称全面类型识别。合成正式链及内存SQLite不能替代真实同步资料、真实模型稳定性、客户保存/API/浏览器验收。本次未处理 IML-D01 的取消/发布状态争议，也未扩大合法引导例外。修复完成后仍须由原审计者在固定修复SHA上独立复核。
