# N12 测试合同适配独立静态复审

接受固定提交 `62cbbc240e6a072795220ef3cd91dd49b230eb19` 相对父提交 `08aed59db3ed9bf08316fc792a757a3ee65d992b` 的限定测试合同适配，未发现确认阻断。接受仅覆盖旧 037（LX0609-04-04-02）测试改用显式 1-call 合同与人工冻结抽取 facts；不代表重审或关闭 N12 核心生产、43/SQLite 独审或真实模型语义验收。

固定树 `F:/MedQC-worktrees/qc-fix-ledger-20261008` clean；提交父关系核实。九路径为七个旧测试、一个新stdlib helper及作者文档。`backend/app` 零diff，无生产、Prompt、目录、CI、公共投影或根报告修改。本组没有运行测试、作者 preservation/audit脚本或其宽松 runner，也未访问.env、PG、模型或网络。作者保护JSON不作为独立证据。

## Standards

硬合同违规0，未发现需要阻断的风格判断。两次静态读取（WIP与固定提交）七旧文件blob一致，helper已纳入最终提交，blob `cea2124efda5ec3a3d6f855534581b1e45e182aa`。按仓库AGENTS限定只读审查，不执行本次明确禁止的测试及提交动作。

| 旧测试路径（均在 backend/tests/unit） | 保留证据与允许变化 |
|---|---|
| test_luxian_0609_native_surgery_document_execution.py:1064 | 原否定正文、NC、ASA/气道/风险三项missing保留；仅037人工客户端、1call和10/5/15 Token计量适配 |
| test_luxian_0609_round2_document_boundaries.py:33 | 原四项输入、C/NC及“已核对”不应出现的负向finding断言保留；跨事件三参数仍NoModel/0call，gap/association_failed不变；_final只显式注入037人工facts |
| test_luxian_0609_rule_contracts.py:242/295 | 仅037移出program_only；新增精确v3/optional/max1/Prompt断言；其余授权集合保留 |
| test_luxian_0609_surgery_document_freeze.py:483 | 参数化输入/答案、status/reason/display facts/findings/evidence/fact refs逐项断言保留；仅037调用计量调整 |
| test_luxian_0609_surgery_document_precise_fact_refs.py:134/157 | 七规则参数和expected materials、精确refs集合断言保留；只有037用人工client/1call，其他仍0call |
| test_n04_n06_anesthesia_pathology_boundaries.py:79 | 13项037原替换输入及parametrize保留，missing/present正负断言与有效阴性C保留；病理保护不变 |
| test_n08_anesthesia_label_ownership.py:32 | 八项原输入/参数保留；正常无missing及空标签精确missing集合断言保留 |

## Spec

已实施需求无确认缺失、错误或越界。独立静态AST对照七文件119个test函数：parametrize装饰器全部保留；原医学status/reason/missing/refs与负向assert未删改。唯一非资源类断言适配为明确授权的037权限集合，新权限定为显式1call/对应Prompt。两个结果赋值变更只替换037受控事实client，不按新生产结果改医学答案。

新 `luxian_0609_anesthesia_test_facts.py:15` 的CASE_FACTS逐具名案例手工冻结片段或None，含25边界案例及三个正式链fixture。N04/N08按精确案例查表，无泛化关键词分类、病例过滤、生产答案读取或从执行输出生成expected。`:69` generate只从当前合成输入找冻结片段及对应文书坐标；present/absent由冻结表决定，不从正文自动推答案。仅导入stdlib json，返回抽取事实schema，不直接返回C/NC、reason或missing判定。`:71` 约束一次调用、禁止length retry、预算≤4096及PRE/POST两文书。“呼吸循环稳定”支撑片段只在既有freeze/precise案例具名冻结，不扩展成通用临床词表。

原25项失败此前先停在_final的0call断言，该断言在Binding/Finalizer及调用者医学断言之前。因此旧红不能当作医学已绿。本次静态可确认后续医学断言仍在且适配后控制流可达，不能单靠静态确认其真实执行通过。根/作者报告的348=346pass+2父版本同fail、43及旧28绿、277=275pass+2baseline为外部运行证据；本组未复跑、不把这些计作独立医学通过数。根协调将另做严格guard复跑。

若后续将手工表改成关键词自动判定、从生产输出生成facts、删除病例/负向assert、或放宽医学答案，需重新阻断审查。仍缺本组动态运行验证与真实模型语义证据，工程接受不补造临床验收。

轴结论：Standards 0确认违规、Spec 0确认缺陷；接受范围固定于该test-only提交。
