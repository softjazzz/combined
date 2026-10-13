# 六条发布范围定向补证

固定源码：`4e51e55406fcec8b2940f2d16244ca3062db6115`。仅0609指定6条；原86矩阵冻结。本轮6条定向源码阅读已补齐，未运行测试、HTTP、worker、模型或PG，未修改生产/目录/台账，不构成6条工程或医学验收通过。

单病历/批次在本报告指 `workspace/batch-jobs` 的1/多 `record_refs`；样本指customer `sample-pools/run`。不把所有诊断/debug API列为已覆盖。

| 规则 | 当前发布状态（实际核对） | 默认客户交付/医学执行 | 显式选择 | 本轮结论 |
|---|---|---|---|---|
| LX0609-05-01-01 | active / pending_definition / default | 交付暂停 / 不医学执行 | workspace/workspace/sample仅暂停均422；混合交付pause | 固定源码范围证据已补；当前运行未验 |
| LX0609-05-01-04 | active / pending_definition / default | 交付暂停 / 不医学执行 | workspace/workspace/sample仅暂停均422；混合交付pause | 固定源码范围证据已补；当前运行未验 |
| LX0609-05-03-01 | active / pending_definition / default | 交付暂停 / 不医学执行 | workspace/workspace/sample仅暂停均422；混合交付pause | 固定源码范围证据已补；当前运行未验 |
| LX0609-06-03-01 | pending_definition / pending_definition / default | 不进交付 / 不执行 | 直接拒绝；sample混合路径待复现 | 固定源码范围证据已补；当前运行未验 |
| LX0609-07-04-02 | active / pending_definition / default | 交付暂停 / 不医学执行 | workspace/workspace/sample仅暂停均422；混合交付pause | 固定源码范围证据已补；当前运行未验 |
| LX0609-08-01-05 | active / phase_1_target / acceptance_only | 默认排除 / 不执行 | workspace422；仅customer sample显式可计划 | 固定源码范围证据已补；当前运行未验 |

已核对额外拒绝分支：普通workspace仅选暂停项时active为空，`qc_sichuan.py:2009–2010`返回422；不是创建后生成只暂停任务。

登记、阶段和发布范围是三个不同维度。4条已注册pending保留可选交付并生成政策暂停；06-03-01未注册，不能同样生成正常暂停结果；08-01-05仍active/phase_target，但入口默认过滤、普通workspace显式422。其内部可执行不等于默认发布。

## 固定调用路径

目录/暂停：master→active catalog→customer ruleset→phase partition→package→phase result：

- [luxian_0609_rule_master.py:58](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/luxian_0609_rule_master.py:58)（固定行58–107）：active/pending与release_scope正交；acceptance_only要求active+phase_target。
- [luxian_0609_rule_catalog.py:23](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/luxian_0609_rule_catalog.py:23)（固定行23–60）：执行wrapper严格投影implementation_status=active。
- [sample_validation_rule_sets.py:307](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/sample_validation_rule_sets.py:307)（固定行307–335）：客户可选交付目录仅registered且非客户排除项；此时尚含pending及acceptance_only。
- [phase_scope.py:168](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/luxian_0609/phase_scope.py:168)（固定行168–192）：已注册选项拆为phase_target与withheld；未注册拒绝。
- [native_package.py:278](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/luxian_0609/native_package.py:278)（固定行278–327）：inventory来自active wrappers，package选中pending但不分发医学批次。
- [native_package.py:525](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/luxian_0609/native_package.py:525)（固定行525–536）：公开包入口仅扩展可执行选项，pending不转旧执行ID。
- [phase_scope.py:121](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/luxian_0609/phase_scope.py:121)（固定行121–165）：注册pending生成not_executed/is_compliant=None/facts={}/evidence=[]及受控原因。
- [execution.py:384](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/luxian_0609/execution.py:384)（固定行384–387）：phase gate结果生成。
- [execution.py:891](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/luxian_0609/execution.py:891)（固定行891–891）：暂停结果纳入native_results。
- [canonical_result_finalizer.py:482](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/luxian_0609/canonical_result_finalizer.py:482)（固定行482–494）：发布暂停合同允许无公开facts，不伪造事实。

