# RR-M01 / 074 模型权限与执行合同收口设计（设计与工程收口）

2026-10-08。范围仅 `LX0609-12-02-01`（原074，修正或补充诊断时应记录理由及诊断依据）。阅读基线为危急值固定提交 `0628782191861460bbf24edbf848eb601829876c` 的独立树 `F:/MedQC-worktrees/qc-fix-critical-v2-20261008`。准备阶段仅阅读既有业务标准、执行合同、Prompt、调用与历史交接文档；主协调随后批准以下最小元数据修复。危急值及074执行器、Renderer、Finalizer继续冻结。全程未读取.env、连接PG或网络，真实模型调用为0。

**建议对齐074的执行权限合同为 `program_then_optional_llm / max_llm_calls_per_rule=1`，保留现有受控事实抽取与Python裁决，不为满足旧0调用元数据而撤掉语义路径。** 已按此建议完成最小元数据修复与合成工程验证，待固定提交独立复核；不代表当前Prompt的真实语义准确性已验收。

## 本次实施与验证

本次只修改074覆盖合同的 `decision_authority`、`max_llm_calls_per_rule`，目录的 `prompt_version`，以及旧program_only精确集合中的074项；新增专属21例测试。目录版本标识为 `lx0609_diagnosis_change_documentation_v1-quote-2026-10-07`，对应现有schema与10月7日引文Prompt修订，仅作版本留痕，运行时仍使用既有抽取函数。`executor_type=program`、规则版本、typed_shadow_v1、golden pending、目录发布状态及其他条目均未改变。没有新增Prompt、模型调用、重试或全局预算框架。

- 红测21项：12失败、9通过。失败仅为加载权限仍program_only/0、Prompt版本仍none，以及真实fake执行1次超过加载预算0。最初PowerShell转码日志已用子进程UTF-8直写重跑，以下红测日志为有效证据。
- 修复后新增21项全部通过；覆盖合规、缺理由/依据、unknown、2/12文书单批1调用、传输/引文/截断/usage失败无重试，以及前置来源/时间/上限/无客户端/结构化声明等0调用路径。均经原生typed执行→绑定归约，检查实际请求与Token计量。
- 第一轮7文件99项：95通过、2失败、2fixture错误。两个旧合同断言为总数硬编码84但当前目录85、typed_shadow集合遗漏`LX0609-08-01-05`；使用HEAD原合同及原测试只读复现同样两处失败，保持不改。两个API用例依赖隔离runner未加载的client fixture，明确列为**本轮未执行API**，不视为历史业务失败或API通过。
- 明确排除上述4项后，7文件聚焦95通过（4 deselected，1 warning，6.61秒）；另原native_extended中074保护37通过（377 deselected，1 warning，3.88秒）。本轮工程绿测合计132项。未知与技术失败保持既有不可交付结果合同，未改变临床判据。
- 两份JSON剥离074对象后原始字节SHA保持一致；074其余字段结构等价。专属测试及旧集合文件Ruff通过，`git diff --check`通过。原抽取模块及Prompt正文SHA保持`eb6f67e2fa4cc9f028a0740a1acbb16deab052ec0f822287c9b869cbd9b7e853`。
- 前端源码/配置1147文件与危急值批次冻结manifest逐项一致，继承此前lint结果（0错误、1214既有警告）。根/应用AGENTS资源最低门禁按主协调本批统一安排；此前type-check受内存压力正常中断、结果未确认，全量前端unit未运行，本轮未重复启动。本次提交使用真实Husky及编码校验；只有hook成功后的固定提交才作为交付候选，实际输出保留在`.tmp/rr-m01/commit.log`。

临时证据位于本树`.tmp/rr-m01/`，不提交：`pytest-red.log` SHA256 `214bffcbfc000232af9ce84590e8fce71661f788607abdab0f5b544f5f75e816`；`pytest-green.log`保留首次完整99项结果；`baseline-contract-failures.log`保留原基线失败；`pytest-focused.log` SHA256 `c9023144a27ebf50462fbd8afe0e038b4226e51c986edbb6476da792f73223c3`；`pytest-native074.log` SHA256 `385c174b7aaadcd3003aeaec0948924cfdc5a6cd0bd1f7165657acecf6ccfa32`；`freeze-verification.json`记录冻结及日志摘要。

其他条目原始字节SHA：合同`edbc0e7beadc6d7a2fdb1f3e88cb83ac339f48fa4d0e1246b22c9654179f4d44`；目录`05bb2888cc4736708d9edc96c99327b4f2ac1fd59ff84cbdc2d11c3634ca54d3`。修复后整文件SHA：合同`30f2469af9e3c989f9447f05cdd18e5d9cd7878e66128791c17b916ece1af316`；目录`f593e61b36b00c72b170f7280ff9875e07e105ded225c86e4d3e78e693f8a804`。

