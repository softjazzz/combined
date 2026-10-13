# 0609当前进度叠加

固定账版本 `1958ae3bb954af7c28d0ed4f747b09913073a205`。保留T0原86矩阵：51可继承限定成果、29原开放、6原复验；本附件叠加后续问题级工程成果，**不重新审查、不算整条通过率**。本轮没有测试、模型、PG、病例或生产修改。

## 互斥下一动作（不是验收通过数）

| 下一动作 | 规则数 |
|---|---:|
| 原限定成果可继承，剩余T7证据待补 | 25 |
| 规则相关开放问题/业务口径 | 20 |
| 受输入/Prompt/事件关系变动需复验 | 7 |
| 已有实质成果，针对性阅读/manifest绑定待补 | 7 |
| 已注册暂停，仅范围/暂停合同 | 10 |
| 客户排除来源，保持撤出范围 | 5 |
| 工程子项已关，真实语义待验 | 1 |
| 已集成子项可继承，余证据层待验 | 4 |
| 部分工程集成，剩余关联映射unknown | 1 |
| 待验收撤出默认，仅显式范围 | 5 |
| 未注册，保留来源定义与历史身份范围 | 1 |
| 合计 | 86 |

当前队列40项：规则专属34项、公共链路6项。明确有限工程子项关闭16项；有已核Git祖先集成的项19项，覆盖明确映射13个唯一规则（含未注册scope项），均不是整条规则完成。默认可执行65条；其余21条为未注册1、注册暂停10、客户来源排除5、acceptance_only撤默认5，不能算医学通过。

## 必须保留的限定结论

- **N12 / 04-04-02**：copy/core/原28保护及43新项、独审SQLite3、root383可继承；真实语义模型及全扫描准确率未验。root严格348含2同父已有失败，不写全部绿。
- **TP-D04 / 05-01-06**：原18输入/oracle、35独审及SQLite3子项已集成；仅跨药支持/时间归属与多药半覆盖文案，不是整个特殊级用药规则临床通过。未知药名及自然资料签认保留；TP-D05和N13属其他规则。
- **SCOPE6-01 / 06-03-01**：4c47入口原选择membership检查已集成，root21正式TestClient/SQLite通过；独审0运行。原4e51静态待复现被此后成果接续，不能继续据旧标签算开放。仍未注册、未启用，未改医学结论。
- **PRIV003**：d2e限定拒发边界集成；两CLI可信身份来源/自然caller未接，failclosed保持。这是功能恢复前置，不能称确认继续泄漏。
- **N13 / 05-02-01**：TP-D01/错误日期归属子项可继承，原6NC→gap能力与2归属计数仍未达；TP-D02/D03独立开放，不能假关整条。
- **IML01**：US/培养角色子项已集成，CT/MRI同键合同与新字段真实输入影响仍待验。队列历史3 affected IDs未分配剩余合同到各规则，逐条标unknown，不臆造规则关闭。

## 逐规则索引

