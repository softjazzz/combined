# 入院与病史族第一轮引擎审查

审查日期2026-10-08；工作树 `F:\MedQC-worktrees\qc-integration-20261008`；起始HEAD `7b894dc84491b7b72eb096de58fe61f772cc0080`；落盘HEAD `6930540f27e9c279241d35ac05d1c1c6e9134f82`（主协调提交验收规划文档，本组审计生产文件git diff为零）。实际纳入16条，逐条已审，未审0。

第一轮结论：确认1项共享来源绑定缺陷，覆盖0916-001至007。001/002/003/004/007可形成错误来源的合规或不合规结论；005/006临床结论由二次引用保护降为资料不足，但锚点及文书可用事实仍错误。另001次数源合同保留1项争议。0609本轮未确认新缺陷，不代表整体通过。

## 范围与逐条结论

| rule_id | 质控点 | 首要结论 | 离线证据 | 尚缺证据 |
| --- | --- | --- | --- | --- |
| LX0609-01-01-01 | 入院记录24小时时限 | 已审；已审 | 24h整点compliant、+1秒non_compliant，原生→归约→Finalizer保持，0模型。 | 真实当前版本原始字段/完成时间含义与正式保存/页面同源未验 |
| LX0609-01-02-01 | 首次病程8小时时限 | 已审；已审 | 8h整点compliant、+1秒non_compliant，原生→归约→Finalizer保持，0模型。 | 真实当前版本原始字段/完成时间含义与正式保存/页面同源未验 |
| LX0609-02-01-01 | 主治48小时首次查房 | 已审；已审 | 48h整点compliant、+1秒non_compliant，原生→归约→Finalizer保持，0模型。 | 真实当前版本原始字段/完成时间含义与正式保存/页面同源未验 |
| LX0609-02-01-02 | 副主任及主任72小时首次查房 | 已审；已审 | 72h整点compliant、+1秒non_compliant，原生→归约→Finalizer保持，0模型。 | 真实当前版本原始字段/完成时间含义与正式保存/页面同源未验；最高级别含糊职称抽取需真实模型 |
| LX0609-02-01-03 | 稳定患者3天查房病程 | 已审；已审 | 72h整点及+1秒通过原生→Finalizer，0模型。 | 缺时容量下界、多区间真实全源病例与正式保存回读未验 |
| LX0609-02-01-04 | 病重患者2天查房病程 | 已审；已审 | 完整空严重医嘱→not_applicable/trigger_absent_complete，0模型。 | 病重起止重开真实样本不足；本轮未复现全部阳性自然日分支 |
| LX0609-02-01-05 | 病危每日病程及病情变化记录 | 待真实模型；已审 | 完整空严重医嘱→not_applicable/trigger_absent_complete，0模型。 | 真实变化事件与检验/病程多源对应未验；阳性每日覆盖、变化误抽均需独立样本 |
| LX0609-01-01-02 | 主诉20字及第一诊断方向 | 待真实模型；已审 | 本轮静态已审，未调用该规则真实或替身模型。 | 诊断替代主诉的规范例外与原子事实完整覆盖尚须真实模型和临床签认；当前全链保存回读未验 |
| LX0609-01-02-02 | 首程鉴别诊断与第一诊断关联 | 待真实模型；已审 | 本轮静态已审，未真实或替身送模。 | 真实跨系统合理关联、明显无关、多文书业务键冲突样本及临床预期不足 |
| LX0916-001 | 再次入院诊疗总结 | 确认缺陷；已审 | A空正文+B有效正文，complete→compliant、incomplete→non_compliant均错误锚定A。 | AH-001来源错绑定须修复并重做当前全链验收；真实当前语义质量及独立临床金标准缺失；AH-002 prior_admission_count=1门控争议 |
| LX0916-002 | 民事行为能力与陈述者 | 确认缺陷；已审 | A空正文+B有效正文，complete→compliant、incomplete→non_compliant均错误锚定A。 17岁能力不详→data_quality_gap，符合预期。 | AH-001来源错绑定须修复并重做当前全链验收；真实当前语义质量及独立临床金标准缺失 |
| LX0916-003 | 现病史完整清楚 | 确认缺陷；已审 | A空正文+B有效正文，complete→compliant、incomplete→non_compliant均错误锚定A。 | AH-001来源错绑定须修复并重做当前全链验收；真实当前语义质量及独立临床金标准缺失 |
| LX0916-004 | 鉴别诊断重要阳阴性症状 | 确认缺陷；已审 | A空正文+B有效正文，complete→compliant、incomplete→non_compliant均错误锚定A。 | AH-001来源错绑定须修复并重做当前全链验收；真实当前语义质量及独立临床金标准缺失 |
| LX0916-005 | 院前检查治疗经过效果 | 确认缺陷；已审 | A空正文+B有效正文：005/006返回data_quality_gap但锚点与target_document_available仍指向空A。 | AH-001来源错绑定须修复并重做当前全链验收；真实当前语义质量及独立临床金标准缺失；原文明确不详与笼统治疗详细程度仍需临床签认 |
| LX0916-006 | 既往史完整性 | 确认缺陷；已审 | A空正文+B有效正文：005/006返回data_quality_gap但锚点与target_document_available仍指向空A。 | AH-001来源错绑定须修复并重做当前全链验收；真实当前语义质量及独立临床金标准缺失 |
| LX0916-007 | 个人婚育月经家族史 | 确认缺陷；已审 | A空正文+B有效正文，complete→compliant、incomplete→non_compliant均错误锚定A。 | AH-001来源错绑定须修复并重做当前全链验收；真实当前语义质量及独立临床金标准缺失 |

