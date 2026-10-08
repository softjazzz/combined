# 检查检验、病理与危急值：第一轮只读审计

2026-10-08，代码固定于 `7b894dc84491b7b72eb096de58fe61f772cc0080`，工作树 `F:/MedQC-worktrees/qc-integration-20261008`。根及应用 AGENTS 已读，无 `.codegraph/`。仅读当前源码、正式规则目录和脱敏验收文档；没有访问 `.env`、PG、真实模型、患者原文或旧私有真实产物。只写本报告、同名 JSON 与独占临时探针。未修改生产、共享测试或 TODO，未提交。

**当前结论：2组确认P1影响5条实际规则；另有2项争议。13条active规则均仍待当前真实病例/完整交付链验收，培养一致性1条未定义。不能称全引擎验收通过。**

## 逐规则核对

业务基线为 `apps/medqc-web/docs/0602/泸县0609质控点-业务标准基线-v1.md`；001–049允许状态只查正式CSV，052/053不跨范围套用。四段式当前身份、发布范围来自当前 rule master。良性炎症、退变、陈旧灶已明确属于012阳性标准，不能凭外部旧意见称该判据缺失。

| 实际ID | 当前判据、事件/医嘱/报告与时间来源 | 本轮结论 |
|---|---|---|
| LX0609-06-01-01 | handbook医嘱order_id→exam_id；逐合并医嘱核对病程；正式报告可证明执行；无24h窗口；独立一次语义抽取 | IML-01确认缺陷；待真实验证 |
| LX0609-06-01-02 | 显式order_id→exam_id关联；缺键/歧义资料不足；以检查时间和病程记录时间核对检查前原因，模型仅获前48h候选 | 正式路径含R-02保护；48h依据争议；待真实验证 |
| LX0609-06-01-03 | 按exam_id去重；正式发布且有效正文；计划/新开不证明执行；本地无报告仅资料不足；零模型 | acceptance_only；IML-01确认缺陷 |
| LX0609-06-01-04 | 按exam_id；报告后24h记录同次结果；记录时间与提交时间分开；纯CT引导标签不适用 | 待真实验证；旧C09/C10响应失效 |
| LX0609-06-01-05 | 任一明确异常为阳性；报告后24h分析；与04共享一次事实抽取、Python校验时间与关联 | 待真实验证；当前不确定状态按本规则允许集合收口 |
| LX0609-06-02-01 | 按同命名空间pathology_exam_id/pathology_id归并；申请不证明执行；本地无报告不直接判临床遗漏；零模型 | acceptance_only；聚焦合同通过，待真实验证 |
| LX0609-06-02-02 | 最终诊断与有效报告时间门禁；逐报告关联取材文书的业务键或唯一标本+时间；双条件判据已有确认记录 | 原报告缺口修复仍可作为历史证据；完整双条件真实样本待验 |
| LX0609-06-02-03 | 最终诊断与报告时间同份来源；逐报告与病程/手术文书关联；无唯一关联资料不足 | 完整报告多事件真实样本待验 |
| LX0609-06-03-01 | 主记录缺医嘱关联键；pending_definition，总表保留，未进入执行目录 | 未定义；不能伪称已上线或通过 |
| LX0609-06-03-02 | 按test_id归并多行；正式发布+有效正文；零模型 | acceptance_only；IML-01确认缺陷 |
| LX0609-06-03-03 | 培养/药敏事件test_id；报告后24h记录；共享抽取、病程时间和成熟窗口由Python控制 | 待真实验证 |
| LX0609-06-03-04 | 可靠结构化菌名或语义阳性；24h分析；药敏待出非豁免；同次关联与03共享事实 | 旧单病例菌名修复证据有限；待真实验证 |
| LX0609-06-04-01 | PL/PH；report_id/test_id与处置关联；6h窗口与冻结评价终点；精确/日期成熟口径 | IML-02确认缺陷；待真实验证 |
| LX0609-06-04-02 | PL/PH；对应处置存在性，未附加6h；仍用报告时间核对处置先后 | IML-02确认缺陷；待真实验证 |

## 确认缺陷及结论建议证据

**IML-01 / P1：手册事件台账未校验同键主从身份冲突。** `apps/medqc-web/backend/app/services/luxian_0609/handbook_exam_lab.py:232` 只要任一合并行名称为目标，就保留整个事件并接收另一行报告；不检查DR、超声或普通检验是否明确否定该目标身份。CT主+DR报告、DR主+CT报告、CT主+无身份但超声科报告均从预期资料不足变合规。培养主+血常规身份报告同样合规。全部报告反例补跑正式typed原生入口，仍合规、0模型；CT主+DR报告同时跑01-01与01-03，固定合法语义响应后两条均合规，1次固定客户端调用。01-01本应在身份不明时停止语义调用。近期R-02修复只改 `exam_lab_fact_extraction.py:648`，两套台账事实不一致。

