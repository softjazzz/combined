# 第二轮抗菌药审查缺陷最小修复

2026-10-07，开发基线 `57b863d2b328b2d93b004ffb6e49da55be76d804`。只局部修改 native_extended_document_execution.py 的抗菌辅助函数和05族入口；新增 test_luxian_0609_antimicrobial_audit_regressions.py。同文件转科/疑难讨论/065由其它代理负责，未覆盖其修改。不改公共Renderer、Finalizer、合同、目录、Prompt或源注册。

## 红绿对照

先执行新测试10项：**5失败、5通过**。失败即审查原反例：03/05/06明确取消未给药却缺项；02“理由未记录”却合规；05明确细菌性肺炎依据却理由缺失。完成修复并补冲突保护后，新测试**14通过**。

| 原合成输入                     | 修复前归约                              | 修复后归约                             |
| ------------------------------ | --------------------------------------- | -------------------------------------- |
| 03已取消且未给药               | non_compliant/threshold_exceeded        | not_applicable/trigger_absent_complete |
| 05拟经验用药、拒绝、未给药     | non_compliant/requirement_violated      | not_applicable/trigger_absent_complete |
| 06已取消且未给药               | non_compliant/required_document_missing | not_applicable/trigger_absent_complete |
| 02启用但理由未记录             | compliant/requirement_satisfied         | non_compliant/requirement_violated     |
| 05影像证实细菌性肺炎后经验用药 | non_compliant/requirement_violated      | compliant/requirement_satisfied        |
| 02明确培养感染依据             | compliant/requirement_satisfied         | 保持                                   |

## 最小职责边界

取消门控只用于03/05/06，精确匹配取消/已取消/作废/已作废/撤销/未执行状态，不把停止等于从未给药；另消费可归属同一医嘱或唯一同药事件的明确未实际给药/未实际使用文字。冲突的明确已给药不静默排除。同名多医嘱无关联ID时不猜测文书归属。负向判断保留被排除医嘱和实际消费的否定文书精确引用。06严格使用原合同上级病程/会诊，不消费daily来源。

02按分句剔除明确理由/依据未记录等缺失声明，不让词表中的“理由”本身作为正向事实；另一分句存在真实理由仍有效。05仅增加“证实/确诊细菌或感染”这一明确诊断依据形式，并保护未证实、尚不能证实等否定，不新增药品或疾病词典。充分性一般语义判定仍未全面解决。

## 验证

- 新回归14项通过，覆盖明确未实施、否定理由、明确诊断依据、否定诊断、无不良反应、已停用、取消与实际给药冲突、另一条实际医嘱。
- 新测试当时10项 + antimicrobial_action_extraction/result_mapping + 057_source_boundary：113通过。
- 原生执行器聚焦 `-k '054 or 055 or 057 or 058 or antimicrobial'`：127通过、287未选择。
- Ruff目标文件通过；git diff --check通过。
- 原审查正式typed读入→执行→绑定归约再回放：6条合成全部符合冻结预期；18条冻结真实来源规则的状态/原因及调用统计逐项未变。未重新读PG，旧快照不是当前数据库状态证明。
- 真实模型调用0，Token0。测试conftest按既有行为初始化本地demo SQLite，未写PG。

私有红/绿材料在 `.tmp/0910-full-audit/round2-antibiotic-private/`，基线 typed-results-private.json保留，修复后另存typed-results-after-fix-private.json及typed_replay_fix.py。不包含患者原文的此报告可交主审；私有材料不提交。

## 未解决与交付限制

状态文字精确过滤有同仓其它执行器实践，但六例真实来源没有取消状态，未验收医院具体取消编码。仅代码未知状态不被推断为取消；需上游真实码表覆盖。仅daily包含06取消/实际给药事实而其药嘱状态不明，现有06合同不读取daily，本次未扩大来源。

未解决03首次实际给药时间与计划时间合同问题；未做真实特殊级病例、02真实语义模型、停/换/联合全部实际动作的临床验收。任意同义理由或复杂否定并未声称全面覆盖。

本轮执行验证止于绑定/归约，没有新增完整Finalizer/Renderer/Aggregator及保存/API/UI验证；映射现有测试通过不能替代最终客户链验收。未全量测试、提交、推送、重启或操作PG。主协调需独立审关键diff及决定是否接受上线。

## 交叉复核补修：新增“证实”形式的否定误放行

主协调复核发现本轮新增短前缀lookbehind仍将“尚无证据证实细菌性肺炎”和“并非证实细菌性肺炎”作为05的肯定依据。新增两条真实执行器回归先红：2失败、14未选择；并未将这次新增回归掩盖为旧有问题。

补修把新增依据识别限制为分句开头的明确“证实/确诊细菌或感染”形式，允许本次冻结正例的影像/胸部影像主语及“已”，不再任意位置搜索肯定动词；带否定、推测、计划修饰的分句不能走这条新增快捷路径。原有已认可理由合同未扩展，来源及其它代理分支未动。该形式有意保持窄范围，不声称一般临床自然语言理解。

补修后独立回归16项全部通过，正向影像依据、未证实/尚不能证实及原取消与实际给药冲突控制保留；Ruff通过。未真实模型、PG写入、提交或重启。