| 规则 | 原继承层 | 本轮集成子项 | 仍开放/部分问题 | 复验项 | 当前下一动作 |
|---|---|---|---|---|
| LX0609-01-01-01 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-01-02-01 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-04-02-01 | specific_completed_engineering_issue_and_independent_offline_review | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-09-01-01 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-02-01-01 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-02-01-02 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-02-01-03 | specific_completed_engineering_issue_and_independent_offline_review | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-02-01-04 | specific_completed_engineering_issue_and_independent_offline_review | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-02-01-05 | specific_completed_engineering_issue_and_independent_offline_review | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-06-01-02 | existing_source_review_or_offline_protection_only | — | imaging-laboratory:IML-D02 | — | 规则相关开放问题/业务口径 |
| LX0609-06-01-04 | existing_source_review_or_offline_protection_only | — | — | CT-INPUT-CHANGE | 受输入/Prompt/事件关系变动需复验 |
| LX0609-06-01-05 | existing_source_review_or_offline_protection_only | — | — | CT-INPUT-CHANGE | 受输入/Prompt/事件关系变动需复验 |
| LX0609-06-02-03 | existing_source_review_or_offline_protection_only | — | — | PATH-INPUT-CHANGE | 受输入/Prompt/事件关系变动需复验 |
| LX0609-06-03-03 | existing_source_review_or_offline_protection_only | — | — | — | 已有实质成果，针对性阅读/manifest绑定待补 |
| LX0609-06-03-04 | existing_source_review_or_offline_protection_only | — | — | — | 已有实质成果，针对性阅读/manifest绑定待补 |
| LX0609-12-01-01 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-12-01-02 | specific_completed_engineering_issue_and_independent_offline_review | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-01-01-02 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-06-02-02 | existing_source_review_or_offline_protection_only | — | — | PATH-INPUT-CHANGE | 受输入/Prompt/事件关系变动需复验 |
| LX0609-03-01-01 | pause_scope_source_gate_review_only | — | — | — | 已注册暂停，仅范围/暂停合同 |
| LX0609-03-01-02 | pause_scope_source_gate_review_only | — | — | — | 已注册暂停，仅范围/暂停合同 |
| LX0609-03-01-03 | pause_scope_source_gate_review_only | — | — | — | 已注册暂停，仅范围/暂停合同 |
| LX0609-03-01-04 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-04-02-03 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-04-02-04 | pause_scope_source_gate_review_only | — | — | — | 已注册暂停，仅范围/暂停合同 |
| LX0609-05-02-01 | specific_completed_engineering_issue_and_independent_offline_review | tumor-pathology:TP-D01；部分N13 | tumor-pathology:TP-D02,tumor-pathology:TP-D03,N13 | — | 规则相关开放问题/业务口径 |
| LX0609-08-01-04 | existing_source_review_or_offline_protection_only | — | discharge-death:DD-F05 | — | 规则相关开放问题/业务口径 |
| LX0609-05-01-01 | pause_scope_source_gate_review_only | — | — | — | 已注册暂停，仅范围/暂停合同 |
| LX0609-04-01-01 | existing_source_review_or_offline_protection_only | — | SURGERY-029030 | — | 规则相关开放问题/业务口径 |
| LX0609-04-02-02 | existing_source_review_or_offline_protection_only | — | SURGERY-029030 | SURGERY-FREEZE | 规则相关开放问题/业务口径 |
| LX0609-04-02-05 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-04-03-01 | existing_source_review_or_offline_protection_only | — | — | SURGERY-FREEZE | 受输入/Prompt/事件关系变动需复验 |
| LX0609-11-01-01 | customer_exclusion_scope_review_only | — | — | — | 客户排除来源，保持撤出范围 |
| LX0609-11-02-01 | customer_exclusion_scope_review_only | — | — | — | 客户排除来源，保持撤出范围 |
| LX0609-11-02-02 | customer_exclusion_scope_review_only | — | — | — | 客户排除来源，保持撤出范围 |
| LX0609-04-04-01 | pause_scope_source_gate_review_only | — | — | — | 已注册暂停，仅范围/暂停合同 |
| LX0609-04-04-02 | existing_source_review_or_offline_protection_only | N12 | — | — | 工程子项已关，真实语义待验 |
| LX0609-04-04-03 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-04-01-02 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-04-01-03 | existing_source_review_or_offline_protection_only | — | — | SURGERY-FREEZE | 受输入/Prompt/事件关系变动需复验 |
| LX0609-11-03-01 | customer_exclusion_scope_review_only | — | — | — | 客户排除来源，保持撤出范围 |
| LX0609-11-03-02 | customer_exclusion_scope_review_only | — | — | — | 客户排除来源，保持撤出范围 |
| LX0609-07-01-01 | existing_source_review_or_offline_protection_only | — | treatment-consultation:TC-01 | — | 规则相关开放问题/业务口径 |
| LX0609-07-01-02 | specific_completed_engineering_issue_and_independent_offline_review | — | TR-044-MULTI,treatment-consultation:TC-01 | — | 规则相关开放问题/业务口径 |
| LX0609-07-02-01 | existing_source_review_or_offline_protection_only | — | treatment-consultation:TC-01 | — | 规则相关开放问题/业务口径 |
| LX0609-07-02-02 | existing_source_review_or_offline_protection_only | — | treatment-consultation:TC-01 | — | 规则相关开放问题/业务口径 |
| LX0609-07-03-01 | existing_source_review_or_offline_protection_only | — | treatment-consultation:TC-01 | — | 规则相关开放问题/业务口径 |
| LX0609-07-04-01 | specific_completed_engineering_issue_and_independent_offline_review | — | treatment-consultation:TC-03 | TR-048-REAL | 规则相关开放问题/业务口径 |
| LX0609-07-04-02 | pause_scope_source_gate_review_only | — | — | — | 已注册暂停，仅范围/暂停合同 |
| LX0609-03-02-01 | existing_source_review_or_offline_protection_only | course-timing:CT-02,course-timing:CT-03,course-timing:CT-04 | course-timing:CT-01 | — | 规则相关开放问题/业务口径 |
| LX0609-09-02-01 | existing_source_review_or_offline_protection_only | rescue-remaining:RR-D02 | rescue-remaining:RR-D01 | — | 规则相关开放问题/业务口径 |
| LX0609-06-04-01 | specific_completed_engineering_issue_and_independent_offline_review | imaging-laboratory:IML-02 | — | — | 已集成子项可继承，余证据层待验 |
| LX0609-06-04-02 | specific_completed_engineering_issue_and_independent_offline_review | imaging-laboratory:IML-02 | — | — | 已集成子项可继承，余证据层待验 |
| LX0609-05-01-02 | existing_source_review_or_offline_protection_only | — | — | — | 已有实质成果，针对性阅读/manifest绑定待补 |
| LX0609-05-01-03 | existing_source_review_or_offline_protection_only | — | tumor-pathology:TP-D05 | — | 规则相关开放问题/业务口径 |
| LX0609-05-01-04 | pause_scope_source_gate_review_only | — | — | — | 已注册暂停，仅范围/暂停合同 |
| LX0609-05-01-05 | existing_source_review_or_offline_protection_only | — | — | — | 已有实质成果，针对性阅读/manifest绑定待补 |
| LX0609-05-01-06 | existing_source_review_or_offline_protection_only | tumor-pathology:TP-D04 | — | — | 已集成子项可继承，余证据层待验 |
| LX0609-05-03-01 | pause_scope_source_gate_review_only | — | — | — | 已注册暂停，仅范围/暂停合同 |
| LX0609-04-02-06 | existing_source_review_or_offline_protection_only | — | — | — | 已有实质成果，针对性阅读/manifest绑定待补 |
| LX0609-08-01-01 | existing_source_review_or_offline_protection_only | — | — | — | 已有实质成果，针对性阅读/manifest绑定待补 |
| LX0609-08-01-02 | existing_source_review_or_offline_protection_only | — | discharge-death:DD-F02 | — | 规则相关开放问题/业务口径 |
| LX0609-08-01-03 | existing_source_review_or_offline_protection_only | discharge-death:DD-F01 | — | — | 已集成子项可继承，余证据层待验 |
| LX0609-04-05-01 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-04-05-02 | existing_source_review_or_offline_protection_only | — | N10 | — | 规则相关开放问题/业务口径 |
| LX0609-04-05-03 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-08-02-01 | existing_source_review_or_offline_protection_only | — | N10 | — | 规则相关开放问题/业务口径 |
| LX0609-08-02-02 | existing_source_review_or_offline_protection_only | — | — | — | 已有实质成果，针对性阅读/manifest绑定待补 |
| LX0609-04-02-07 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-07-01-03 | existing_source_review_or_offline_protection_only | — | treatment-consultation:TC-02 | — | 规则相关开放问题/业务口径 |
| LX0609-10-01-01 | specific_completed_engineering_issue_and_independent_offline_review | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-10-02-01 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-10-02-02 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-12-02-01 | existing_source_review_or_offline_protection_only | rescue-remaining:RR-M01 | — | PROMPT-074 | 受输入/Prompt/事件关系变动需复验 |
| LX0609-10-03-01 | pause_scope_source_gate_review_only | — | — | — | 已注册暂停，仅范围/暂停合同 |
| LX0609-04-02-08 | specific_completed_engineering_issue_and_independent_offline_review | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-01-02-02 | existing_source_review_or_offline_protection_only | — | — | — | 原限定成果可继承，剩余T7证据待补 |
| LX0609-04-01-04 | bounded_real_model_fields_copy_and_local_persistence_with_limited_independent_review | — | PREOP-MEDICAL | — | 规则相关开放问题/业务口径 |
| LX0609-04-01-05 | bounded_real_model_fields_copy_and_local_persistence_with_limited_independent_review | — | PREOP-MEDICAL | — | 规则相关开放问题/业务口径 |
| LX0609-06-01-01 | existing_source_review_or_offline_protection_only | —；部分imaging-laboratory:IML-01 | imaging-laboratory:IML-01 | — | 部分工程集成，剩余关联映射unknown |
| LX0609-06-01-03 | existing_source_review_or_offline_protection_only | —；部分imaging-laboratory:IML-01 | imaging-laboratory:IML-D01,imaging-laboratory:IML-01 | — | 待验收撤出默认，仅显式范围 |
| LX0609-06-03-01 | catalog_registration_and_source_pause_metadata_only | SCOPE6-01 | — | — | 未注册，保留来源定义与历史身份范围 |
| LX0609-06-03-02 | existing_source_review_or_offline_protection_only | —；部分imaging-laboratory:IML-01 | imaging-laboratory:IML-01 | — | 待验收撤出默认，仅显式范围 |
| LX0609-06-02-01 | existing_source_review_or_offline_protection_only | — | — | — | 待验收撤出默认，仅显式范围 |
| LX0609-09-01-02 | existing_source_review_or_offline_protection_only | — | — | — | 待验收撤出默认，仅显式范围 |
| LX0609-08-01-05 | acceptance_only_scope_switch_check_only | — | — | — | 待验收撤出默认，仅显式范围 |

