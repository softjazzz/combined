# 0609 既有实质审查证据定位

本附件逐条核对冻结T0的86条既有阅读/反例索引。没有重新阅读生产代码，没有运行测试、探针、PG或模型。0916排除，原总矩阵与台账不改。

“已分配”“报告列名”“已审标签”和套件通过总数不能单独证明实质已审。下列状态只说明报告证据能定位到哪里，不是医学通过或真正未审的统计。

## 定位结果

| 文档证据状态 | 条数 |
| --- | ---: |
| 针对性源码/合同阅读记录可定位（非整条验收） | 70 |
| 实质审查/反例可定位，源码阅读定位待补 | 10 |
| 仅定位范围/目录核对，业务实现阅读未证明 | 6 |

**truly_unreviewed_confirmed仍为null。** 无法证明针对性源码阅读的16条不等于16条真正未审：其中10条已有实质行为/反例审查，6条只有范围/目录或影子摘要。没有把“未找到更多证据”改成“从未审”，也没有因报告86行齐全写0未审。

## 先补证的16条

| rule_id | 已有证据及未证明处 | 下一步 |
| --- | --- | --- |
| LX0609-04-02-06 | 历史六例只覆盖无死亡触发，本轮套件与现行行说明有保护，但没有独立定位060死亡记录存在性分支的阅读函数/行号。 | 补既有源码阅读摘录/函数定位与本条执行身份，若仍不存在才向root申请有限补审；不重跑已有实质审查。 |
| LX0609-05-01-01 | 总表/phase及not_executed范围结果有实质记录；I/II切口抗菌药时限业务实现源码阅读未证明，不能把暂停合同算医学审核。 | 仅按发布状态核范围/历史可读/启用条件；是否需补业务实现审查由root确认，不能据此强行启用。 |
| LX0609-05-01-02 | 现有6个针对性合成理由案例及动作所有权描述，不是只列名；报告未逐条绑定实际理由分支函数/行号和源码hash。 | 补既有源码阅读摘录/函数定位与本条执行身份，若仍不存在才向root申请有限补审；不重跑已有实质审查。 |
| LX0609-05-01-04 | 总表pending与not_executed范围结果有实质记录；双重点抗菌药用前病原学实现阅读未证明，重点药目录欠冻结。 | 仅按发布状态核范围/历史可读/启用条件；是否需补业务实现审查由root确认，不能据此强行启用。 |
| LX0609-05-01-05 | 现有7个针对性合成理由案例与会诊来源边界描述；未明确绑定057经验理由分支阅读摘录，不能把测试文件名当阅读证据。 | 补既有源码阅读摘录/函数定位与本条执行身份，若仍不存在才向root申请有限补审；不重跑已有实质审查。 |
| LX0609-05-03-01 | 正式暂停合同及影子套件保护陈述可定位；严格业务键/多事件等摘要没有逐规则影子函数阅读摘录和对应hash绑定。缺真实金标不等于从未审。 | 仅按发布状态核范围/历史可读/启用条件；是否需补业务实现审查由root确认，不能据此强行启用。 |
| LX0609-06-01-04 | 既有真实限定批次及现行事件/时间/引导规则陈述可定位；针对本条抽取/结果记录判定函数的阅读定位未明确，历史模型响应不是源码阅读日志。 | 补既有源码阅读摘录/函数定位与本条执行身份，若仍不存在才向root申请有限补审；不重跑已有实质审查。 |
| LX0609-06-01-05 | 既有阳性标准/共享抽取与真实限定结果索引可定位；本条独立分析判定函数阅读位置未明确。 | 补既有源码阅读摘录/函数定位与本条执行身份，若仍不存在才向root申请有限补审；不重跑已有实质审查。 |
| LX0609-06-02-01 | 历史阶段A P01-P03真实生产Session/确定性发布/交付技术证据和当前ID命名空间说明可定位；不是未做过。本条病理报告完整性实现阅读函数/行号仍未绑定。 | 补既有源码阅读摘录/函数定位与本条执行身份，若仍不存在才向root申请有限补审；不重跑已有实质审查。 |
| LX0609-06-03-01 | 仅目录未注册、pending_definition及培养医嘱关联键不足约束；旧新规则合并清单有源字段问题分析，但无可执行规则/合同分支阅读。启用条件待补，不自动称真正未审。 | 仅按发布状态核范围/历史可读/启用条件；是否需补业务实现审查由root确认，不能据此强行启用。 |
| LX0609-06-03-03 | 历史四份培养材料预期与既存结果审查、现行test_id/24h陈述可定位；旧审计未新做语义抽取，本条源代码阅读段落未明确。 | 补既有源码阅读摘录/函数定位与本条执行身份，若仍不存在才向root申请有限补审；不重跑已有实质审查。 |
| LX0609-06-03-04 | 历史阳性/正常菌群、菌名修复及既存结果审查可定位；当前阳性分析执行分支的针对性源码阅读定位未明确。 | 补既有源码阅读摘录/函数定位与本条执行身份，若仍不存在才向root申请有限补审；不重跑已有实质审查。 |
| LX0609-07-04-02 | 只有客户缺收费来源、pending_definition和不执行范围核对；没有049收费比较实现阅读/反例。当前发布状态无需强启用。 | 仅按发布状态核范围/历史可读/启用条件；是否需补业务实现审查由root确认，不能据此强行启用。 |
| LX0609-08-01-01 | 7个061确定性函数边界实际结果可定位；当前报告未给061函数/模块行号，不能仅由7/7证明源码针对性阅读。 | 补既有源码阅读摘录/函数定位与本条执行身份，若仍不存在才向root申请有限补审；不重跑已有实质审查。 |
| LX0609-08-01-05 | 仅1个acceptance_only范围配置观察；没有诊疗经过内容充分性实现的阅读摘录/正常缺陷语义案例。业务实现未证明已审。 | 仅按发布状态核范围/历史可读/启用条件；是否需补业务实现审查由root确认，不能据此强行启用。 |
| LX0609-08-02-02 | 4个068合成正式执行/聚合案例及历史角色/时间资料审查可定位；针对068源码分支的阅读位置未明确。 | 补既有源码阅读摘录/函数定位与本条执行身份，若仍不存在才向root申请有限补审；不重跑已有实质审查。 |

