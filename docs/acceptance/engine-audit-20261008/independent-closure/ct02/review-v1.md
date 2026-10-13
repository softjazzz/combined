# CT-02 独立有限关闭复审

结论：建议在固定提交 `81fe8fed3027ea7f636014fd59237819138f7f9c` 上关闭 CT-02 的工程缺陷，即 LX0609-03-02-01（旧 050）候选病程缺少可用权威时间被误判为 NA。本次未确认阻断缺陷。该结论限于合成离线工程验证；CT-01 语义词匹配、CT-03 空白讨论、CT-R02 疑难讨论反例仍待原协调复核，0916 已被用户排除。

修复目录：`F:/MedQC-worktrees/qc-fix-critical-v2-20261008`。基线：`bb3d0b5c3762ea7a0c8aa0580af8ec666794347b`。已读完整六路径 diff，六路径在独立执行前后均与固定提交字节一致，SHA256 明细见 observed-v1.json 与 projection-review-v1.json。独立原冻结和原观察文件未修改。

冻结的 28 组预期来自基线、原 course-timing 报告与最小关闭设计，在本组独立执行前冻结。冻结完成时 owner 工作树已有修改，因此不声称冻结早于 owner 实现。完成冻结前未读取 owner 实现或新增测试；之后在固定提交上核完整 diff。根追加的混合 local/缺时疑点另冻结两组，未替换原 28 组。

| 验收项 | 独立证据与实际行为 | 结论 |
|---|---|---|
| 缺时候选不再误 NA | G01 原反例、G02 无效时间、G03 null/空白、G08 local 缺时、G10 created/updated/title 日期、G12 两候选均为 data_gap/authoritative_time_missing；新 kind=uncertain_diagnosis_course_time_gap、record_times=[]、缺口计数为实际候选数 | 通过 |
| 讨论不能填补候选时间 | G04 已有讨论仍 gap；计数与讨论证据保留，不冒称候选已满七天 | 通过 |
| 成熟强触发结论保护 | G05/G06 成熟 strong+缺时及反序均保持 NC/required_document_missing；G07 已有讨论保持 C/requirement_satisfied。facts 保留成熟时间，附缺口计数 1，文案明确已确认结论保留 | 通过 |
| 七天与未触发保护 | P01 恰满七天与 P03 超一秒为 NC，P02 差一秒、P04 非候选、P05 完整空来源为旧 NA；P06 正常成熟加讨论为 C，P07 仅成熟 local 保持 uncertain；P08/P09 来源与入院时间缺口保持原优先级 | 通过 |
| 时间来源与时区 | A01-A04 四合法时间别名、A05 空白高优先级回退、A06 UTC 与 A07 +08 同一边界保持 NC；G09 无效非空高优先级时间不偷用下级字段 | 通过 |
| 混合 local/缺时补充疑点 | S01 成熟 local+缺时 strong，S02 成熟 local+缺时 local，均为 data_gap 且新 kind record_times=[]。实现 gap 分支取 strong_uncertain_rows，不取 local 列表；未复现所疑 technical_error | 通过，原疑点不成立 |
| Binding/Finalizer/Renderer 文案 | 全 30 场景 native→binding→finalizer 结果一致。纯 gap 建议保留“核对源系统时间及同步”，structured_suggestion 未覆盖；不把缺时说成七天强触发或“未触发” | 通过 |
| 公开 kind/status/count | 25 项公开合法/非法约束通过：新 kind 仅 data_gap；C/NC/NA/uncertain/technical_error/其他 status 拒绝；零/负数/bool/字符串/小数/null 缺口数拒绝；非法枚举组合及讨论数拒绝。必需字段检查另以固定源码核对，不声称每种字段缺失均有独立动态测试 | 通过，限定已列覆盖 |
| 公共 facts 无私有透传 | document_id、raw_payload、extra 三次公开调用均过滤为五个合法字段，标记 SYN-PRIVATE 未出现 | 通过；原拒绝预期过强 |
| 无 ID 不伪定位 | G11 customer_evidence 为空；native fact_refs 含实际 daily source snapshot SHA，material 中能按该实际来源读取候选原合成 row；未捏造 document ID 或记录时间 | 通过 |
| 正常旧事实和建议 | 16 个 P/A 场景对完整基线 native/renderer/finalizer 逐字段比较 status、reason、facts、findings、suggestion、evidence，均一致 | 通过 |
| 保存/重新加载 | G01/G05/G07 使用新合成 SQLite、生产 CanonicalResultStore 写入，关闭并重开引擎读取。极窄补验对已有库只读，独立断言 source_type、field_path、摘录和时间逐值正确，锚非空且无原 ID；纯缺时证据无 record_time | 通过 |

原始 observed-v1.json 如实保留了公开约束 25/28 与三次保存 raw-format 比较失败。它们不构成六个产品缺陷：

1. 三个 extra-key 用例原预期“出现即拒绝”超出批准合同。批准合同要求原文、ID、raw payload 不进入公共 facts，并对新 kind 的枚举、计数与 status 严格校验；旧 050 sanitizer 本来过滤额外字段。本次只补充合同解释，不重写原冻结，也不建议扩大为全部拒绝。
2. 保存投影将 generic evidence 字符串与 customer_evidence 列表归一为安全 evidence 列表，source_document_id 被 HMAC source_ref 替代，customer_evidence 不再重复公开。字段名 source_type、field_path、evidence_excerpt、excerpt_kind=文书级依据均存在。G01 缺时摘录保留但无时间；G05 成熟时间 2026-06-08 09:00:00 保留；G07 讨论时间 2026-06-09 09:00:00 及原合成讨论摘录保留。独立预期来源/时间/字段/摘录逐项 assert 通过；另调用生产 projector 仅解释归一格式，不将同函数自比算独立定位证据。

边界：本次未接触原始患者材料、.env、PG、网络或真实模型；离线防护记录为零越界调用。未运行 owner 测试（开发 166 绿只作线索），生产文件与共享测试均未改。独立探针使用旧合成 fixture 的 AST 构造函数，因此并不覆盖数据库实际适配器、浏览器或真实脱敏记录到 UI 的全链路。工程关闭不代表临床规则语义关闭。

过程记录：主探针首轮因独立 AST table factory 环境缺 lru_cache 终止，修正自有脚本后完整执行完成。极窄证据脚本先校准自有“病情级摘要/source_key”的非合同格式假设为实际 source_type、非空 excerpt_kind，原来源/时间/字段/摘录预期不变；最终运行通过。以上均为探针准备问题，未修改生产或冻结预期。

出处：expected-v1.json SHA256 `343b6e283e886196d8ecc11078a033a061f226c6a0889c25f18cc4060a14f889`；supplemental-expected-v1.json SHA256 `e792579940be942a4557d31a58df7d6913eab98d3784f72135f32213698f902e`；observed-v1.json SHA256 `425654f65f3e3e1896fadc4333dfd4cfe6ffaf48534940ee43e4e0892c282368`。独立脚本、合成库和补验输出同目录。两轮测试槽均已释放，无运行进程。