逐条已有读审/反例位置、源SHA、历史完成问题、最高可定位旧技术层、这轮集成SHA/独审/回归出处及剩余模型/业务/正式链字段在[overlay.json](F:/MedQC-worktrees/review-artifacts/coverage-progress-current/overlay.json)的`rules`；可筛选简表为[rules.csv](F:/MedQC-worktrees/review-artifacts/coverage-progress-current/rules.csv)。旧报告缺执行SHA或case manifest的字段原样保留，不补猜。

## 问题级账（不等同规则数）

| 进度类 | 项数 |
|---|---:|
| limited_engineering_subissue_closed | 16 |
| open_issue_or_business_basis | 16 |
| partial_engineering_integrated_issue_open | 2 |
| affected_inputs_revalidation_open | 5 |
| functional_prerequisite_open_after_boundary_closed | 1 |

问题分类使用逐ID明确状态及集成祖先核验，不扫描notes中的closed词。原claim/source_classification/reconciliation_state可能保留初审语义，最新工程状态依固定state和后续集成记录分账；不同层不互相替代。

## 真实缺口与下一阶段

- 先沿仍开放根因与业务口径收口：CT01、N10、TR044多事件、SURGERY029030/冻结差异、输血TC01/02/03、化疗TP-D02/D03/D05、带药DD-F02及其他明确业务争议；复用已有反例和正常保护，不重审86。
- 输入/Prompt受影响项沿CT-INPUT、PATH-INPUT、PROMPT074、SURGERY-FREEZE、TR048原定位复验；旧真实响应不代替新输入输出。
- 工程子项关后按职责补自然资料/独立人工预期。program_only不制造模型调用；可选语义规则仅自然触发语义的场景补真实输出，暂停/撤默认项继续范围验收。
- 最终候选正式保存/新实例回读/真实HTTP/浏览器/历史读取/导出及客户环境、构建身份门禁仍缺；已有SQLite与合成TestClient按原界限继承，不从零，也不冒充客户全链。
- 既有全仓encoding问题/全量typecheck资源中断/全量单测未完成保留；新增lint exit0但1214warnings不是所有门禁通过。

未审数量继续`null`。10条有实质行为但业务源码阅读定位未充分绑定；T5另外6条范围源码已补，仍非业务医学通过。本附件不因证据弱把规则改成真正未审。

集成祖先核验只确认报告声明的root集成提交位于固定1958历史；没有重新审生产diff或把旧用例冒称1958新跑。逐条原历史证据的适用限制和未绑定manifest仍保留。