历史：完整master身份→合法Envelope→原保存冻结范围/展示快照→受限retry：

- [custom_qc_workspace_service.py:146](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/custom_qc_workspace_service.py:146)（固定行146–155）：历史身份使用完整master，含暂停、未注册和acceptance_only。
- [canonical_result_store.py:117](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/qc_workspace/canonical_result_store.py:117)（固定行117–154）：已知身份仍需唯一身份/状态/合规语义一致，非任意旧结果通行。
- [custom_qc_workspace_service.py:3526](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/custom_qc_workspace_service.py:3526)（固定行3526–3580）：latest-result校验Envelope及全master身份；只过滤客户明确排除集，不因当前phase/release_scope删这6条。
- [phase_scope.py:203](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/luxian_0609/phase_scope.py:203)（固定行203–224）：重试从保存scoped或旧rule_ids+paused+gate恢复；缺计划拒绝并要求新建。
- [custom_qc_workspace_service.py:4493](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/custom_qc_workspace_service.py:4493)（固定行4493–4505）：重试禁止超原冻结范围。
- [sichuan_workspace_batch_worker.py:1324](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/sichuan_workspace_batch_worker.py:1324)（固定行1324–1345）：领取任务恢复冻结范围，失败规则重试不得扩范围。

历史链只证明范围身份与计划规则：不因暂停/acceptance/取消注册把合法保存身份改成未知，也不以当前default猜旧范围。合法Envelope的schema、状态、事实和完整性仍必须满足。没有读取真实历史病例，也没有当前每条历史API执行证明。

## 每条当前应验、已有证据与剩余缺口

### LX0609-05-01-01 — I类、II类切口手术预防使用抗菌药物超过24小时，特殊情况超过48小时

当前master位于 [luxian_0609_rule_master_v1.json:238](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/data/luxian_0609_rule_master_v1.json:238)，JSON `/rules/27`。暂停原因：`antimicrobial_dictionary_missing`。

当前发布范围应满足：

- 目录保持已注册且phase=pending，不把暂停解释为医学合规或不适用。
- 默认/显式任务不得把该条交给正式医学执行器、亦不得转旧执行ID绕过暂停。
- 合法交付项保留该ID及受控pending原因；not_executed、null合规、空facts/evidence，不产生临床data_gap/non_compliant。
- 原任务计划与合法历史身份可恢复；重试不得用当前默认范围扩大任务。

已有证据（均保留层次）：

- 旧组报告：[JSON](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/tumor-pathology.json)，基线 `7b894dc84491b7b72eb096de58fe61f772cc0080`；只继承该行限定结果，不把族总测试数算该条通过。
- 已有测试源码 [test_execution_catalog_is_exactly_the_active_master_projection](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_rule_master.py:160)：注册目录必须精确等active master投影。限制：本轮只读测试源码，不声明当前运行通过；本轮未运行。
- 已有测试源码 [test_phase_scope_is_a_read_only_master_projection](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:162)：phase/registered来自同一master，非另造列表。限制：未执行；本轮未运行。
- 已有测试源码 [test_customer_delivery_excludes_registration_only_handbook_rules](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:224)：默认客户交付为registered非excluded；06-03-01不可选且partition拒绝。限制：不覆盖06-03-01混合sample入口创建；本轮未运行。
- 已有测试源码 [test_defaults_freeze_scope](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/integration/test_luxian_0609_release_scope.py:81)：workspace单/批与sample默认过滤acceptance，冻结旧计划，worker/Canonical读取。限制：fixture为合成空材料+SQLite；源码可定位，本轮未执行，不证明医学内容/正式环境；本轮未运行。
- 已有测试源码 [test_public_package_entry_never_expands_pending_rules_to_legacy_execution_ids](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_native_package.py:862)：参数明确包含该条，公开入口暂停项不得转旧执行ID。限制：源码存在；无本轮执行结论；本轮未运行。

剩余证据与启用前条件：

