# 0609成果叠加：e5f569

固定文档版本 `e5f5696f559b4571b0d2a7d339d0d65485f8344b`；保留原86矩阵及1958叠加。root后续ce1为文档提交，TC02 219b+196d候选未集成。本轮只读成果账及归档证据，0测试/模型/PG/生产编辑。

## 当前可证规则去重数

| 统计口径 | 数量 | 边界 |
|---|---:|---|
| 有针对性源码/合同或实质行为/反例证据 | 80 | 原70读审定位+10实质行为；不是80医学通过 |
| 只有范围/目录合同证据 | 6 | 已T5范围核查，不称医学功能审查 |
| 完全从未审 | unknown/null | 不能证明闭世界数量，不报0 |
| 旧有限修复子项涉及规则 | 14 | 原completed_problem_ledger |
| 本轮已集成生产工程/权限/入口子项涉及规则 | 13 | 不含新测试适配和未集成候选 |
| 两者交集 | 3 | 05-02-01、06-04-01、06-04-02 |
| 已有修复子项覆盖并集 | **24** | 不等于整条工程或临床闭环 |
| 可证明整条工程/临床闭环 | unknown/null | 不把有限tests变整条通过 |

原数量出处：固定catalog-coverage.json的completed_problem_ledger及原remaining-audit-evidence的70/10/6；本轮集成13来自1958已核Git祖先的明确rule_id映射。e5新增fad/5f仅测试合同适配，4source包补7条当前来源绑定，未新增生产修复条数。

## 实际下一步队列

| 类别 | 数量与单位 | 具体索引 |
|---|---|---|
| 已知代码行为/冻结能力未达 | 9 root问题项 | course-timing:CT-01, discharge-death:DD-F02, treatment-consultation:TC-01, treatment-consultation:TC-02, treatment-consultation:TC-03, tumor-pathology:TP-D02, tumor-pathology:TP-D03, tumor-pathology:TP-D05, N13 |
| 待业务合同/来源口径 | 6 root问题项 | PREOP-MEDICAL, discharge-death:DD-F05, imaging-laboratory:IML-01, imaging-laboratory:IML-D01, imaging-laboratory:IML-D02, rescue-remaining:RR-D01 |
| 当前输入/Prompt/自然资料复验 | 5 root问题包 | CT-INPUT-CHANGE, PATH-INPUT-CHANGE, PROMPT-074, SURGERY-FREEZE, TR-048-REAL |
| 旧反例来源绑定/准备 | 3 root问题包 | N10, TR-044-MULTI, SURGERY-029030 |
| CLI可信身份来源功能前置 | 1 root问题项 | PRIV003，继续failclosed，不是泄漏 |
| 有限工程问题子项已关 | 16 root问题项 | 原明确关闭子项保持 |

**以上主队列互斥相加为40。** 第二维真实模型/样本明确followup为6包（5复验+N12），与上述类别交叉；全链缺口为1个共享T6/T7门禁包，不能加作第41个缺陷。自然适用语义、正式发布/保存/新实例回读/真实HTTP/浏览器/历史结果/客户部署未被局部合成替代。program-only和暂停/撤默认项不制造模型调用。

优先事项：TC02候选196d实际privacy wrapper输入view/坐标/临床保护独审；TP-D02两原语义失败及115旧医学保护未证；随后N10/TR044/SURGERY029先取现存反例manifest再最小修复。原TR044三项精确node未知，不能猜三条。业务合同和真实层按职责补证，不重审86。

## 后续提交与补证已完成什么

