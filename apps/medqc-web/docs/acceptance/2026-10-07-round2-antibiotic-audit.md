# 第二轮抗菌药规则独立审查

日期：2026-10-07。基线 HEAD：`c3a87a4f820259bca37a01764522ea1f3f485a3c`。审查范围为 LX0609-05-01-02/03/05/06；01/04 的 pending 目录不计实际验证。达到两类确认工程缺陷后收尾，未修生产代码、Prompt、目录或发布范围，未写 PG、调用真实模型、提交、推送或重启。

## 依据与方法

已读仓库 AGENTS.md、滚动接续信息、总表 `luxian_0609_rule_master_v1.json` 的 qc_point/policy_summary、0602业务标准基线及扩展合同。总表四条均 active。CodeGraph 首次定位返回 `unable to open database file`，随后按降级流程读取源码。目标执行器及动作抽取文件相对 HEAD 的 git diff 为空；工作区其它并发改动未触碰。

只使用既有0910坐标清单的 C01–C06 别名及坐标，重新读取抗菌药医嘱、日常/上级病程、会诊、住院登记。PG事务执行 SET TRANSACTION READ ONLY，实测 SHOW transaction_read_only = on。凭据仅从 backend/.env 读取；未读历史质控结果或旧人工预期。

先查看源材料，再写 `expectations-freeze-private.json`，之后才运行执行器。冻结SHA256：`64a949f2d0a1b4f42898206cb7cad0112a4e5193267583dde3a984a228989466`。冻结前已看实现，故属于来源先行工程审查，不声称完全盲审。真实来源和坐标仅在 `.tmp/0910-full-audit/round2-antibiotic-private/`，不提交。

正式内存入口：`build_luxian_0609_evidence_read_session → execute_luxian_0609_native_extended_document_rules(decision_rule_ids=...) → bind_and_reduce_luxian_0609_rule_decisions`。row_reader 返回本轮来源快照或明示合成材料；未替换判定函数。评价终点明确冻结为 2026-10-07（frozen_task_date），不是生产任务旧快照。本轮止于绑定和归约，未走 Finalizer/Renderer/Aggregator、保存/API/浏览器及真实生产全任务装配；下述状态均是归约结果，不能声称可交付客户最终状态。

## 按规则实际执行覆盖

| rule_id         | 真实来源离线执行 |              真实适用覆盖 | 合成执行 | 边界                                          |
| --------------- | ---------------: | ------------------------: | -------: | --------------------------------------------- |
| LX0609-05-01-02 |                0 |                         0 |        2 | 实际启用且理由否定/明确正例；真实语义抽取未跑 |
| LX0609-05-01-03 |                6 | 4用药候选，实际时间未验证 |        1 | 明确取消；实际执行时间及窗口临床结论未验收    |
| LX0609-05-01-05 |                6 |                  1（C03） |        2 | 拟用未给药、明确同义感染依据                  |
| LX0609-05-01-06 |                6 |                         0 |        1 | 明确取消；六例全为非特殊级负向控制            |

共18次真实来源规则执行、6次合成执行，每次重复一遍。重复不增加覆盖数。02发现是**否定理由被当存在**，05发现是**明确同义依据被当缺失**，未将二者混称同一函数缺陷。

## 真实来源覆盖与输出

六例中 C01–C04 有抗菌药医嘱（含重复技术行/皮试），C05/C06 没有；真实候选用药例为4，负向控制2。未找到特殊级药，06真实适用数为0。医嘱表无实际执行时间字段，不能凭“新开”或计划开始证明首次实际给药时间。

| 别名    | 03效果评价                         | 05经验用药                        | 06特殊级       |
| ------- | ---------------------------------- | --------------------------------- | -------------- |
| C01     | data_gap / association_failed      | not_applicable                    | not_applicable |
| C02     | non_compliant / threshold_exceeded | not_applicable                    | not_applicable |
| C03     | non_compliant / threshold_exceeded | compliant / requirement_satisfied | not_applicable |
| C04     | data_gap / association_failed      | not_applicable                    | not_applicable |
| C05/C06 | not_applicable                     | not_applicable                    | not_applicable |

C03源病程明确经验用药并给出感染可能，05与冻结预期一致；不能将其它未触发例统计为真实适用合规。03的C02/C03输出只是计划时间代理下的程序结果，不称临床误判已被证明或实际48–72小时窗口已验收。02需受控语义动作抽取，本轮不调用真实模型，因此没有真实02结果验收；C02/C03/C04源材料可作下一轮候选。

