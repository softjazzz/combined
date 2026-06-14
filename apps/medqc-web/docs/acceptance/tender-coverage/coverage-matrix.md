# 招标功能覆盖矩阵

更新时间：2026-06-07

状态说明：

- `implemented`：已有代码、测试或验收证据支撑，剩余主要是演示和回归。
- `partial`：有核心链路或页面，但缺正式数据源、闭环、字段覆盖、稳定测试或验收证据。
- `missing`：只有基础依赖或零散能力，缺少可独立验收的功能闭环。

## 总览

| 条款  | 功能                     |        状态 | 责任域                | 演示入口                                           |
| ----- | ------------------------ | ----------: | --------------------- | -------------------------------------------------- |
| 3.1.1 | 首页自动生成             | implemented | frontpage-generation  | workstation-v4 病案详情 / 病案首页 / 结算清单      |
| 3.3.1 | 质控规则                 | implemented | formal-qc             | 质控规则管理 / 首页质控 / 结算清单质控             |
| 3.4.1 | ICD 编码规范内涵质控     | implemented | coding-qc             | ICD 编码规范内涵质控 / 质控规则管理                |
| 3.4.3 | 诊断及手术操作完整性校验 | implemented | clinical-completeness | 病历详情 / 诊疗完整性                              |
| 3.5.1 | 智能编码                 | implemented | icd-coding            | ICD 编码查询 / 质控助手编码查询 / 病案首页编码建议 |
| 4.1.2 | 病案问题概览             | implemented | notification-overview | 工作台右侧助手 / 问题概览                          |
| 6.1.1 | 基于病历信息的自动化入组 | implemented | pre-grouping          | DRG/DIP 分析 / 事前分析                            |
| 6.2.1 | 预入组及修正建议         | implemented | grouping-correction   | DRG/DIP 分析 / 事前分析 / 分组器                   |
| 6.2.2 | 分组器本地化适配         | implemented | grouper-config        | DRG/DIP 分析 / 分组器 / 本地化配置                 |
| 6.2.3 | 医保付费监测             | implemented | payment-monitoring    | DRG/DIP 分析 / 付费监测                            |
| 6.3.1 | DRG/DIP 综合分析         | implemented | drg-analysis          | DRG/DIP 分析 / 事后分析                            |

## 逐项覆盖

### 3.1.1 首页自动生成

- 状态：`implemented`
- 后端证据：
  - `backend/app/routers/frontpage.py`
  - `backend/app/routers/case_front_page.py`
  - `backend/app/schemas/frontpage_generation_contract.py`
  - `backend/app/services/frontpage_extraction_service.py`
  - `backend/app/services/frontpage_report_generation_service.py`
  - `backend/app/services/settlement_assembly_service.py`
- 前端证据：
  - `src/views/workstation-v4/components/FrontpageWorkspace.vue`
  - `src/views/workstation-v4/components/SettlementWorkspace.vue`
- 测试证据：
  - `backend/tests/unit/test_frontpage_report_generation_service.py`
  - `backend/tests/unit/test_frontpage_extraction_service.py`
  - `backend/tests/unit/test_frontpage_tender_field_extraction.py`
  - `backend/tests/unit/test_frontpage_export.py`
  - `tests/unit/test_demo_case_loader.py`
  - `tests/unit/test_frontpage_generation_contract.py`
  - `tests/unit/test_frontpage_auto_generate.py`
  - `tests/unit/test_frontpage_procedure_detail_extraction.py`
  - `tests/unit/views/workstation-v4/frontpage-field-coverage.spec.ts`
- 当前证据：
  - 统一生成接口支持病案首页和医保结算清单草稿。
  - 已有诊断、手术编码建议、入院病情推理和部分其他医疗信息归一化。
  - 导出格式包含卫健委标准首页、医保病案首页、医保结算清单。
  - 已建立 tender 级首页生成字段契约并校验当前结算映射。
  - `auto-generate-draft` 在缺少病历正文/文书时返回 `requires_data`，避免 demo 数据伪装成功。
  - `auto-generate-draft` 支持仅传 `visit_id` 时加载真实病历文书正文并生成草稿，未命中真实文书时不启用 demo 兜底。
  - 手术细项归一化支持中文键、别名键和嵌套 `main_procedure` 结构。
  - 前端首页/结算清单工作区展示字段覆盖分组摘要和优先补全字段。