- **fad64946e**：029 MR fixture/031032家族测试漂移适配，root354/354；旧348两个同父失败接续关闭，但多医嘱029/030医学归属仍开。
- **5f34698a2**：培养旧015身份literal测试适配，root原45/45。原44/1日志保留，医学全文和输入不变；不称45临床例通过。
- **7条指定当前合成来源绑定**：05-01-02/05、04-02-06、08-01-01、08-02-02、06-03-03/04；旧真实运行manifest和正式链缺口没有倒填。
- **IML01 mapping**已只读细分：06-01-03原joint CT/MRI gap/C合同未决；06-01-01同ledger但原case无orders/course不能继承C；06-03-02culture不消费exam-only case，仅保留新字段真实输入与正式链复验，不再臆造三条同一剩余合同。
- **N12**保持工程子项可继承、真实语义/全扫描待验；**TP-D04**保持跨药支持子项可继承，非整条医学通过。
- **TC02/TP-D02**仍未集成：作者202/284或65绿都不增加修复规则；TC02-PV01为候选输入完整性阻断，不推断真实隐私泄漏。

| 来源绑定包 | 规则 | 既有执行层 | 仍缺 |
|---|---|---|---|
| antibiotic-current | LX0609-05-01-02, LX0609-05-01-05 | 指定原13合成观察完成；8/13符合原expected，13/13复现旧observed；168真实app源码/727来源hash固定。 | TP-L01两个Noneclient failclosed不是真实语义误判；TP-Q03医院目录、TP-Q05无痰理由、TP-Q04会诊来源口径保留；无真实材料/model/Worker/Store/API。 |
| death060-current | LX0609-04-02-06 | 4原执行/Binding/Finalizer+1矛盾事实拒绝+6公开格式保护共11符合；原输入/预期hash不变，3系统初始化替身披露。 | 历史6例仅无死亡触发，旧真实执行manifest仍缺；无真实死亡阳性gold、Store/HTTP/API/浏览器/临床签认。 |
| discharge-death-current | LX0609-08-01-01, LX0609-08-02-02 | DD001..007为7纯时间函数；DD028..031为4真实执行/Binding/Canonical；11/11符合，142来源绑定；4支撑失败保留。 | 包家族常量初始化声明替身；无完整package初始化、endpoint/save/store/HTTP；旧历史执行manifest未反推。 |
| culture-current | LX0609-06-03-03, LX0609-06-03-04 | 原45节点44/1旧015身份literal失败；保留原记录。固定f37仅2处身份替换独审、5f34698a2集成后root原45/45，10直接合成+33共享projection+1parser+1全文prompt，不是45医学例。 | 旧真实/model manifest及6例语义抽取当前未验；不能证明实际临床输入截断不存在。 |

抗菌药13观察中5原期望差异仍按旧TP-L01/Q03/Q05/Q04：两个Noneclient failclosed不算语义误判，三个Q为目录/理由/会诊来源口径，root40主键尚未规范对应，保留mapping unknown不擅增新问题。

## 86条互斥下一动作

| 下一动作 | 数量（非通过数） |
|---|---:|
| inherited_limited_remaining_T7 | 25 |
| open_issue_or_business_basis | 20 |
| affected_inputs_revalidation_open | 7 |
| current_synthetic_source_bound_remaining_real_layers | 7 |
| scope_registered_pending | 10 |
| scope_customer_excluded | 5 |
| engineering_closed_real_semantic_pending | 1 |
| integrated_subissue_remaining_evidence | 4 |
| ledger_subitem_repaired_consistency_input_and_contract_pending | 1 |
| scope_acceptance_only | 5 |
| scope_unregistered | 1 |
| 合计 | 86 |

21非默认医学执行项仍为未注册1、注册暂停10、客户来源排除5、acceptance撤默认5，不计医学通过。7已补绑定在原80实质证据内，未增加审查分母或新造通过数。逐rule全部旧成果、这轮集成子项、当前issue状态与新来源绑定出处均在JSON，CSV可筛选。

[JSON](F:/MedQC-worktrees/review-artifacts/coverage-progress-current/overlay-e5f569.json) · [CSV](F:/MedQC-worktrees/review-artifacts/coverage-progress-current/overlay-e5f569.csv)
