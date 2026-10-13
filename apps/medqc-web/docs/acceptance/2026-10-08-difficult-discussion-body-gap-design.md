# CT-03 讨论正文资料不足补充工程预期与最小设计

准备基线 `81fe8fed3027ea7f636014fd59237819138f7f9c`。CT-02已独审通过并集成7d36d0316。root追加的CT-02 local成熟+另一缺时候选疑点已由独审观察通过，未证实，不据此改源码；本次仅实施root批准的CT-03物理正文可用性分支。

原独立冻结 `.tmp/engine-audit-20261008/course-timing/expected.json` 中 `050_blank_discussion=data_gap_or_non_compliant` 保留，SHA256 `37ec08e8d766b9a071bd0bc60f7ae3ead925239ff22225c0c9181a1da9285752` 不变。以下为root明确的**新增工程预期**，供独立审计另附冻结，不覆盖原记录，不代表新增临床签认。

所有新增正文场景复用原入院2026-06-01 08:00:00、病程2026-06-08 09:00:00“目前诊断仍不明确。”和真实讨论行ID/时间，不补正文：

| 已读取的讨论资料                                 | 新增工程预期                                 |
| ------------------------------------------------ | -------------------------------------------- |
| record_content缺键                               | data_gap，已定位行但正文资料不足             |
| record_content=None                              | 同上                                         |
| record_content非字符串（数字、bool、list、dict） | 同上；不能用str()转成正文                    |
| record_content=""或仅空白                        | 同上；不能证明C或认定医生漏写                |
| 两条及更多上述空/不可读行                        | 同上；行数不证明完成                         |
| 一条空行+一条可用非空字符串正文，两个排列顺序    | 沿现有C路径，不能仅因空行覆盖已存在可用正文  |
| 无讨论行                                         | 保留旧NC/required_document_missing           |
| 有短有效非空字符串正文                           | 沿旧路径；不新增字数、关键词或临床充分性判断 |

“可用正文”本项仅指record_content是字符串且strip后非空，不包括通过标题、签名、ID或时间补造正文。非空正文是否对应当前诊断问题、是否只写计划/否定、语义是否充分，仍属CT-01/N10及CT-R02后续口径；本项不靠“拟/未/计划”词表关闭，不改变提前讨论关联规则。

## 实际合同与限定实施方向

规则为 `LX0609-03-02-01`（旧050）。phase1目录/执行合同仍program_only/0、Prompt=none、文书存在性。source_registry050支持入院登记/入院记录/daily_course_record/diffcase_discussion_record。source_evidence_reader:586白名单只有讨论document_id/title、四权威记录/提交时间及record_content，没有“临床讨论已完成”状态；来源COMPLETE只证明查询/快照范围，不能证明正文可读。

当前native:2356仅因diffcase_rows非空判C。窄修应在既有源错误、缺入院时间、CT-02时间缺口、无成熟强候选和局部scope未知之后，针对**已确认成熟强候选**独立检查讨论正文：无行仍旧NC；有行且全部正文缺失/不可用则data_gap/required_field_missing；至少一份非空字符串沿旧C。discussion_count保留资料行计数语义，正常旧facts不变，不把空行说成已形成可用正文。

新增050白名单kind `uncertain_diagnosis_discussion_body_gap`，包含有效admission_time、非空成熟强uncertain_record_times、正整数非bool discussion_count、与全部讨论行数相等的discussion_body_gap_count；仅允许data_gap。CT-02缺时计数若同时存在，可保留其正整数安全摘要，仍不能改为确定C/NC或虚构触发。没有成熟强候选时不进入此正文分支，继续CT-02或旧scope判断。

必要文件仅：native_extended050；difficult_case_result_mapping新kind/必要值与status严格、旧无摘要兼容；customer_renderer050说明“已读取讨论行但正文缺失或不可用，无法核对内容，请核对源系统正文及同步”，不催医生补写/倒签；Finalizer050新kind窄status门禁（root已授唯一窄锁，保留RR-PUB sentinel）；新专属测试与本文。保持既有sanitizer过滤额外键，不能把它改成所有未知键拒绝；新kind/必要值/status矛盾仍严格拒绝。无目录、Prompt、shared时间解析、Reducer、Store/API或其他规则变更。

证据使用真实讨论ID对应的合法文书引用；无ID只用已有source/snapshot可核锚，不造ID、原文或精确位置。空正文是否可通过既有公共投影形成仅含真实ID/时间的资料定位，实施前检查既有合同；不能为了有证据卡扩共享projector或伪造摘录，无法精确投影时应明确定位能力缺口。

## 冻结与执行记录