- 缺口：无当前阻断项。

### 3.3.1 质控规则

- 状态：`implemented`
- 后端证据：
  - `backend/app/routers/qc.py`
  - `backend/app/services/frontpage_formal_qc.py`
  - `backend/app/services/qc_rule_coverage.py`
  - `backend/app/services/settlement_formal_qc.py`
  - `backend/app/services/unified_rule_engine.py`
- 前端证据：
  - `src/views/workstation-v4/WorkstationRulesView.vue`
  - `src/views/workstation-v4/components/WorkstationV4RulesView.vue`
- 测试证据：
  - `backend/tests/unit/test_frontpage_formal_qc.py`
  - `tests/unit/test_qc_rule_coverage.py`
- 当前证据：
  - 首页正式质控包含必填、格式、逻辑、一致性规则。
  - 结算清单正式质控包含必填、格式、逻辑、一致性规则。
  - 已建立规则覆盖注册表，可按标准来源、适用对象、分类、严重度和字段统计规则覆盖。
  - 已提供只读规则覆盖审计 API，并在质控规则管理页展示首页、结算清单、完整性、逻辑一致性覆盖情况。
- 缺口：无当前阻断项。

### 3.4.1 ICD 编码规范内涵质控

- 状态：`implemented`
- 功能边界：
  - 本条款验收对象是 ICD 编码规范、医保版/国临版映射、诊断/手术编码组合、病案首页字段与费用字段之间的编码逻辑一致性。
  - 不把病程记录、查房记录、主诉、现病史等文书书写质量作为本条款验收对象；疾病诊断/手术操作画像和首页书写辅助对照归入 `3.4.3`。
- 后端证据：
  - `backend/app/routers/qc.py`
  - `backend/app/services/coding_qc_service.py`
  - `backend/app/data/coding_rules.json`
- 前端证据：
  - `src/components/rules/CodingRulesTab.vue`
  - `src/views/workstation-v4/semantic-rules/components/SemanticRulesOverviewPanels.vue`
  - `src/views/workstation-v4/WorkstationRulesView.vue`
- 测试证据：
  - `backend/tests/unit/test_coding_qc.py`
  - `backend/tests/unit/test_coding_qc_api.py`
  - `tests/unit/test_coding_connotation_qc.py`
- 当前证据：
  - 已有 ICD 编码合并、互斥、主诊断、主手术、附加编码、医保版/国临版映射和一致性审查提示。
  - 规则数据包含阑尾炎伴腹膜炎、肿瘤形态学编码、冠脉支架附加编码、病理编码费用关联。
  - 投标示例已转为确定性规则：肿瘤病理 M 码、病理费一致性、阑尾炎伴腹膜炎合并编码、冠脉支架附加编码。
  - 编码内涵规则通过现有 `/api/v1/qc/coding-qc/check` 进入统一质控问题持久化结构。
  - 编码质控规则页已提供可执行验收样例，直接调用真实 ICD 编码规范内涵质控接口并展示规则问题、问题数量和只读边界。
- 专项验收用例：
  - 肿瘤主诊断编码存在时，校验病理诊断编码或形态学 M 码是否缺失或不一致。
  - 病理编码存在时，校验病理诊断费、病理诊断名称和首页相关字段是否一致。
  - 阑尾炎与腹膜炎诊断同时存在时，提示是否需要按 ICD 规则合并编码并给出推荐。
  - 冠状动脉支架置入术存在时，提示补充共同使用的必要附加编码。
  - 诊断编码、手术操作编码与 DRG/DIP 预入组输入不匹配时，提示编码修正建议但不写正式结果。
- 缺口：无当前阻断项。

### 3.4.3 诊断及手术操作完整性校验

- 状态：`implemented`
- 当前阶段验收边界：
  - 按招标参数字面验收“疾病诊断画像、手术操作画像、诊断发生发展时间轴、手术操作执行与否验证、首页书写辅助对照”五项能力。
  - 不要求在当前阶段整合手术记录、麻醉记录、医嘱、费用、手术相关单据等多源证据来严格证明“是否真的执行”；该能力归入后续增强。
