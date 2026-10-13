# 0609 下一阶段：050、026、055 当前基线复现

固定基线 `4dbcd8e819f439c576262eebd1565f0eab0774e2`。本次仅合成材料、离线工程执行，不访问外部模型、数据库或环境凭据，不修改生产。原历史反例和预期保留；本文件唯一 owner 为 phase2_other_defects，共享台账由 root 更新。

## 原材料与冻结

已读 AGENTS.md、下一阶段计划、ledger80-reconciliation/specialty/course 三份台账；仓库没有 `.codegraph/`。原入口位于 `.tmp/engine-audit-20261008/course-timing/{probe.py,expected.json}` 和 `tumor-pathology/{probe.py,expectations.json,antimicrobial_probe.py,antimicrobial-expectations.json}`。

专属冻结文件 `.tmp/phase2-other-20261009/frozen-cases.json` 包含 15 项：050 四项、026 原五项、055 六项。原 JSON 输入直接复制，050 输入逐字从原 probe 提取。冻结 SHA256 `df6f636981d8c4406c4af6ca27ede89fe13d67ea076529a3cc849012ed1f3451`，原文件哈希在 `freeze-manifest.json`。

执行路径为 native → binding/reducer → Canonical Finalizer；050 旧 probe 只有 Renderer 出口，此次保留其原 reduced 状态预期并补 Finalizer 出口。026 原五预期保持：同药肯定 130mg 为 C、否定给药为 NC、仅计划为 DG、借他药剂量为 NC、实际剂量与计划混合为 DG。055 48/60/72 小时明确疗效“美罗培南抗感染治疗效果评价：体温下降。”预期 C；47/73 小时及无抗菌语境疗效预期 NC。

## 当前结果

| 规则/根因 | 当前分类 | 原预期与观察 | 证据 |
| --- | --- | --- | --- |
| 050 / CT-01 | 仍存在 | 否定、未来两项 NA → NC，均 required_document_missing；肯定 NC、无 marker NA 两保护符合 | baseline-050-1791528846845055200.json |
| 026 / TP-D02 | 仍存在 | v3 原五项：肯定130mg C符合；否定 NC→C、计划 DG→C、借他药剂量 NC→C、实际/计划混合 DG→C，均 requirement_satisfied | baseline-v3-026-1791529029807805400.json |
| 055 / TP-D05 | 仍存在 | 48/60/72h 三项 C → NC，均 threshold_exceeded；47/73h 与无抗菌语境三项 NC 保护符合 | baseline-055-1791528883524719100.json |

三份成功执行产物与首异常产物均在专属 `.tmp/phase2-other-20261009/`，含实际 Git HEAD、前后0609源码/目录JSON哈希、原生客户事实和 Finalizer 完整结果。三份成功产物导入前/导入后/执行后哈希完全相同。每项程序记录 llm_call_count 为零；外部网络、数据库与凭据读取由隔离守卫阻止。没有用旧候选通过率证明当前通过。026 四项误判客户文案均称药物名称、剂量、方法和时间一致。

## 接线与后续修复核对

050 当前 `native_extended_document_execution.py:2363` 调用 `extended_document/difficult_case_trigger.py`。其最后提交 `88aa13770` 仅排除邻接历史时间词且当前明确解决的情况，不处理本次否定/未来原反例；因此后续修复存在，但 CT-01 未关闭。当前主表三个规则均 active，026 目录实现 implemented_native；正式默认选择的运行时范围由 root 独立核实，不能将旧 overlay 当实时状态。

026 当前生产仍使用既有整篇候选剂量比较，不消费隔离候选 `chemotherapy_local_dose_facts.py`。N13 的 `880a433b0` 及 TP-D01 限定工程修复不能关闭跨药归属。原合成 C18.9 由 `malignancy_fact.py` 的结构化恶性编码 fullmatch 先行确认，不使用 fake 恶性结论；NoModel 仅阻止意外模型调用。共享恶性门控在 resolve 内 create_task，导致手动 coroutine 驱动无事件循环。v2 复制现有 offline_guard，使用受守卫 Windows SelectorEventLoop，但在 SQLAlchemy 导入的 platform.machine → Windows platform._syscmd_ver 子进程被守卫拒绝，业务尚未执行。第二次接线失败摘要保存 baseline-026-v2-startup-failure.json，完整 traceback 在 Codex 命令输出。v3 仅按现有R2 runner次序预热 platform.uname()/machine() 后 install，不弱化守卫；root核读并授槽一次执行成功。v1/v2和首异常保持。准备阶段 future import 位置错误由 root 静态发现并改正，纯 compile 通过，此项不是执行失败。