影响：01-03、03-02会将非目标报告当目标报告齐全；01-01会将此报告当执行证明，随后接受医嘱/病程一致性事实。对应客户合规结论已缺少可靠事件依据。尚未估计真实病例频率，不将合成病例冒充真实缺陷。

**IML-02 / P1：危急值报告时间替代与冲突未校验。** `native_extended_document_execution.py:578` 使用 `report_time or report_datetime or record_time`：缺报告时间时取记录时间，两个报告字段相差一天时任取第一个。冻结反例中仅记录时间08:00、处置09:00，或者报告字段分别为第1日08:00/第2日08:00、处置第1日09:00；两条规则都输出合规。基线052要求报告时间起算，两字段冲突也不能可靠确认处置先后。

两反例各经正式typed原生执行→Reducer→Aggregator/Renderer，均交付合规，并显示建议“继续保持。”；实际模型0。正常同键明确报告+1h处置正例保持合规。此处是执行器事实错误，后续合法白名单校验无法修正；未运行真实保存/API/浏览器。

## 冻结预期、离线测试与争议

先冻结 `expected.json`（SHA256 `907902ea92c3c7bdc9e1724a2d322b80bec35f7d686aaa70a3af5768a5bc10c3`）再执行9例；补充先冻结含完整输入的 `expected-extra.json`（`4540b293986702c6501cb929dc11ce052863157259fd8d6748d388860a22ff8a`）再执行3例。产物位于 `.tmp/engine-audit-20261008/imaging-laboratory/`，所有字段都是合成材料。12例共7例偏离预期：6例支持上述确认缺陷，1例为下列状态争议；5个保护正例/负例符合预期。JSON保留逐例实际、原因码、原生结果及模型计数。

16组现有聚焦单测为 **619 passed，1 warning，11.00s**：手册台账、CT一致性、影像身份/引导、原生检查检验、病程时间、模型失败/事件顺序、病理缺口/完整性/事件关联、危急值时间/来源缺口/公开合同。命令为根目录 `python .tmp/engine-audit-20261008/imaging-laboratory/run_tests.py`；用 `--confcutdir=tests/unit` 跳过应用启动配置，禁缓存；dotenv替换、审计钩子阻止.env及网络，asyncio仅允许本地socketpair控制通道。不修改旧测试断言。测试通过不覆盖新反例，也不代表临床验收。

- **IML-D01 / 争议**：主检查记录明确取消、同键报告已正式出具，台账仍合规。需确认取消字段是最终执行事实还是历史残留；本轮不将它计入确认P1。
- **IML-D02 / 争议**：01-02在 `exam_lab_fact_extraction.py:193/994/1397` 与 `native_exam_lab_execution.py:1481` 硬限检查前48h。业务基线010只要求检查前原因，本轮未找到客户批准48h有效期的文档。旧单测明确保护48h，所以实现行为清楚，业务来源需核对。不能因旧测试绿就称判据已确定，也未擅改阈值。

## 当前改动对旧证据的影响

1. 10月7日第六轮真实模型报告固定 `1e9af161f`，仅04/05四次HTTP，26个期望结果一致但另4个DR错误事件；未验01-01和完整客户文案链。到当前版 `exam_lab_fact_extraction.py` 为47新增/1删除，身份优先、引导恢复、同键身份冲突改变事件目录/输入。C09/C10移除DR后输入已变，旧响应不能作为当前模型验收；C12/C04只有脱敏复验文档记录的逐字输入一致旧响应回放，也不能称新模型稳定性通过。
2. `2026-10-07-0910-r01-r02-h03b-recheck.md`明确01-01/03不经修改投影且未验证，本轮IML-01填补该合成边界。30例影像投影一致不证明另一套手册台账正确。
3. 9月12日培养015四个模型回答及150项冻结回放仅证明当时菌名识别与该病例结果，不覆盖新增03-02报告身份完整性，也不证明当前全族真实泛化。
4. 9月13日病理019两次30例主要覆盖最终诊断缺失、24例不适用，不能证明最终结果完整时逐事件取材/病程双条件正确。当前 `_pathology_documentation_links`有同键/唯一标本/时间门禁，聚焦关联单测通过，仍待完整真实样本验证。
5. 9月24日危急值公开合同报告是固定合成发布/读取证据，未覆盖报告时间替代/别名冲突；本轮IML-02证明公开合同合法仍可承载错误事实和“继续保持”建议。不能用该历史记录称当前医学判定正确。