## 已确认缺陷与争议

**AH-001 / P1**：`input_context.py:108–110`固定取来源列表首项；`semantic_extractor.py:487–547`则跳过空正文/无法定位的记录，选中下一份。经source gate、merge后，`admission_rules.py:242–286`仅消费state，没有核对本次目标document_id。合成SYN-A空、SYN-B有效，两种预先冻结预期（complete/incomplete）均复现五条规则错误锚定SYN-A。005/006再次ground_items拒绝B事实，保留资料不足，但仍输出A可用/锚点。建议修复实际目标文书选取一致性或事实document_id校验；本轮未改代码。

**AH-002 / 争议**：`prior_admission_count=1`直接不适用，而该字段字面可能表示曾住院1次。现有测试采用累计次数口径；生产源合同未定位到明确说明，所以不把此项认作确定缺陷，须先确认字段含不含本次。

## 源字段→执行→事实→客户文案

0609基础时限读取登记入院时间、受控备用锚、文书权威时间/正文和评价终点；native_basic_timeliness形成决策与精确秒数，经decision_binding归约、basic_timeliness_customer_projection白名单、Finalizer校验、Renderer文案。合成24/8/48/72h整点、+1秒共8目标均保持；007的72h/+1秒共2目标保持。008/009两个完整无触发医嘱目标为not_applicable，不能据此认可阳性分支。018使用确定长度+LLM原子关系，077抽关联状态后受控映射，均待真实模型。

0916读取入院记录最小context，受控selector选取完整同源材料；001/002/003/004/007是state合同，005/006是逐项引用合同。source gate负责selected source/document_id，执行器形成状态/原因/判定事实/证据/建议，contracts仅序列化。005明确不详保持recorded_information_unknown，006缺预防接种保持non_compliant；17岁能力不详保持资料不足。source错绑定缺陷来自context与selector选文书标准不一致。

## 历史证据适用性

已读脱敏统一进度与基础时限/阶段A报告，未读-private患者原文。2026-09-24报告绑定a832ebdb/31109f8b且明言非临床零回退：a832是当前祖先，但native_basic_timeliness与rules_008_009均有差分。0916专项A树09bf7a826不是当前HEAD祖先，admission_rules/admission_content_items/input_context/semantic_extractor四文件均有差分。003旧3例均正例、005旧3/3、006旧7/7及007旧3/3不能复用为当前全规则验收。当前每条源文件SHA-256与相关脱敏文档SHA见JSON；没有把只有HEAD文字的旧报告视为完整构建冻结。

## 复现与边界

预期文件先于生产函数执行生成：`.tmp/engine-audit-20261008/admission-history/expectations.json`、`source-expectations.json`、`native-expectations.json`；结果分别为results/source-results/native-results。native使用注入合成row_reader，保留执行器→归约→Finalizer，只隔离未用数据库I/O模块与静态目录。禁网络/凭据读取；初次asyncio本机自管道被禁socket护栏拒绝，随后无挂起协程同步推进，未开放网络。没有运行共享pytest conftest，也没有真实模型、PG查询、病例原文、正式保存或页面回读。

本轮真实模型0、PG查询0、.env读取0、真实病例读取0、生产修改0、提交0。已审不等于通过：当前结论为16条有明确审查结果、7条确认共享来源缺陷、6条已审未确认新缺陷、3条待真实模型；所有单规则完整临床验收仍缺独立样本/签认。