055 当前 `_is_antimicrobial_effect_evaluation` 要求有限结果词；“体温下降”没有被承认为结果。不能仅扩词迎合反例，应冻结同一目标抗菌药的明确疗效评价事实及引用，保持任意检验趋势不能充当评价的边界。

## 轮次与停改约束

本阶段生产修改零轮，基线业务复现不计生产修复轮次；026 接线尝试三次，前两次失败、第三次成功，已如实保留，不能隐藏。尚未授权任何生产修改。

026 历史候选计划记录：首次35为34/1；专属39加四旧保护共283为164/119；42为37/5；最后67为65/2。原否定 NC 未达在上述迭代持续出现，widened 他药剂量坏响应在42/67持续假 C；旧115失败未恢复证明。按同根因保守清点，已有至少三次实现后验证仍失败的证据，不能在新阶段归零。应停止该否定/跨药局部事实候选根因继续生产试修，交 root 核验每轮源码 manifest 与准确归因。050/055 未找到本根因已发生生产试修的轮次证据；不能将其他子项修复计入或重置它们的轮次。

## 最小运行命令及槽

从仓库根执行：`python .tmp/phase2-other-20261009/reproduce.py --root-slot-authorized 050`、同命令 `026`、同命令 `055`。三项首次命令已按 root 授槽串行执行；026 异常立即停止，随后 root 单独授槽执行055，已释放。

026 成功最小命令：`python .tmp/phase2-other-20261009/reproduce-v3.py --root-slot-authorized 026`。实际执行前验证 HEAD 与冻结输入 hash，源码在应用导入前冻结并记录导入后/运行后 hash；产物使用独立 time_ns 名称，不覆盖首结果。v2/v3各经root单次授槽，最后已释放；不继续重跑。

下一步只读准备：050 优先复用现有受控当前状态、否定和时间作用域事实；若现有能力不足，列明新语义合同与预算，程序消费事实后判触发。不追加否定/未来关键词表，不擅自调用模型。026 历史轮次审计与能力缺口优先交 root 决策。

## 050/055 最小通用设计草案（未实施）

现有可复用入口：`course_body_fact_extraction.extract_course_body_facts` 提供逐文书、严格集合、受控JSON和原文引用边界，但仅判正文 present/absent，不输出诊断状态或疗效归属；`extended_document/diagnosis_change_extraction.py` 提供逐文书 reason/basis present/missing/unknown 的单次批量、隐私view和引用校验，但限定074诊断变更，不能直接借其结果裁定050；`extended_document/antimicrobial_action_extraction.extract_confirmed_antimicrobial_actions` 已表达 affirmed/negated_or_planned/no_action/uncertain，可复用事件/药物绑定和抽取实现模式，但其合同是054动作，既有 `_SHARED_ACTION_BLOCKERS` 包括疗效/效果，不能把疗效正文塞入动作合同。

**050 缺失事实：** 每份可核查病程中每个诊断问题的当前状态（明确/未明确/未知）、极性（肯定/否定/未知）、时间作用域（当前/历史/未来条件/未知）及连续引用。程序以可信文书引用和原文问题span生成局部问题键；模型自报问题ID不构成关联证明。必须校验问题提及、状态/极性/时间作用域引用span确实属于同一输入文书，坐标与原文逐字一致；“同问题当前解决”还须可核查地指向原问题，不能仅凭模型复用ID或另一诊断已明确抵消本问题。存在多个可能问题、重复引用、代词指代或跨文书关系无法唯一确认时进入关联歧义分支，不猜owner。逐字span校验只证明引用有效，不能证明模型对问题关系的语义判断正确，仍须独立语义验收。模型只抽事实，程序以已有可信病程时间、入院时间和7天窗口决定触发；不让模型判成熟时间或最终质控状态。仅历史且同问题当前解决可排除。未知按现有规则未决合同处理，不能统一映射DG；合法空数组本身不能证明无触发。

**055 缺失事实：** 每个目标抗菌药事件对应每份病程是否有已完成的疗效评价（present/absent/unknown）、被评价药物/事件引用、评价连续原文、极性及时间作用域。本次“体温下降”仅在明确抗菌疗效评价语境下作为评价，不能扩为任意症状、生命体征或检验趋势。程序仍按已有可信起始时间和病程时间计算48～72h。药物提及span、给药动作span和评价语境/结果span必须在可信文书原文可核，模型只返回程序给定候选键；程序以既有结构化医嘱/动作事件键、文书引用和明确局部关系核对目标，不把模型自报药物/事件ID当归属证明。一个评价可归属于多个药物或事件、仅有不明代词、跨文书关系未经证明时保留关联歧义；不能以全篇药名出现或span几何相容自动确认。结构与引用校验不替代语义正确性验证。其他药/镇痛评价、将来拟评价、否定“未评估”和纯趋势不能借用。