## 下一轮验收边界

先由协调方独立核对IML-01/02源码和冻结反例，再在各自权威执行器内修复、冻结保护范围。真实验证需涵盖CT/MRI主从身份、重复/合并医嘱、报告时间与病程记录/提交冲突、培养多行及阳性分析、病理完整报告多事件/取材+结果、危急值时间缺失/冲突与6h边界。每条实际规则同时核对状态、原因、客户结论/建议、对应事件证据、调用/Token，再通过保存/API/浏览器回读。旧真实报告、离线固定响应和源码存在均不能替代这些步骤；本代理未开展这些当前真实步骤。

## T1 独立修复交接（只整理既有证据）

本节不新增审查、探针或测试；IML-01/02仍开放。旧 `64dd69e9a` R-02影像投影修复与旧 `4d5322c4a` 危急值合同已关项分别保留，不能冒充本次两个新缺陷关闭。011/012、019/013已经有历史审查和验收，来源或模型输入改变时归为复验，不能标成从未审。

**生产文件无重叠，可分开实施。** IML-01由 `apps/medqc-web/backend/app/services/luxian_0609/handbook_exam_lab.py` 拥有；IML-02由 `apps/medqc-web/backend/app/services/luxian_0609/native_extended_document_execution.py` 的 `_critical_value_item_from_row` 拥有。IML-02若要表达缺失/冲突状态，可评估同族 `extended_document_critical_value.py` 输入合同；不要为本缺陷先改共享时间读取器、Renderer或Finalizer。IML-01的入口 `native_exam_lab_execution.py` 与消费者 `ct_order_course_consistency.py` 作为调用链及断言对象，现有证据未证明必须修改它们。

| 项 | IML-01 | IML-02 |
|---|---|---|
| 冻结预期 | `.tmp/engine-audit-20261008/imaging-laboratory/expected.json` | 同目录 `expected-extra.json` |
| 既有探针/实际结果 | `probe.py` / `results.json` | `probe-extra.py` / `results-extra.json` |
| 确认反例 | `ct-master-dr-report`、`dr-master-ct-report`、`ct-master-ultrasound-dept`、`culture-master-routine-report` | `critical-record-time-fallback`、`critical-report-alias-conflict` |
| 已有正常/保护对照 | `normal-ct-report`、`normal-culture-report`、`pending-report-with-time`、`culture-pending-report` | `critical-normal-report` |
| 可继承测试（均在 `apps/medqc-web/backend/tests/unit/`） | `test_luxian_0609_handbook_exam_lab.py`、`test_luxian_0609_ct_order_course_consistency.py`、`test_luxian_0609_imaging_identity_boundary.py`、`test_luxian_0609_native_exam_lab_execution.py` | `test_luxian_0609_critical_value_source_gaps.py`、`test_luxian_0609_critical_value_disposition_time.py`、`test_luxian_0609_native_extended_document_execution.py`、`test_luxian_0609_critical_value_public_boundary.py`、`test_luxian_0609_critical_value_result_mapping.py` |

IML-01关闭标准：4个确认身份冲突反例在正式typed入口均为资料不足，保留核查引用；01-01在身份冲突时固定客户端调用0；01-03与03-02仍0模型。正常目标报告、培养多行、未命名合法明细、显式合并医嘱、新开但正式报告证明执行、同名重复检查与待审核/初步报告保护不得回退；不把身份冲突改成确定不适用。独立复审需固定修复SHA、原生状态/原因/事实/引用/调用量及对照结果。

IML-02关闭标准：缺报告时间即使有record_time，两规则仍 `data_gap/authoritative_time_missing`；两个有效非等价报告别名均 `data_gap/authoritative_time_conflict`，等价跨时区别名不能误报冲突；明确报告+同键1h处置正例保持合规。typed原生→Reducer→Aggregator/Renderer应交付缺口和对应建议，两个反例不再显示“继续保持”；0模型。保护现有PL/PH、多事件关联、坏处置时间、052的6h成熟/未成熟、053无附加6h及已发布原值读回合同。修复SHA和独立复审索引应与旧危急值合同修复单列。

旧CT真实证据：C09/C10在移除DR后模型输入已经变化，当前04/05需要新验证；C12/C04只保留逐字输入相同的历史响应离线回放证据，不称当前新模型稳定通过；第六轮未纳入01-01/03。病理019/013已有历史缺口/关联审查，不标从未审，完整结果或来源/输入改变后按复验管理。临床真实频率及完整保存/API/浏览器关闭仍由后续授权验收负责。