- 后端证据：
  - `backend/app/main.py`
  - `backend/app/routers/clinical_completeness.py`
  - `backend/app/schemas/clinical_timeline.py`
  - `backend/app/services/clinical_timeline_service.py`
  - `backend/app/routers/frontpage.py`
  - `backend/app/services/diagnosis_surgery_profiling_service.py`
  - `backend/app/services/frontpage_extraction_service.py`
  - `backend/app/services/bundles/assembly.py`
- 前端证据：
  - `src/views/workstation-v4/components/ClinicalCompletenessPanel.vue`
  - `src/views/workstation-v4/components/WorkstationV4DetailView.vue`
  - `src/views/workstation-v4/components/WorkstationV4AssistView.vue`
  - `src/views/workstation-v4/frontpage/components/AIProfileDashboard.vue`
- 测试证据：
  - `tests/unit/test_clinical_completeness_router.py`
  - `tests/unit/test_clinical_timeline_service.py`
- 当前证据：
  - 已有病历 bundle 和首页抽取证据基础。
  - 已有只读临床完整性 API 骨架：`GET /api/v1/clinical-completeness/{visit_id}`。
  - 已有轻量诊断/手术时间轴数据结构，可在单元测试夹具中识别诊断证据、手术计划和手术执行。
  - `ClinicalCompletenessPanel` 将诊断证据、手术/操作证据、时间轴、执行验证和首页书写提示按只读辅助方式展示。
  - `AIProfileDashboard` 通过 `/api/v1/frontpage/profile/analyze` 承载疾病诊断和手术操作画像分析。
  - 接口安全声明明确不写正式病案首页、医保结算清单或正式质控结果。
- 缺口：无当前阻断项。
- 后续增强：
  - 可继续接入手术记录、麻醉记录、医嘱、费用和手术相关单据，提升手术操作执行验证的证据强度。
  - 可继续把画像与病案首页生成页做更强联动，例如在首页字段旁显示画像对照来源和差异原因。

### 3.5.1 智能编码

- 状态：`implemented`
- 后端证据：
  - `backend/app/routers/icd_search.py`
  - `backend/app/services/local_icd_service.py`
  - `backend/app/services/icd_coding_service.py`
  - `backend/app/services/qc_agent/tools.py`
- 前端证据：
  - `src/views/workstation-v4/components/FrontpageWorkspace.vue`
  - `src/views/workstation-v4/components/SettlementWorkspace.vue`
  - `src/views/workstation-v4/components/QCAgentChatDrawer.vue`
- 测试证据：
  - `backend/tests/unit/test_case_front_page_extract.py`
  - `backend/tests/unit/test_frontpage_extraction_service.py`
  - `backend/tests/unit/test_icd_search_contract.py`
  - `tests/unit/test_record_coding_suggestions.py`
- 当前证据：
  - ICD 查询支持诊断、手术操作、医保版、国临版和映射信息。
  - 本地 ICD 服务支持精确、模糊和可选语义兜底。
  - ICD 查询响应已收敛为候选卡契约，包含编码类型、版本、匹配方式、置信度和映射信息。
  - ICD 查询响应测试覆盖原始响应、向量、内部路径、病历正文等敏感字段过滤。
  - 当前病历编码建议已用固定夹具验证主诊断、其他诊断、手术操作、业务来源和候选编码稳定性。
- 缺口：无当前阻断项。

### 4.1.2 病案问题概览

- 状态：`implemented`
- 后端证据：
  - `backend/app/routers/notifications.py`
- 前端证据：
  - `src/views/workstation-v4/composables/useNotifications.ts`
  - `src/views/workstation-v4/components/WorkstationV4AssistView.vue`
- 测试证据：
  - `backend/tests/unit/test_notifications_overview_router.py`
  - `tests/unit/views/workstation-v4/useNotifications.spec.ts`