权限与版本元数据工程收口待独立审计固定SHA；原C20与074真实模型语义复验继续独立待验，不能用这些fake结果宣称临床或模型验收通过。

## 业务与既有设计依据

- `docs/0602/泸县0609质控点-业务标准基线-v1.md:162`：074要求修正/补充诊断时记录理由及依据，状态为正式、已确定。
- `docs/0602/LX0609-我方口径标准汇编.md:63`：病程正文显式变更与入院记录结构化修正/补充声明是并列触发通道；静态入出院诊断差异不自动触发；两通道完整但均无声明时不适用，声明来源不可读时资料不足。
- `docs/0602/泸县0609事实抽取优先质控路线说明.md` 提供可追溯事实抽取与后续判断分离的总体路线。本文件本身不授权074新增模型调用，不能单独当作放宽权限依据。
- 074特定依据来自已经存在的 `extended_document/diagnosis_change_extraction.py`、对应专属抽取测试、`docs/acceptance/2026-10-07-074-quote-repair.md` 及 `docs/plans/2026-10-07-0910-codex-repair-handoff.md:289`：该路径明确按同一文书做单次受控语义抽取，已针对连续引用改Prompt并保留单次、无重试、Python映射。既有历史交接继续为这条路径准备真实复验，表明此能力是现行设计组成，而非审计中临时调用。
- 集成树 `docs/acceptance/engine-audit-20261008/rescue-remaining.md:47` 冻结RR-M01：合法引文合成客户端实际调用1次、判合规；加载合同仍program_only/0。该审计没有替项目方裁定修合同或修执行；本稿提供推荐依据。

原C20无效连续引文、10月7日Prompt工程加固及待授权真实复验是独立问题。权限元数据对齐不会使旧无效响应变合法，不得顺手改解析器、模型失败映射、恢复/重试、医学预期或客户展示合同。

## 当前加载合同与目录漂移

| 所有者                                                                     | 当前074值                                                                       | 本项建议                                                                                                              |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `backend/app/data/luxian_0609_phase1_rule_contracts_extension_v1.json:267` | `decision_authority=program_only`；`max_llm_calls_per_rule=0`                   | 仅该条改为program_then_optional_llm/1                                                                                 |
| `backend/app/data/luxian_0609_phase1_rules_extension_v1.json` 的074条目    | `executor_type=program`；`prompt_version=none`；规则版本2026-07-31              | 最终裁决仍由Python，不能将executor改成LLM直接裁决；Prompt版本应标记既有受控抽取Prompt的真实版本，避免字面none继续误导 |
| `backend/app/data/luxian_0609_rule_master_v1.json:618`                     | active、customer_confirmed；业务点理由及依据                                    | 不改变医学口径、发布状态或rule master身份                                                                             |
| `backend/app/services/luxian_0609/rule_contracts.py:184`                   | authority只允许program_only/program_then_optional_llm；前者强制0，普通后者强制1 | 074属于已支持的普通1调用，不需新增枚举/放宽全局校验                                                                   |

`rule_contracts._load_payload` 读取主合同并追加phase1覆盖层；`compile_luxian_0609_rule_contracts` 原样编译authority、调用上限及目录prompt_version。当前不是读取了错误的旧alias，而是074覆盖层本身声明0。现有测试 `test_luxian_0609_rule_contracts.py:267` 还把074列在program_only精确集合，需对这条同步修改；typed_shadow和golden pending不因权限对齐升级为临床已验收。

目录的 `prompt_version="none"` 是非空字符串，现有 `bool(contract.prompt_version)` 不能证明它是有效语义Prompt版本。因此不能仅改权限两字段后便声称所有目录元数据收口。实施阶段应对该074条目冻结一个反映现有抽取schema及10月7日连续引文Prompt的版本标签，并明确这只是版本留痕，不重新发送Prompt。无需为普通元数据新增逐文书digest或改变其他规则版本。

## 实际调用与计量路径

`execution.py:468` 将原生extended_document函数注册给统一引擎；兼容主链 `execution.py:865` 也把同一 `llm_client` 传给原生执行器。074只在自己分支抽取，不给同族其他规则新增调用。