- 05-01-01不在现有empty_evidence_contract直接参数内；no-legacy参数有该条 下一步：将05-01-01加入冻结的纯phase结果合成矩阵，核验antimicrobial_dictionary_missing与全部空值；不调用医学执行器。
- 固定4e51下该条默认/显式（仅暂停拒绝、与active混合交付）到保存/读取/重试的独立合成消费证据尚未定位 下一步：复用已有合成SQLite入口fixture补选项范围与暂停结果；历史限定结果按原SHA继承，不将源码断言算新pass。
- 冻结院方抗菌药字典（名称/编码/预防与治疗用途映射）及24/48小时例外业务口径，再核实切口级别、实际给药/起止时间与事件关联；当前阶段不要求强行临床启用。 下一步：保留暂停，启用另需用户授权/客户合同；不追要真实模型来强行关闭当前暂停范围。

### LX0609-05-01-04 — 接受两个或两个以上重点抗菌药物，使用前未完善病原学检查

当前master位于 [luxian_0609_rule_master_v1.json:468](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/data/luxian_0609_rule_master_v1.json:468)，JSON `/rules/55`。暂停原因：`key_antimicrobial_catalog_missing`。

当前发布范围应满足：

- 目录保持已注册且phase=pending，不把暂停解释为医学合规或不适用。
- 默认/显式任务不得把该条交给正式医学执行器、亦不得转旧执行ID绕过暂停。
- 合法交付项保留该ID及受控pending原因；not_executed、null合规、空facts/evidence，不产生临床data_gap/non_compliant。
- 原任务计划与合法历史身份可恢复；重试不得用当前默认范围扩大任务。

已有证据（均保留层次）：

- 旧组报告：[JSON](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/tumor-pathology.json)，基线 `7b894dc84491b7b72eb096de58fe61f772cc0080`；只继承该行限定结果，不把族总测试数算该条通过。
- 已有测试源码 [test_execution_catalog_is_exactly_the_active_master_projection](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_rule_master.py:160)：注册目录必须精确等active master投影。限制：本轮只读测试源码，不声明当前运行通过；本轮未运行。
- 已有测试源码 [test_phase_scope_is_a_read_only_master_projection](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:162)：phase/registered来自同一master，非另造列表。限制：未执行；本轮未运行。
- 已有测试源码 [test_customer_delivery_excludes_registration_only_handbook_rules](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:224)：默认客户交付为registered非excluded；06-03-01不可选且partition拒绝。限制：不覆盖06-03-01混合sample入口创建；本轮未运行。
- 已有测试源码 [test_defaults_freeze_scope](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/integration/test_luxian_0609_release_scope.py:81)：workspace单/批与sample默认过滤acceptance，冻结旧计划，worker/Canonical读取。限制：fixture为合成空材料+SQLite；源码可定位，本轮未执行，不证明医学内容/正式环境；本轮未运行。
- 已有测试源码 [test_public_package_entry_never_expands_pending_rules_to_legacy_execution_ids](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_native_package.py:862)：参数明确包含该条，公开入口暂停项不得转旧执行ID。限制：源码存在；无本轮执行结论；本轮未运行。
- 已有测试源码 [test_pending_definition_result_has_one_empty_evidence_contract](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:143)：参数明确包含该条和pending_reason，空事实/证据合同。限制：源码存在；不证明正式三入口逐条历史读取已运行；本轮未运行。

剩余证据与启用前条件：

- 固定4e51下该条默认/显式（仅暂停拒绝、与active混合交付）到保存/读取/重试的独立合成消费证据尚未定位 下一步：复用已有合成SQLite入口fixture补选项范围与暂停结果；历史限定结果按原SHA继承，不将源码断言算新pass。
- 冻结重点抗菌药目录与两个及以上的事件计数/使用前时间、病原学来源定义；目录或资料缺失不能生成医学不合规；之后才做用药事件金标。 下一步：保留暂停，启用另需用户授权/客户合同；不追要真实模型来强行关闭当前暂停范围。

### LX0609-05-03-01 — 缺诊疗医嘱，或诊疗医嘱与病程记录不一致

当前master位于 [luxian_0609_rule_master_v1.json:494](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/data/luxian_0609_rule_master_v1.json:494)，JSON `/rules/58`。暂停原因：`treatment_event_order_course_real_gold_pending`。