- 当前证据：
  - 当天问题按类型、严重度、科室、病历聚合。
  - 已有概览/明细切换、筛选、点击联动和验收报告。
  - 通知概览后端测试覆盖同日聚合、严重度排序、嵌套科室提取和日期格式校验。
  - 前端通知 composable 测试覆盖概览接口失败后的本地聚合回退、批量汇总过滤、已读标记和病历定位。
- 缺口：无当前阻断项。

### 6.1.1 基于病历信息的自动化入组

- 状态：`implemented`
- 后端证据：
  - `backend/app/routers/case_front_page.py`
  - `backend/app/routers/pre_grouping.py`
  - `backend/app/services/frontpage_extraction_service.py`
  - `backend/app/services/pre_grouping_diff_service.py`
  - `backend/app/services/pre_grouping_event_service.py`
  - `backend/app/services/dip_grouping_service.py`
  - `backend/app/services/drg_grouping_service.py`
- 前端证据：
  - `src/views/workstation-v4/frontpage/components/PreAnalysisView.vue`
  - `src/api/drg.ts`
- 测试证据：
  - `backend/tests/unit/test_case_front_page_extract_pre_group_fast.py`
  - `backend/tests/unit/test_case_front_page_extract.py`
  - `tests/unit/test_pre_grouping_diff_service.py`
  - `tests/unit/test_pre_grouping_event_service.py`
  - `tests/unit/views/workstation-v4/frontpage/pre-analysis-auto-update.spec.ts`
- 当前证据：
  - 事前分析支持手动抽取和 DIP/DRG 预判。
  - 入院导向抽取接口不要求出院诊断。
  - 新增入院记录完成事件服务，按 `visit_id` / `document_id` 生成只读模拟入组版本。
  - 自动化入组事件结果包含输入 hash、版本、DIP/DRG 模拟结果和不写正式表安全声明。
  - 预入组差异服务已比较主诊断、其他诊断数量、手术数量、年龄、住院日和费用变化，并写入 `change_tracking`。
  - 事前分析页已读取最新自动模拟历史，展示版本号、生成时间、是否需要重新入组以及变化字段。
  - 已提供 `admission-note-completed/from-visit` 入口，可按 `visit_id` 加载真实病历文书触发自动预入组，未命中真实文书时不启用 demo 兜底。
  - 事前分析页抽取完成后会创建后端只读模拟历史，支持病历书写变化后的版本追踪。
- 缺口：无当前阻断项。

### 6.2.1 预入组及修正建议

- 状态：`implemented`
- 后端证据：
  - `backend/app/routers/pre_grouping.py`
  - `backend/app/services/dip_grouping_service.py`
  - `backend/app/services/drg_grouping_service.py`
  - `backend/app/services/grouping_correction_service.py`
- 前端证据：
  - `src/views/workstation-v4/frontpage/components/PreAnalysisView.vue`
  - `src/api/drg.ts`
- 数据源：
  - `backend/app/data/luzhou_dip_groups.json`
  - `backend/app/data/drg_weights.json`
- 测试证据：
  - `backend/tests/unit/test_drg_analysis_router.py`
  - `tests/unit/test_luzhou_dip_grouping_service.py`
  - `tests/unit/test_drg_weight_lookup.py`
  - `tests/unit/test_grouping_correction_service.py`
- 当前证据：
  - DRG 服务支持远程分组和本地降级。
  - 已有 DIP/DRG 预判 UI。
  - 后端 DIP 服务已读取泸州市 DIP 核心和综合病种 JSON，返回分值、病种属性和基层病种标识。
  - DRG 服务已读取 2024 绩效监测权重 JSON，补齐权重、低风险组标识和本地降级来源。
  - 已提供只读预入组修正建议服务，覆盖缺主诊断、未入组诊断候选、手术候选和更高分值入组选项。
  - 事前分析结果卡已接入预入组修正建议接口，按当前主诊断、手术编码和分组结果展示候选修正，不写正式结果。
- 缺口：无当前阻断项。

### 6.2.2 分组器本地化适配

- 状态：`implemented`
- 后端证据：
  - `backend/app/services/dip_grouping_service.py`
  - `backend/app/services/drg_grouping_service.py`
  - `backend/app/services/drg/config_service.py`
  - `backend/app/services/drg_config_store.py`