独立新增工程冻结位于 `F:/MedQC-worktrees/review-artifacts/ct03-closure/expected-v1.json`，28组；保留原gap_or_NC预期。正文缺口原因为required_field_missing，discussion_count为已读取资料行数，discussion_body_gap_count等于所有不可用行数。额外内部字段仍按白名单过滤，不改成拒绝全部未知字段。

新专属测试52项，首轮在未改生产的81fe执行21失败/31通过，日志 `.tmp/ct03-closure/red.log`。目标红包括：空正文误C、正文新kind未识别、旧technical_error放行、正文计数附到旧kind被过滤后仍接受，以及保存前已误C。另两项保护预期需分开说明：local-only公开uncertain对应归约evaluation_unknown，已修正层级对照，原业务含义不变；未满7天且已有讨论行原生/归约NA，公开technical_error，是新发现既有CT04候选，保留应NA断言不改成技术错误求绿。中间红复验20失败/32通过有1条误用RuleDecision.final_state的测试笔误，日志 `.tmp/ct03-closure/red-corrected.log`，不计为产品问题；现已独立命名CT04候选并恢复真实公开应NA断言。

限定实施：native只在050成熟强候选后检查record_content字符串且strip非空；无行、短有效正文及混合可用正文保持旧路径/原facts。正文gap和候选缺时共存时保留成熟时刻/两计数；time_gap_only限定authoritative_time_missing，不将正文gap误归无成熟记录的纯时间kind。mapping只新增正文kind/必要计数与status匹配，Finalizer只扩050既有谓词，renderer只扩050正文gap文案及原structured_suggestion保护。CT-01语义、其他规则、目录、Prompt、共享时间解析/公共投影、Reducer、Store/API未改。

有唯一真实讨论ID时使用原合法文书引用，空正文可以形成真实ID/时间资料定位；无ID时保留可读来源快照锚，无精确讨论ID，客户最多展示其他已精确定位来源，不制造讨论卡或摘录。公开facts不携带原文/ID。待唯一绿槽：完整52新+既有050/CT02/Finalizer/RR-PUB保护一次；CT04应NA失败单列，不宣称整套全绿。纯合成SQLite用新Engine/新Store回读，不代表真实API、临床或真实模型验收。

完整218项（52专属+166既有）首次限定复验为214通过/4失败，日志 `.tmp/ct03-closure/green-complete.log`。既有166项及CT03业务/公开合同均通过；4失败分为保留CT04应NA1项，以及3条SQLite新增证据断言误用保存后已被签名移除的原始source_document_id。修正为真实ID生成的规范keyed_ref/source_ref后，3条短复验为2通过/1失败，日志 `.tmp/ct03-closure/sqlite-corrected.log`：两个正文gap已证明原来源/时间/字段及可用摘录保存；mixed_c另有旧投影范围限制，原来源级公共投影只有该来源唯一一行时可补精确ID，多讨论行不能猜选任一ID。本轮不扩公共投影，因此mixed_c保护应证明两个冻结材料实际可读、讨论来源锚非空、病程真实source_ref/时间/field_path/摘录准确，公开无猜造讨论卡；不能宣称多讨论行逐份精确定位通过。两次完整/短测输出保留，不以过滤或改临床应NA预期求全绿。

源码限定校验 `.tmp/ct03-closure/frozen-verification.json` 已证明native050以外逐字一致、Finalizer只有已授050谓词扩展，触发器、共享时间、source_registry、074两个data、旧native/mapping/CT02/RR-PUB/renderer测试未改，1147个前端源码/配置hash保持原门禁输入。Ruff已检查新增测试和mapping，无问题；最终提交前再核限定路径与编码。前端代码未变，继承本批lint既有证据（0错误、1214既有警告）；此前type-check因资源终止、全量前端unit未运行，不宣称通过。PG、.env、网络、真实模型均未执行。
最终仅复验上述3条SQLite，新Engine/新Store均通过（3 passed，2.08秒），日志 `.tmp/ct03-closure/sqlite-final.log`。正文gap/正文gap兼候选缺时准确回读来源签名、原时间及无虚造摘录；mixed_c保留两讨论材料来源锚与精确病程字段/摘录。未重新运行完整218套件，CT04既有应NA失败仍保留；结论限定为CT03目标与既有保护已通过，不宣称218全部通过。固定原独立冻结SHA256 `c92061e62c1d0049f4d68ea007e774cb43ef54c81672289dba78134afe29ad9e`；新专属测试最终SHA256 `a82593c7ac28fbd40bc5b8f602d699d3035efb5de9814c896e323f7467ef97b9`。