当前发布范围应满足：

- 目录保持已注册且phase=pending，不把暂停解释为医学合规或不适用。
- 默认/显式任务不得把该条交给正式医学执行器、亦不得转旧执行ID绕过暂停。
- 合法交付项保留该ID及受控pending原因；not_executed、null合规、空facts/evidence，不产生临床data_gap/non_compliant。
- 原任务计划与合法历史身份可恢复；重试不得用当前默认范围扩大任务。
- 若单独打开影子开关，摘要标shadow_only/release_eligible=false，正式状态和正式计费不受影子结果影响；本轮不打开。

已有证据（均保留层次）：

- 旧组报告：[JSON](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/tumor-pathology.json)，基线 `7b894dc84491b7b72eb096de58fe61f772cc0080`；只继承该行限定结果，不把族总测试数算该条通过。
- 已有测试源码 [test_execution_catalog_is_exactly_the_active_master_projection](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_rule_master.py:160)：注册目录必须精确等active master投影。限制：本轮只读测试源码，不声明当前运行通过；本轮未运行。
- 已有测试源码 [test_phase_scope_is_a_read_only_master_projection](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:162)：phase/registered来自同一master，非另造列表。限制：未执行；本轮未运行。
- 已有测试源码 [test_customer_delivery_excludes_registration_only_handbook_rules](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:224)：默认客户交付为registered非excluded；06-03-01不可选且partition拒绝。限制：不覆盖06-03-01混合sample入口创建；本轮未运行。
- 已有测试源码 [test_defaults_freeze_scope](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/integration/test_luxian_0609_release_scope.py:81)：workspace单/批与sample默认过滤acceptance，冻结旧计划，worker/Canonical读取。限制：fixture为合成空材料+SQLite；源码可定位，本轮未执行，不证明医学内容/正式环境；本轮未运行。
- 已有测试源码 [test_public_package_entry_never_expands_pending_rules_to_legacy_execution_ids](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_native_package.py:862)：参数明确包含该条，公开入口暂停项不得转旧执行ID。限制：源码存在；无本轮执行结论；本轮未运行。
- 已有测试源码 [test_pending_definition_result_has_one_empty_evidence_contract](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:143)：参数明确包含该条和pending_reason，空事实/证据合同。限制：源码存在；不证明正式三入口逐条历史读取已运行；本轮未运行。
- 已有测试源码 [test_package_plan_keeps_pending_rules_visible_but_never_dispatches_them](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_native_package.py:744)：明确05-03-01与07-04-02在not_executed，不进入native/compatibility。限制：未运行；本轮未运行。
- 已有测试源码 [test_059_shadow_setting_defaults_off](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_059_shadow_execution.py:158)：源码保护默认关闭。限制：未读取本机配置，未执行；本轮未运行。
- 已有测试源码 [test_enabled_shadow_calls_llm_once_attaches_safe_summary_and_keeps_formal_totals](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_059_shadow_execution.py:200)：FakeLLM1次摘要shadow_only=true/release_eligible=false，正式059保持not_executed，正式tokens不混入shadow。限制：fake模型测试源码；无真实模型结论；本轮未运行。

05-03-01影子例外必须单列：getter缺省False，现有测试保护default off；若另行开shadow且资料就绪，允许影子LLM，摘要标shadow_only/release_eligible=false，正式状态仍not_executed。未读取实际运行配置、未启用；不能泛称任意配置下零模型。

剩余证据与启用前条件：

- 固定4e51下该条默认/显式（仅暂停拒绝、与active混合交付）到保存/读取/重试的独立合成消费证据尚未定位 下一步：复用已有合成SQLite入口fixture补选项范围与暂停结果；历史限定结果按原SHA继承，不将源码断言算新pass。
- 客户确认实际诊疗事件—医嘱—病程多事件/多键冲突及动作语义真实金标；先通过来源与关联合同，再考虑取消phase暂停；影子响应不得作为正式合规。 下一步：保留暂停，启用另需用户授权/客户合同；不追要真实模型来强行关闭当前暂停范围。