- 前端证据：
  - `src/views/drg/GrouperConfig.vue`
  - `src/api/drg.ts`
- 数据源：
  - `backend/data/drg_grouper_config_store.json`
  - `tests/fixtures/grouper_consistency_acceptance_samples.json`
- 测试证据：
  - `backend/tests/unit/test_drg_config_router.py`
  - `tests/unit/test_grouping_config_runtime.py`
  - `tests/unit/test_drg_config_consistency_real_samples.py`
- 当前证据：
  - 支持配置读取、保存、发布、版本、回滚、审计和一致率校验。
  - 已有验收报告记录样本一致率。
  - 已发布配置参与 DIP/DRG 运行时计算，分组结果返回 `config_version_id`、费率、医院系数、地区系数及高低费用阈值。
  - 一致率校验支持 `expected_group` / `expected_drg` / `expected_dip` 对照字段，并返回差异原因和无效样本。
  - 已补充 20 条医保对照验收样本并用单元测试验证一致率不低于 95%。
- 缺口：无当前阻断项。

### 6.2.3 医保付费监测

- 状态：`implemented`
- 后端证据：
  - `backend/app/routers/payment_monitoring.py`
  - `backend/app/services/payment_monitoring_service.py`
  - `backend/app/services/drg/analysis_service.py`
- 前端证据：
  - `src/views/workstation-v4/frontpage/components/PaymentMonitoringView.vue`
  - `src/api/drg.ts`
- 数据源：
  - `backend/app/data/drg_weights.json`
  - `backend/app/data/luzhou_dip_groups.json`
  - `src/views/drg-grouper/drgWeightData.ts`
  - `src/views/drg-grouper/luzhouDipData.ts`
- 测试证据：
  - `tests/unit/test_payment_monitoring_service.py`
  - `tests/unit/views/workstation-v4/frontpage/payment-monitoring.spec.ts`
- 当前证据：
  - 前端已有总费用、预计支付、支付率、盈亏风险和趋势展示。
  - 后端已提供付费监测模拟服务，按地方运行时配置计算预计支付、实际费用、盈亏、医保支付率、基础组/费用极高/极低组和控费提示。
  - 前端 API 层已提供 `simulatePaymentMonitoring` 调用入口。
  - 付费监测页面已优先调用后端模拟接口，失败时展示降级状态并保留不写正式结果安全提示。
  - 付费监测服务测试覆盖预计支付、实际费用、盈亏、支付率、基础组/极高费用组/极低费用组和安全边界。
- 缺口：无当前阻断项。

### 6.3.1 DRG/DIP 综合分析

- 状态：`implemented`
- 后端证据：
  - `backend/app/routers/drg_analysis.py`
  - `backend/app/services/drg/analysis_service.py`
- 前端证据：
  - `src/views/workstation-v4/frontpage/components/PostEventAnalysisView.vue`
  - `src/api/drg.ts`
- 测试证据：
  - `backend/tests/unit/test_drg_analysis_router.py`
  - `tests/unit/test_drg_analysis_dimensions.py`
  - `tests/unit/test_drg_analysis_metrics.py`
  - `tests/unit/test_drg_analysis_exports.py`
- 当前证据：
  - 后端可计算组数、CMI、费用消耗指数、时间消耗指数、低风险死亡率、平均住院日、平均费用、医保盈亏。
  - 分析导出支持 excel、pdf、docx。
  - 分析维度已支持院级、科级、病区、主诊医师组、个人、诊断组和 DRG，`doctor` 作为 `person` 兼容别名。
  - 真实感夹具已校验 DRG/DIP 组数、CMI、费用消耗指数、时间消耗指数、低风险组死亡率、平均住院日、平均费用、医保盈亏及科室/诊断组/医师盈亏。
  - 传入 `session_id` 时综合分析只读取该 session 的正式上传/批量分组数据，空 session 返回空结构，不再回退演示库。
  - 事后分析页面已接入 `/api/v1/drg/analysis` 和 `/api/v1/drg/analysis/export/{format}`，页面指标与导出使用同一分析模型。
- 缺口：无当前阻断项。