**预算和失败合同：** 050与055当前 phase1 extension均program_only、v1、max_llm_calls_per_rule=0。新增上述语义会改变正式调用行为，0→1仅是待评估的单次批量方向，尚未批准。撤回8份/合计12000字符/每份6000字符/输出2048 token建议：这些数值没有本规则正式来源上限及输出基数依据，不能继承其他模块参数。须从正式source limit、实际文书集合/去重引用上限、每文书多问题/多药/多动作输出基数、引用长度和完整JSON输出开销推导，再核token、HTTP尝试和金额预算及超限处理；未冻结前不接线、不调用。050与055独立事实用途，不能未经定义让一个规则代付另一个调用，不默许隐藏重试、分块或截断。

语义unknown、关联歧义、schema/引用invalid、来源unavailable/truncated、客户端失败分别记录，逐项沿现有规则/共享出口的对应状态与reason_code，不统一降为DG。合法空数组只有在来源完整、所有程序候选已覆盖且明确抽取为无相关事实、无unknown/歧义时才可进入“无触发/无评价”的既有程序分支；空数组本身、漏项或来源未就绪不能建立不存在事实。重复键、额外/缺失候选、错误引用是输出无效，不伪装为语义unknown；来源不可用不是模型未识别；模型调用失败不是临床缺失。正式状态映射须先冻结现有合同对照表再实现，不能回退旧关键词判C/NC。预算与状态合同均未批准，真实provider/HTTP重试与金额尚未冻结。

**文件边界：** 建议新增唯一语义owner `extended_document/diagnosis_scope_extraction.py`、`extended_document/antimicrobial_effect_extraction.py`；由root登记owner后只在 `native_extended_document_execution.py` 对应分支消费。共有 `rule_contracts.py`、`luxian_0609_phase1_rule_contracts_extension_v1.json` 以及必要的结果mapping字段由root串行维护；Renderer/Finalizer仅在新增明确公开事实确有需要时调整，不伪造旧计数/引文。复用现有隐私发送view与来源读取，禁止新增药名/否定关键词表或病例ID答案分支。合成测试文件应与生产/真实语义证据分开。

**冻结保护与泛化：** 050保留原四项，新增不同否定位置、未来条件、历史已解决、历史仍未解决、同文书多诊断互不抵消、双重否定、缺时间、不可读正文与错误引用；变换语序、问题名和文书位置但医学预期不变。055保留原六项，新增其他已知抗菌药在明确疗效评价语境下的同义体温表达、另一药评价、仅体温/检验趋势而无评价语境、拟于未来评价、明确尚未评价、同文书多药混合、跨文书不得借事实、48/72边界与缺时间；不扩大为任意趋势。两规则均新增合法空数组但来源未就绪、候选漏项、未知与输出无效分别处理、模型自报ID与原文span不一致、重复span/多owner歧义保护。不写专用词表让变体过关。工程人工事实替身只证明程序消费与合同，真实语义必须另经冻结输入/独立金标/预算批准后验证，不把fake green等同模型正确。

**轮次账：** 050与055各为本根因已知生产失败轮次0（未找到历史同根因试修证据，交root核验）；冻结baseline不算修复。未来每次实现记录源码hash、假设、原反例/保护、结果和失败原因，同根因最多3轮失败，第三轮停改；新增事实schema、换模块名或阶段名都不清零。026已获root确认至少三轮历史失败，严格停改，后续只保留调查/方案与原证据。

## 独审意见与设计修订

独审提出三项设计阻断：参数缺本规则来源/输出基数依据；模型自报关联ID不是关联证明；unknown、invalid和source unavailable不能合并或由合法空数组假定无触发。本次仅修订草案：撤回具体容量/token参数，补程序可核原文span、可信候选/事件键及歧义分支，分开保留现有状态并要求冻结映射对照。055明确限于“明确抗菌疗效评价语境下的体温变化”，不扩任意趋势。

上述修订尚未构成预算、状态映射或生产实现批准。待正式source limit及多问题/多药输出推导、独立语义预期和现有状态合同对照充分后由root复核。未修改生产、未重跑测试、未调用模型/数据库；026继续严格停改。