### LX0609-06-03-01 — 医嘱与病程一致性

当前master位于 [luxian_0609_rule_master_v1.json:686](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/data/luxian_0609_rule_master_v1.json:686)，JSON `/rules/81`。暂停原因：`culture_order_course_linkage_unavailable`。

当前发布范围应满足：

- 完整master保留未定义身份及来源缺关联键原因；active wrapper、inventory与客户默认可选目录不注册它。
- 所有新任务显式请求该条（单选/混合）在创建前稳定拒绝，不能将其伪装为注册暂停项；不得启用或新增执行器。
- 合法历史Envelope身份依完整master识别，不能因未注册被当未知；历史重试的执行拒绝与只读身份可读分别验。

已有证据（均保留层次）：

- 旧组报告：[JSON](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.json)，基线 `7b894dc84491b7b72eb096de58fe61f772cc0080`；只继承该行限定结果，不把族总测试数算该条通过。
- 已有测试源码 [test_execution_catalog_is_exactly_the_active_master_projection](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_rule_master.py:160)：注册目录必须精确等active master投影。限制：本轮只读测试源码，不声明当前运行通过；本轮未运行。
- 已有测试源码 [test_phase_scope_is_a_read_only_master_projection](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:162)：phase/registered来自同一master，非另造列表。限制：未执行；本轮未运行。
- 已有测试源码 [test_customer_delivery_excludes_registration_only_handbook_rules](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:224)：默认客户交付为registered非excluded；06-03-01不可选且partition拒绝。限制：不覆盖06-03-01混合sample入口创建；本轮未运行。
- 已有测试源码 [test_defaults_freeze_scope](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/integration/test_luxian_0609_release_scope.py:81)：workspace单/批与sample默认过滤acceptance，冻结旧计划，worker/Canonical读取。限制：fixture为合成空材料+SQLite；源码可定位，本轮未执行，不证明医学内容/正式环境；本轮未运行。

剩余证据与启用前条件：

- SCOPE6-01混合sample请求创建前拒绝尚未证明；静态路径显示验证发生过晚 下一步：独立worker正式合成入口复现后再决定是否最小修复，不计确认运行缺陷。
- 仅本条合法历史Envelope的读取与对照未知ID拒绝、旧重试不新执行的合成证据未定位 下一步：离线合法合成Envelope/冻结任务读接口；不得读真实历史病例。
- 培养主记录具备可信医嘱关联键及逐事件医嘱—病程关系；冻结培养边界（普通病毒检测不自动算培养）和金标后才可另行注册；本轮禁止启用。 下一步：继续未注册；来源关联/定义成熟后另立启用验收。

### LX0609-07-04-02 — 输血医嘱与收费不一致

当前master位于 [luxian_0609_rule_master_v1.json:410](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/data/luxian_0609_rule_master_v1.json:410)，JSON `/rules/48`。暂停原因：`charging_source_unavailable_customer_scope`。

当前发布范围应满足：

- 目录保持已注册且phase=pending，不把暂停解释为医学合规或不适用。
- 默认/显式任务不得把该条交给正式医学执行器、亦不得转旧执行ID绕过暂停。
- 合法交付项保留该ID及受控pending原因；not_executed、null合规、空facts/evidence，不产生临床data_gap/non_compliant。
- 原任务计划与合法历史身份可恢复；重试不得用当前默认范围扩大任务。

已有证据（均保留层次）：