## 86条已有阅读/反例位置

JSON逐条保留当前组报告JSON指针、Markdown行号、旧报告的匹配rule_id及源码/合同候选行、具体结果/问题指针、SHA与已有合成artifact索引。旧报告提到其他规则的源码不能自动分摊为本条阅读证明；旧生产行号不冒充当前代码行号。

| rule_id | 定位状态 | 已有针对性阅读/反例范围 | 首要证据位置 |
| --- | --- | --- | --- |
| LX0609-01-01-01 | 针对性源码/合同阅读记录可定位（非整条验收） | apps/medqc-web/backend/app/services/luxian_0609/native_basic_timeliness.py；decision_binding.py；basic_timeliness_customer_projection.py；canonical_result_finalizer.py | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.md:11)；JSON rules指针见附件 |
| LX0609-01-01-02 | 针对性源码/合同阅读记录可定位（非整条验收） | apps/medqc-web/backend/app/services/luxian_0609/course_quality/rule_018.py；native_course_quality_execution.py；course_quality_result_mapping.py；canonical_result_finalizer.py | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.md:18)；JSON rules指针见附件 |
| LX0609-01-02-01 | 针对性源码/合同阅读记录可定位（非整条验收） | apps/medqc-web/backend/app/services/luxian_0609/native_basic_timeliness.py；decision_binding.py；basic_timeliness_customer_projection.py；canonical_result_finalizer.py | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.md:12)；JSON rules指针见附件 |
| LX0609-01-02-02 | 针对性源码/合同阅读记录可定位（非整条验收） | apps/medqc-web/backend/app/services/luxian_0609/course_quality/rule_077.py；native_course_quality_execution.py；canonical_result_finalizer.py | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.md:19)；JSON rules指针见附件 |
| LX0609-02-01-01 | 针对性源码/合同阅读记录可定位（非整条验收） | apps/medqc-web/backend/app/services/luxian_0609/native_basic_timeliness.py；decision_binding.py；basic_timeliness_customer_projection.py；canonical_result_finalizer.py | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.md:13)；JSON rules指针见附件 |
| LX0609-02-01-02 | 针对性源码/合同阅读记录可定位（非整条验收） | apps/medqc-web/backend/app/services/luxian_0609/native_basic_timeliness.py；decision_binding.py；basic_timeliness_customer_projection.py；canonical_result_finalizer.py | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.md:14)；JSON rules指针见附件 |
| LX0609-02-01-03 | 针对性源码/合同阅读记录可定位（非整条验收） | apps/medqc-web/backend/app/services/luxian_0609/course_quality/rule_007.py；decision_binding.py；course_quality_result_mapping.py；canonical_result_finalizer.py | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.md:15)；JSON rules指针见附件 |
| LX0609-02-01-04 | 针对性源码/合同阅读记录可定位（非整条验收） | apps/medqc-web/backend/app/services/luxian_0609/course_quality/rules_008_009.py；course_quality_result_mapping.py；canonical_result_finalizer.py | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.md:16)；JSON rules指针见附件 |
| LX0609-02-01-05 | 针对性源码/合同阅读记录可定位（非整条验收） | apps/medqc-web/backend/app/services/luxian_0609/course_quality/rules_008_009.py；course_quality_result_mapping.py；canonical_result_finalizer.py | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.md:17)；JSON rules指针见附件 |
| LX0609-03-01-01 | 针对性源码/合同阅读记录可定位（非整条验收） | 总表162起：源库会诊文书实际是执行记录，缺独立会诊记录单；phase_scope:121生成not_executed/policy_definition_pending，facts为空、不催补文书。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/course-timing.md:3)；JSON rules指针见附件 |
| LX0609-03-01-02 | 针对性源码/合同阅读记录可定位（非整条验收） | 总表173起：未同步会诊申请单；相同暂停链。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/course-timing.md:24)；JSON rules指针见附件 |
| LX0609-03-01-03 | 针对性源码/合同阅读记录可定位（非整条验收） | 总表184起：缺独立会诊记录单意见源；相同暂停链。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/course-timing.md:25)；JSON rules指针见附件 |
| LX0609-03-01-04 | 针对性源码/合同阅读记录可定位（非整条验收） | 总表195起：建议从会诊执行记录正文语义提取，逐条匹配后续病程/医嘱。episode执行器3397：具体痕迹或高置信具体医嘱才合规；确认缺证或笼统记录不合规；相关源缺口和未知安全降级。2913：计划痕迹不等于完成。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/course-timing.md:26)；JSON rules指针见附件 |
| LX0609-03-02-01 | 针对性源码/合同阅读记录可定位（非整条验收） | 入院registration/admission时间+满7天daily病程当前诊断不明确+讨论表存在性。客户事实显示admission_time、uncertain_record_times、discussion_count；Renderer生成结论文案。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/course-timing.md:3)；JSON rules指针见附件 |
| LX0609-04-01-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_surgery_document_execution.py：旧029术前小结门控与逐台关联冻结 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:28)；JSON rules指针见附件 |
| LX0609-04-01-02 | 针对性源码/合同阅读记录可定位（非整条验收） | native_surgery_document_execution.py：旧039术前讨论存在性/术者参与/紧急抢救例外冻结 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:29)；JSON rules指针见附件 |
| LX0609-04-01-03 | 针对性源码/合同阅读记录可定位（非整条验收） | 四级手术MDT typed执行器 source_query_error事实公开差异；专属冻结与当前独立反例 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:30)；JSON rules指针见附件 |
| LX0609-04-01-04 | 针对性源码/合同阅读记录可定位（非整条验收） | native_preop_content_execution.py / baf99ba79：三态、术者查看与诊断定义的Prompt/原子合同，限定字段复核 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:31)；JSON rules指针见附件 |
| LX0609-04-01-05 | 针对性源码/合同阅读记录可定位（非整条验收） | native_preop_content_execution.py / baf99ba79：术前讨论原子三态/同文书引用合同，限定字段复核 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:32)；JSON rules指针见附件 |
| LX0609-04-02-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_surgery_gate_execution.py / surgery_gate_result_mapping.py：C-SECOND精确秒合同；003/031逐台覆盖记录 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:33)；JSON rules指针见附件 |
| LX0609-04-02-02 | 针对性源码/合同阅读记录可定位（非整条验收） | native_execution.py / surgery_presence_result_mapping.py：旧030正式存在性事实/Finalizer所有权 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:34)；JSON rules指针见附件 |
| LX0609-04-02-03 | 针对性源码/合同阅读记录可定位（非整条验收） | native_surgery_gate_execution.py：历史surgery-family-ownership-baseline六规则职责表的024恶性/淋巴结分支 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:35)；JSON rules指针见附件 |
| LX0609-04-02-04 | 针对性源码/合同阅读记录可定位（非整条验收） | phase_scope.py::partition_luxian_0609_rule_scope / build_luxian_0609_pending_definition_result：旧025专项实际入口与空事实合同 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:36)；JSON rules指针见附件 |
| LX0609-04-02-05 | 针对性源码/合同阅读记录可定位（非整条验收） | native_surgery_gate_execution.py：旧031术者签名资格与逐台覆盖合同 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:37)；JSON rules指针见附件 |
| LX0609-04-02-06 | 实质审查/反例可定位，源码阅读定位待补 | 历史六例只覆盖无死亡触发，本轮套件与现行行说明有保护，但没有独立定位060死亡记录存在性分支的阅读函数/行号。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:38)；JSON rules指针见附件 |
| LX0609-04-02-07 | 针对性源码/合同阅读记录可定位（非整条验收） | evaluate_consultation_timeliness：旧069空申请时间source_unavailable→authoritative_time_missing专项 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:39)；JSON rules指针见附件 |
| LX0609-04-02-08 | 针对性源码/合同阅读记录可定位（非整条验收） | extended_document/rule_076.py::_parse_time：日期不能代死亡时刻及合法格式，C-DEATH专项独审 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:40)；JSON rules指针见附件 |
| LX0609-04-03-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_execution.py / surgery_presence_result_mapping.py：旧032安全核查存在性逐台关联与展示合同 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:41)；JSON rules指针见附件 |
| LX0609-04-04-01 | 针对性源码/合同阅读记录可定位（非整条验收） | phase_scope.py：现行036来源范围暂停；旧native_surgery_document_execution.py逐源访视合同 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:42)；JSON rules指针见附件 |
| LX0609-04-04-02 | 针对性源码/合同阅读记录可定位（非整条验收） | native_surgery_document_execution.py:871,902 / N08标签解析归属修复 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:43)；JSON rules指针见附件 |
| LX0609-04-04-03 | 针对性源码/合同阅读记录可定位（非整条验收） | native_surgery_document_execution.py：旧038非局麻实施/记录存在性，旧手术文书冻结职责与R02五例预期 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:44)；JSON rules指针见附件 |
| LX0609-04-05-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native extended executor：旧064术后1–3日逐台病程与术者查房fact_refs合同 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:45)；JSON rules指针见附件 |
| LX0609-04-05-02 | 针对性源码/合同阅读记录可定位（非整条验收） | native_extended_document_execution.py:3620 / _row_time：旧065无权威时间查房缺口；72h窗口及fact_refs合同 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:46)；JSON rules指针见附件 |
| LX0609-04-05-03 | 针对性源码/合同阅读记录可定位（非整条验收） | native extended executor：旧066最近已结束手术关联与缺失事件fact_refs | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.md:47)；JSON rules指针见附件 |
| LX0609-05-01-01 | 仅定位范围/目录核对，业务实现阅读未证明 | 总表/phase及not_executed范围结果有实质记录；I/II切口抗菌药时限业务实现源码阅读未证明，不能把暂停合同算医学审核。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/tumor-pathology.md:15)；JSON rules指针见附件 |
| LX0609-05-01-02 | 实质审查/反例可定位，源码阅读定位待补 | 现有6个针对性合成理由案例及动作所有权描述，不是只列名；报告未逐条绑定实际理由分支函数/行号和源码hash。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/tumor-pathology.md:16)；JSON rules指针见附件 |
| LX0609-05-01-03 | 针对性源码/合同阅读记录可定位（非整条验收） | native_extended_document_execution.py:198,1137：48/60/72h明确效果评价词漏识别TP-D05 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/tumor-pathology.md:17)；JSON rules指针见附件 |
| LX0609-05-01-04 | 仅定位范围/目录核对，业务实现阅读未证明 | 总表pending与not_executed范围结果有实质记录；双重点抗菌药用前病原学实现阅读未证明，重点药目录欠冻结。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/tumor-pathology.md:18)；JSON rules指针见附件 |
| LX0609-05-01-05 | 实质审查/反例可定位，源码阅读定位待补 | 现有7个针对性合成理由案例与会诊来源边界描述；未明确绑定057经验理由分支阅读摘录，不能把测试文件名当阅读证据。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/tumor-pathology.md:19)；JSON rules指针见附件 |
| LX0609-05-01-06 | 针对性源码/合同阅读记录可定位（非整条验收） | native_extended_document_execution.py:2794：单个事件无条件回退另一药专家支持TP-D04 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/tumor-pathology.md:20)；JSON rules指针见附件 |
| LX0609-05-02-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_tumor_pathology_execution.py:632,1298,1342,1399,1490,2010：化疗取消、跨药剂量、空正文解包及N13 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/tumor-pathology.md:21)；JSON rules指针见附件 |
| LX0609-05-03-01 | 仅定位范围/目录核对，业务实现阅读未证明 | 正式暂停合同及影子套件保护陈述可定位；严格业务键/多事件等摘要没有逐规则影子函数阅读摘录和对应hash绑定。缺真实金标不等于从未审。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/tumor-pathology.md:22)；JSON rules指针见附件 |
| LX0609-06-01-01 | 针对性源码/合同阅读记录可定位（非整条验收） | handbook_exam_lab.py:232 / native_exam_lab_execution.py / ct_order_course_consistency.py：报告身份冲突与医嘱执行证明 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md:13)；JSON rules指针见附件 |
| LX0609-06-01-02 | 针对性源码/合同阅读记录可定位（非整条验收） | exam_lab_fact_extraction.py:193,994,1397 / native_exam_lab_execution.py:1481：检查前48h候选门控及R02身份投影 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md:14)；JSON rules指针见附件 |
| LX0609-06-01-03 | 针对性源码/合同阅读记录可定位（非整条验收） | handbook_exam_lab.py:232：同exam_id主从身份与报告完整性 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md:15)；JSON rules指针见附件 |
| LX0609-06-01-04 | 实质审查/反例可定位，源码阅读定位待补 | 既有真实限定批次及现行事件/时间/引导规则陈述可定位；针对本条抽取/结果记录判定函数的阅读定位未明确，历史模型响应不是源码阅读日志。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md:16)；JSON rules指针见附件 |
| LX0609-06-01-05 | 实质审查/反例可定位，源码阅读定位待补 | 既有阳性标准/共享抽取与真实限定结果索引可定位；本条独立分析判定函数阅读位置未明确。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md:17)；JSON rules指针见附件 |
| LX0609-06-02-01 | 实质审查/反例可定位，源码阅读定位待补 | 历史阶段A P01-P03真实生产Session/确定性发布/交付技术证据和当前ID命名空间说明可定位；不是未做过。本条病理报告完整性实现阅读函数/行号仍未绑定。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md:18)；JSON rules指针见附件 |
| LX0609-06-02-02 | 针对性源码/合同阅读记录可定位（非整条验收） | native_tumor_pathology_execution.py:706,1668,1677 / _pathology_documentation_links：取材关联/最终诊断前置门控 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md:19)；JSON rules指针见附件 |
| LX0609-06-02-03 | 针对性源码/合同阅读记录可定位（非整条验收） | native_tumor_pathology_execution.py:769,2160 / _pathology_documentation_links：报告结果逐事件同次关联 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md:20)；JSON rules指针见附件 |
| LX0609-06-03-01 | 仅定位范围/目录核对，业务实现阅读未证明 | 仅目录未注册、pending_definition及培养医嘱关联键不足约束；旧新规则合并清单有源字段问题分析，但无可执行规则/合同分支阅读。启用条件待补，不自动称真正未审。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md:21)；JSON rules指针见附件 |
| LX0609-06-03-02 | 针对性源码/合同阅读记录可定位（非整条验收） | handbook_exam_lab.py:232：同test_id培养主从身份与报告完整性 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md:22)；JSON rules指针见附件 |
| LX0609-06-03-03 | 实质审查/反例可定位，源码阅读定位待补 | 历史四份培养材料预期与既存结果审查、现行test_id/24h陈述可定位；旧审计未新做语义抽取，本条源代码阅读段落未明确。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md:23)；JSON rules指针见附件 |
| LX0609-06-03-04 | 实质审查/反例可定位，源码阅读定位待补 | 历史阳性/正常菌群、菌名修复及既存结果审查可定位；当前阳性分析执行分支的针对性源码阅读定位未明确。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md:24)；JSON rules指针见附件 |
| LX0609-06-04-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_extended_document_execution.py:578 / _critical_value_item_from_row：危急值报告时间缺失/别名冲突与6h | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md:25)；JSON rules指针见附件 |
| LX0609-06-04-02 | 针对性源码/合同阅读记录可定位（非整条验收） | native_extended_document_execution.py:578 / _critical_value_item_from_row：危急值处置存在性及报告后先后 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md:26)；JSON rules指针见附件 |
| LX0609-07-01-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_transfusion_execution.py:2865：共享门控仅正文长度≥16误认计划/拒绝/暂缓实施 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/treatment-consultation.md:27)；JSON rules指针见附件 |
| LX0609-07-01-02 | 针对性源码/合同阅读记录可定位（非整条验收） | native_transfusion_execution.py:2865：共享门控仅正文长度≥16误认计划/拒绝/暂缓实施 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/treatment-consultation.md:28)；JSON rules指针见附件 |
| LX0609-07-01-03 | 针对性源码/合同阅读记录可定位（非整条验收） | native_extended_document_execution.py:3001 / native_transfusion_execution.py:961：070完成时间替代实际输血 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/treatment-consultation.md:34)；JSON rules指针见附件 |
| LX0609-07-02-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_transfusion_execution.py:2865：共享门控仅正文长度≥16误认计划/拒绝/暂缓实施 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/treatment-consultation.md:29)；JSON rules指针见附件 |
| LX0609-07-02-02 | 针对性源码/合同阅读记录可定位（非整条验收） | native_transfusion_execution.py:2865：共享门控仅正文长度≥16误认计划/拒绝/暂缓实施 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/treatment-consultation.md:30)；JSON rules指针见附件 |
| LX0609-07-03-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_transfusion_execution.py:2865：共享门控仅正文长度≥16误认计划/拒绝/暂缓实施 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/treatment-consultation.md:31)；JSON rules指针见附件 |
| LX0609-07-04-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_transfusion_execution.py:2388：048否定/备血触发，C-TRANSFUSION-PAIR另列 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/treatment-consultation.md:32)；JSON rules指针见附件 |
| LX0609-07-04-02 | 仅定位范围/目录核对，业务实现阅读未证明 | 只有客户缺收费来源、pending_definition和不执行范围核对；没有049收费比较实现阅读/反例。当前发布状态无需强启用。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/treatment-consultation.md:33)；JSON rules指针见附件 |
| LX0609-08-01-01 | 实质审查/反例可定位，源码阅读定位待补 | 7个061确定性函数边界实际结果可定位；当前报告未给061函数/模块行号，不能仅由7/7证明源码针对性阅读。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/discharge-death.md:13)；JSON rules指针见附件 |
| LX0609-08-01-02 | 针对性源码/合同阅读记录可定位（非整条验收） | native_extended_document_execution.py:3470-3509 / executor_registry.py:226-236：062完整性与医嘱一致性覆盖差异 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/discharge-death.md:14)；JSON rules指针见附件 |
| LX0609-08-01-03 | 针对性源码/合同阅读记录可定位（非整条验收） | native_extended_document_execution.py:2889-2895,373-394：063死亡诊断被出院记录存在性门控跳过 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/discharge-death.md:15)；JSON rules指针见附件 |
| LX0609-08-01-04 | 针对性源码/合同阅读记录可定位（非整条验收） | native_tumor_pathology_execution.py:1587-1624 / business基线108 / master230-236：027治疗或随访口径差异 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/discharge-death.md:16)；JSON rules指针见附件 |
| LX0609-08-01-05 | 仅定位范围/目录核对，业务实现阅读未证明 | 仅1个acceptance_only范围配置观察；没有诊疗经过内容充分性实现的阅读摘录/正常缺陷语义案例。业务实现未证明已审。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/discharge-death.md:17)；JSON rules指针见附件 |
| LX0609-08-02-01 | 针对性源码/合同阅读记录可定位（非整条验收） | extended_document/discharge_course.py:12 / _has_course_body：067纯签名/标题不能代临床正文 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/discharge-death.md:18)；JSON rules指针见附件 |
| LX0609-08-02-02 | 实质审查/反例可定位，源码阅读定位待补 | 4个068合成正式执行/聚合案例及历史角色/时间资料审查可定位；针对068源码分支的阅读位置未明确。 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/discharge-death.md:19)；JSON rules指针见附件 |
| LX0609-09-01-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_basic_timeliness.py:1171；basic_timeliness_facts.py:218 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:13)；JSON rules指针见附件 |
| LX0609-09-01-02 | 针对性源码/合同阅读记录可定位（非整条验收） | rescue_record_completeness.py:75,147,227,281,346 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:27)；JSON rules指针见附件 |
| LX0609-09-02-01 | 针对性源码/合同阅读记录可定位（非整条验收） | extended_document/death_discussion.py:43,89,94；native_extended_document_execution.py:3222 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:21)；JSON rules指针见附件 |
| LX0609-10-01-01 | 针对性源码/合同阅读记录可定位（非整条验收） | extended_document/physician_handoff.py；native_extended_document_execution.py:4420 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:22)；JSON rules指针见附件 |
| LX0609-10-02-01 | 针对性源码/合同阅读记录可定位（非整条验收） | extended_document/transfer_documentation.py:37,49,106；native_extended_document_execution.py:4469 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:23)；JSON rules指针见附件 |
| LX0609-10-02-02 | 针对性源码/合同阅读记录可定位（非整条验收） | extended_document/transfer_documentation.py:37,49；native_extended_document_execution.py:4469 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:24)；JSON rules指针见附件 |
| LX0609-10-03-01 | 针对性源码/合同阅读记录可定位（非整条验收） | phase_scope.py:121；native_extended_document_execution.py:3055 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:26)；JSON rules指针见附件 |
| LX0609-11-01-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_surgery_gate_execution.py:2492,2531,2580,2596 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:16)；JSON rules指针见附件 |
| LX0609-11-02-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_surgery_document_execution.py:775,1336 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:17)；JSON rules指针见附件 |
| LX0609-11-02-02 | 针对性源码/合同阅读记录可定位（非整条验收） | native_surgery_document_execution.py:798,828,837,1397 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:18)；JSON rules指针见附件 |
| LX0609-11-03-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_transfusion_execution.py:975,1018,3161 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:19)；JSON rules指针见附件 |
| LX0609-11-03-02 | 针对性源码/合同阅读记录可定位（非整条验收） | native_transfusion_execution.py:1059,1082,1089 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:20)；JSON rules指针见附件 |
| LX0609-12-01-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_course_quality_execution.py:833,857 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:14)；JSON rules指针见附件 |
| LX0609-12-01-02 | 针对性源码/合同阅读记录可定位（非整条验收） | native_course_quality_execution.py:694,740,1099 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:15)；JSON rules指针见附件 |
| LX0609-12-02-01 | 针对性源码/合同阅读记录可定位（非整条验收） | native_extended_document_execution.py:4516,4665；extended_document/diagnosis_change_extraction.py；luxian_0609_phase1_rule_contracts_extension_v1.json:267 | [组报告](F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.md:25)；JSON rules指针见附件 |

## 冻结与下一阶段

先补10条已有实质审查的源码阅读定位。6条范围/目录者按发布状态办理：08-01-05仅开关不能证明内容实现已审；暂停/未注册/客户源不可用条目不强行启用。若旧摘录仍无法定位，再由root决定有限补审范围；不重新铺开86条。

本附件没有新增通过/新增确认缺陷。所有代码问题当前状态见现行closure-issues；本次只确定已有证据出处及不足。主矩阵两次hash相同：

- catalog-coverage.json SHA256 61075f2c9603b1fbae929a64f528746739ebcaf5cfb32717b012f23b03a0ae87
- catalog-coverage.md SHA256 ae02d4983c80f2b0357e8ea3a214d64936d1a050c5e4082a8bea6426042bdfe4