`native_extended_document_execution.py:4526` → 无结构化diagnosis_rows时搜两种病程的显式修正/补充事件 → 校验每份候选权威记录时间 → `:4668` 单次 `extract_diagnosis_change_documentation` → `diagnosis_change_extraction.py:406` 受控输入与隐私处理 → `:429` `llm_client.generate`（max_completion=2048、allow_length_retry=False） → 严格解析与连续引用/诊断关系验证 → 原生Python映射理由/依据状态。`:5010` 将实际调用、Prompt/Completion/Total Token及耗时汇总到原生结果。

| 输入/分支                                                | 当前实际调用 | 保持的结果语义                                                                                                                    |
| -------------------------------------------------------- | -----------: | --------------------------------------------------------------------------------------------------------------------------------- |
| 完整来源、两显式声明通道均无变更                         |            0 | not_applicable/trigger_absent_complete，保持来源读取引用合同                                                                      |
| 来源不可读/截断、候选时间缺失                            |            0 | 对应data_gap，不发起语义抽取                                                                                                      |
| 结构化诊断历史或结构化声明的既有程序分支                 |            0 | 按现有事件与关联判定，本项不重设计                                                                                                |
| 合法、带权威时间的病程显式变更候选                       |            1 | 一次请求覆盖至多12文书、总字符16000；理由/依据均present→compliant，missing→non_compliant，unknown→uncertain后续按不可交付合同处理 |
| 该语义分支无可用llm_client                               |            0 | technical_error/model_transport_error，不能退回弱词法判定确定临床结论                                                             |
| 已发起请求后传输失败                                     |            1 | technical_error/model_transport_error，计实际调用，无自动重试                                                                     |
| 输出截断、非法结构/usage、无效连续引用或无法可靠验证关系 |            1 | technical_error/model_invalid_output；保持既有严格解析和现有关系校正规则，不把失败伪装资料缺口                                    |

`program_then_optional_llm` 中optional表示某些输入路径0调用，某些触发路径允许1次，并不表示模型可以直接决定最终质控状态。最终触发、时间、事件绑定和状态仍由Python拥有。上限1是规则级预算，不是每文书1次；多个文书仍只能一批请求。

## 推荐实施范围与替代方案代价

推荐后续重新授权owner仅持有：上述074合同条目、074目录Prompt版本条目、专属合同/调用对齐测试，以及测试中074的program_only清单断言。不需要修改冻结中的 `native_extended_document_execution.py`、Renderer、Finalizer、共享解析器或其他规则合同。若目录Prompt版本只是展示字段，仍需明确声明其版本含义，而非虚假声称运行时从目录动态生成Prompt。

另一条路线是让执行符合program_only/0，但必须先提供覆盖自然语言理由与依据的可靠确定性方案及同输入证据，独立验证同文书/同次变更、否定、计划、missing/unknown、连续引用和失败语义。仅删除调用、加一个0预算门禁使原来可判定分支全部技术错误，或重新采用理由关键词，就会改变现行语义能力；既有业务合同和历史设计没有支持该倒退。因此当前证据不推荐走该路线。

不建议在RR-M01中新增全局调用预算强制器：本轮证实的是074元数据漂移；多规则族计量/预算实施的公共问题需另立证据与owner。也不能为通过旧精确集合而给074隐瞒实际调用量。

## 设计阶段关闭标准（工程实施结果见上，真实语义验收仍待授权）

1. 先冻结仅074允许authority/1和有效Prompt版本的合同预期，保证加载后值与实际路径一致，其他规则合同条目原值保持。
2. 以合法合成客户端经正式typed入口验证present、missing、unknown、传输失败、无效输出：发生请求必须实际计1，无请求分支计0；Tokens、耗时与usage一致；无额外重试，未知/失败不交付确定临床结果。
3. 保留无声明、结构化声明、候选时间缺失、来源不可读、候选超上限、同文书关联及连续引用保护；Prompt正文、schema、既有事件/状态/客户事实合同不因权限修复改变。
4. 固定修复SHA，由独立审计重跑RR-M01冻结合法引文探针并核对加载合同及实际计量。可按既有交付合同验证合成结果保存/API投影；不把工程替身当真实模型或临床准确率。
5. 074新Prompt真实语义复验仍单列授权和当前证据要求。本稿不启动该计划、不消费任何历史或建议模型预算。

## 固定只读材料

SHA256：合同覆盖层 `b311ffefca209dd100f8578bc54bb4d23157737256e01d04315ae1752b06e5de`；规则目录覆盖层 `ca4dd781014946202711a71f389c7fd60dda223a4479e20e1a356f2c37e54d14`；074抽取模块 `eb6f67e2fa4cc9f028a0740a1acbb16deab052ec0f822287c9b869cbd9b7e853`。这些是已阅读的当前文件哈希，不代表当前Prompt真实验证通过。