- 旧组报告：[JSON](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/treatment-consultation.json)，基线 `7b894dc84491b7b72eb096de58fe61f772cc0080`；只继承该行限定结果，不把族总测试数算该条通过。
- 已有测试源码 [test_execution_catalog_is_exactly_the_active_master_projection](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_rule_master.py:160)：注册目录必须精确等active master投影。限制：本轮只读测试源码，不声明当前运行通过；本轮未运行。
- 已有测试源码 [test_phase_scope_is_a_read_only_master_projection](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:162)：phase/registered来自同一master，非另造列表。限制：未执行；本轮未运行。
- 已有测试源码 [test_customer_delivery_excludes_registration_only_handbook_rules](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:224)：默认客户交付为registered非excluded；06-03-01不可选且partition拒绝。限制：不覆盖06-03-01混合sample入口创建；本轮未运行。
- 已有测试源码 [test_defaults_freeze_scope](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/integration/test_luxian_0609_release_scope.py:81)：workspace单/批与sample默认过滤acceptance，冻结旧计划，worker/Canonical读取。限制：fixture为合成空材料+SQLite；源码可定位，本轮未执行，不证明医学内容/正式环境；本轮未运行。
- 已有测试源码 [test_public_package_entry_never_expands_pending_rules_to_legacy_execution_ids](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_native_package.py:862)：参数明确包含该条，公开入口暂停项不得转旧执行ID。限制：源码存在；无本轮执行结论；本轮未运行。
- 已有测试源码 [test_pending_definition_result_has_one_empty_evidence_contract](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:143)：参数明确包含该条和pending_reason，空事实/证据合同。限制：源码存在；不证明正式三入口逐条历史读取已运行；本轮未运行。

剩余证据与启用前条件：

- 固定4e51下该条默认/显式（仅暂停拒绝、与active混合交付）到保存/读取/重试的独立合成消费证据尚未定位 下一步：复用已有合成SQLite入口fixture补选项范围与暂停结果；历史限定结果按原SHA继承，不将源码断言算新pass。
- 客户提供可用收费来源及逐事件输血医嘱—收费关联/金额或条目对账口径；在现客户无收费范围内保留暂停，不能以缺收费判gap或医学缺陷。 下一步：保留暂停，启用另需用户授权/客户合同；不追要真实模型来强行关闭当前暂停范围。

### LX0609-08-01-05 — 诊疗经过不全面或不详细

当前master位于 [luxian_0609_rule_master_v1.json:725](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/data/luxian_0609_rule_master_v1.json:725)，JSON `/rules/85`。暂停原因：`无（phase_target）`。

当前发布范围应满足：

- 保持active/phase_target与acceptance_only正交，不将用户撤出默认意图改成默认执行，也不删除已知身份。
- workspace单/批及sample无显式选择时均排除；普通workspace显式也拒绝；仅customer sample验证显式允许。
- 任务保存确切scoped与acceptance_only展示快照；当前配置改变不扩大原计划或重写历史摘要。
- 旧合法结果可读；此阶段仅范围验收，不能算诊疗经过充分性医学通过；本轮不实际启用。

已有证据（均保留层次）：

- 旧组报告：[JSON](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/discharge-death.json)，基线 `7b894dc84491b7b72eb096de58fe61f772cc0080`；只继承该行限定结果，不把族总测试数算该条通过。
- 已有测试源码 [test_execution_catalog_is_exactly_the_active_master_projection](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_rule_master.py:160)：注册目录必须精确等active master投影。限制：本轮只读测试源码，不声明当前运行通过；本轮未运行。
- 已有测试源码 [test_phase_scope_is_a_read_only_master_projection](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:162)：phase/registered来自同一master，非另造列表。限制：未执行；本轮未运行。
- 已有测试源码 [test_customer_delivery_excludes_registration_only_handbook_rules](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:224)：默认客户交付为registered非excluded；06-03-01不可选且partition拒绝。限制：不覆盖06-03-01混合sample入口创建；本轮未运行。
- 已有测试源码 [test_defaults_freeze_scope](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/integration/test_luxian_0609_release_scope.py:81)：workspace单/批与sample默认过滤acceptance，冻结旧计划，worker/Canonical读取。限制：fixture为合成空材料+SQLite；源码可定位，本轮未执行，不证明医学内容/正式环境；本轮未运行。
- 已有测试源码 [test_acceptance_only_registration_is_separate_from_phase_and_customer_selection](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py:269)：acceptance仍active+target且仍可选；不等于默认执行。限制：只读源码；本轮未运行。
- 已有测试源码 [test_acceptance_explicit_and_legacy_retry](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/integration/test_luxian_0609_release_scope.py:130)：普通workspace遍历PILOTS（含08）显式422；显式sample运行/读取/重试仅参数06-02-01和06-01-03。限制：08不在显式sample参数，不能借其他ID声明08链通过；本轮未运行。
- 已有测试源码 [test_failed_retry_cannot_expand_frozen_scope](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/tests/integration/test_luxian_0609_release_scope.py:195)：失败重试不能扩原冻结范围。限制：未运行；不直接证明本条历史结果；本轮未运行。