## A-01：未执行事件被判确定缺项（工程反例）

主反例：合成医嘱状态“已取消”，正文“拟使用美罗培南经验性抗感染治疗，患者拒绝，未实际给药。”冻结预期05不适用；实际为 `non_compliant / requirement_violated`，0模型调用。实现 `_is_explicit_empiric_antimicrobial_use`（native_extended_document_execution.py:1187）只匹配经验性术语、有限否定词，未排除拟使用/未实际给药；`_antimicrobial_orders`（982）只按药名识别。

同次冻结边界检查还显示：取消美罗培南医嘱且正文明确“本次住院未实际给药”，03返回 `non_compliant / threshold_exceeded`，06返回 `non_compliant / required_document_missing`。03治疗过滤（986）只排皮试，06（2606）直接从医嘱建特殊级事件，均未证明实施。该结论是当前正式入口接受上述合成输入后的工程行为；没有证明真实同步库必然采用“已取消”枚举，也未发现六例发生这一反例。

最小修复方向：在事件所有者核实取消/未执行和实际用药事实，不能用药名或医嘱存在替代实施。计划和执行相冲突时应保留明确来源缺口；禁止在Renderer/API改结论。保护集需含仅计划、明确取消、一次取消另一次给药、既往药史及“用药后无不良反应”。

## A-02：理由字面词表无法判断理由存在与充分性（工程反例）

| 合成正文                                               | 冻结预期         | 正式输出                                 |
| ------------------------------------------------------ | ---------------- | ---------------------------------------- |
| 今日启用美罗培南，用药理由未记录。                     | 02 non_compliant | **compliant / requirement_satisfied**    |
| 今日启用美罗培南，因为细菌培养证实感染。               | 02 compliant     | compliant / requirement_satisfied        |
| 胸部影像证实细菌性肺炎，予以美罗培南经验性抗感染治疗。 | 05 compliant     | **non_compliant / requirement_violated** |

02 `_054_reason_documented`（1135）见“理由”即真，不区分“未记录”；05 `_empiric_reason_documented`（1253）依赖固定短语，不能识别上表已完整写明的感染依据。客户02要求“无理由或理由不充分”，05要求经验用药说明理由，均不等价于固定词出现。

为02显式配置了只返回“今日启用美罗培南”动作引用的合成替身；实际这两条动作由确定性路径识别，执行器报告调用数0，未调用替身或真实模型。未使用替身生成理由或状态。由正负对照证明不是所有02输入均失败。最小修复应在单规则事实抽取/校验层分离明确理由、明确缺失、语义未知；不要扩大理由关键词表冒充充分性判定。补否定、同义依据、不同药物不同动作的理由归属保护集。

## 时间口径与未覆盖

0602业务基线第145行写首次实际执行起算；2026-09-03 pending-rule-policy 同时记有计划开始或实际启用口径，9月14日验收仍标注实际起点未闭环。因此本轮不擅自改口径，也不要求客户重新定义已有合同；主审应核实最新客户确认版本，03源缺实际起点不能包装为完成临床验收。当前函数 `_antimicrobial_start_datetime`（1019）确实读取 planned_start_datetime 或 prescribed_datetime。

未覆盖：真实02模型输出与费用/稳定性；实际给药起点；48/72小时边界；停用、更换、联合、超说明书各自理由；跨多次同药事件的关联；无样可采具体原因是否充分；真实特殊级授权专家、紧急越级24小时补办；保存/API/页面、生产任务装配。六例来源读取不等于四条真实适用规则验收通过。

## 复现与留痕

私有目录含 `source_read.py`、`sources-private.json`、`columns.json`、`freeze.py`、`expectations-freeze-private.json`、`typed_replay.py`、`typed-results-private.json`。运行 `python .tmp/0910-full-audit/round2-antibiotic-private/typed_replay.py`，两次18条真实来源离线输出及6条合成输出完全一致；所有执行器报告 total_tokens=0、llm_call_count=0。脚本退出0表示运行完成，不表示冻结预期通过；上表5条合成反例失败、1条正向控制符合。

目标模块SHA256：

- native_extended_document_execution.py：`E4E438EF96ECCA82AA966814CF5184245565578889995077E233EF4D49F96092`
- extended_document/antimicrobial_action_extraction.py：`E75D4E23EB616100D45AF979C2DE9BF940F03374772FB12A20536772DA4C9B9F`

本文件不含患者姓名、住院号、坐标或真实病历原文；正文示例均为本轮合成材料。仅新增审查产物，不宣称临床验收通过或批准上线。