剩余证据与启用前条件：

- 08-01-05显式sample任务仅创建/计划/冻结/快照/合法历史读取的专属无模型合成证据未定位；现test显式参数是另外两条acceptance规则 下一步：合成受控保存项测试此ID的范围链，不运行医学/evaluator，不作为启用默认范围的许可。
- 旧组报告1/1为范围开关，未证明内容充分性 下一步：保留原范围成果；当前不继续优化/审医学内容，日后用户另行授权再补。

## SCOPE6-01：未注册培养项混合选择验证过晚（待复现）

样本入口混合显式选择先把未注册ID归paused并剥离，再仅校验剩active；可把原未注册ID存入任务冻结/paused，worker使用inventory才拒绝。

这只是固定代码调用路径推断，**不是已确认运行缺陷**。worker的拒绝防止本条医学执行；风险是无效请求可能先创建任务、后失败。root已安排独立worker合成正式入口复现，只有确认才做最小修复；不能靠注册/启用06-03-01绕过。

- [qc_sample_pools.py:1025](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/routers/qc_sample_pools.py:1025)，固定行1025–1029。
- [qc_sample_pools.py:1203](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/routers/qc_sample_pools.py:1203)，固定行1203–1228。
- [qc_sample_pools.py:1233](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/routers/qc_sample_pools.py:1233)，固定行1233–1247。
- [qc_sample_pools.py:1449](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/routers/qc_sample_pools.py:1449)，固定行1449–1467。
- [sichuan_workspace_batch_worker.py:109](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/sichuan_workspace_batch_worker.py:109)，固定行109–150。
- [sichuan_workspace_batch_worker.py:1389](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/app/services/sichuan_workspace_batch_worker.py:1389)，固定行1389–1397。

最小合成请求（ready pool、ready item及完全合成三坐标；此文没有发送请求）：

```json
{
  "method": "POST",
  "url": "/api/v1/qc/sample-pools/{synthetic_ready_pool_id}/run",
  "body": {
    "rule_set_key": "luxian_0609_qc_v1",
    "validation_mode": "customer",
    "selected_rule_ids": [
      "LX0609-06-03-01",
      "LX0609-01-01-01"
    ],
    "sample_item_ids": [
      "synthetic-ready-item"
    ],
    "record_refs": [
      {
        "institute_id": "synthetic-I",
        "patient_id": "synthetic-P",
        "visit_id": "synthetic-V"
      }
    ],
    "group_by_luxian_family": false
  }
}
```

## 小范围合成补验建议（未执行）

- **S6-PENDING**：4注册pending各自稳定not_executed/null/空facts/空evidence/准确pending reason；默认和混合选择无formal native、legacy执行调用；workspace/sample仅暂停均422；纯phase/package函数+已有合成SQLite任务fixture，spy正式executor/provider；05-03默认shadow关闭，显式shadow只验安全统计和正式状态不变。
- **S6-UNREGISTERED**：master身份存在但customer/inventory无；单/混合显式创建前拒绝；合法旧合成Envelope仍known，未知ID严格拒绝；不生成本条新暂停/医学结果；SCOPE6-01正式sample入口最小请求；历史读取仅合成保存数据。
- **S6-ACCEPTANCE**：3客户入口default排除；workspace显式422；customer sample显式计划只含此ID且保存acceptance snapshot；旧计划/读取/重试不受当前default变化扩大；no-provider/no-medical-execution的入口创建、合成合法结果保存/读、freeze helper；禁止切换默认或运行医学内容。

JSON保存全部fixed git blob及SHA256、每条测试源码/旧报告SHA、调用路径与剩余字段。旧报告中的`paused`描述阶段，本报告实际`release_scope=default`取当前master，两者不能混用。08-01-05旧1/1仅范围开关；本轮保持撤出默认意图，未声称诊疗经过内容充分性。
