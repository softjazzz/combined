# PRIV003 三入口最小方案与先红冻结记录

本文件保留已获批准的设计/先红历史，实际47绿及真实CLI限制见 `privacy003-repair.md/.json`。原PHONE反例未移除；主协调最终裁定为材料临床标记送达与手机号不得外发的双向检查，原业务状态/20/40/candidate断言保留。

设计依据为隐私修复树固定 `4232ca617`；002已由主协调独审并集成 `26f4fe645`。本文件仅方案，不修改生产/测试、不运行pytest/Node、不读取环境或患者材料，不调用PG/模型/网络。002生产文件冻结。

## 已知来源与明确限制

1. ordinary shadow：`_run:204–263` 经既有ordinary selector读三坐标、文书ID/时间/正文及exists布尔值，再建立evidence session，:240–248直接episode执行器→`_RecordingClient.generate`→真实client。selector SQL不投影患者原名/号码；session不能凭文书正文声称患者身份完整。
2. semantic20：`build_semantic20_review:436` 每case读取daily/senior/consultation，:482/:524直接generate。三类native字段白名单不含患者原名/号码；`author_name`是医师，不得作为患者姓名。case-map是既有公开JSON，不追加原身份。
3. 028 golden：固定 `SCENARIOS`、固定SYNTHETIC-I/P及scenario.label，`_session_for`仅内存row_reader；输入可证明是固定合成，但 `_run:103` 当前仍创建runtime配置client，:108–119直接native执行器。合成命名/result repr检查不能替代发送边界。方案不增加任意“synthetic=true”信任开关。

在不新增PG、环境读取、身份文件或公开字段的约束下，前两脚本的独立CLI没有充分身份来源。必须新增内部内存参数；默认独立CLI缺来源时固定技术拒发，不能计为业务验收通过。已找到的调用者中没有同操作collect来源；新增内部参数只为将来经审查的既有collect调用方留下正常接缝。合成验证可以证明来源有效时边界可运行，但不能等同当前真实脚本功能恢复。不能让缺来源默认值静默退成三ID provider。未读patient_information专有身份限制继续存在。

## 共用已有机制，不改002模块

借用现有 `_Luxian0609IdentityCollector`、`CaseRef`、`luxian_0609_case_identity_scope`、`build_luxian_0609_identity_provider`、`bind_luxian_0609_identity_provider` 和 `wrap_luxian_0609_llm_client`。不扩展共享scope/collector/client/repository/assembly生产文件。

真实输入内部参数为 `_private_identity_collector: _Luxian0609IdentityCollector | None = None`；collector的类型本身不是原身份真实性证明，只有已审查的现有repository.collect读取后产生的操作局部对象才能作为真实来源。当前没有这样的脚本调用方，不新增接受任意字符串/dict/callable的“已验证身份”入口；它是私有不可序列化对象，不是raw身份dict或任意三ID callable。借用方按完整CaseRef取得source provider；None、缺该病例、原姓名空/遮罩、collector关闭或失败都固定 unavailable。进入现有source-required case scope，再构造材料provider，并用带完整三坐标的bind返回组合provider，wrapper使用同一组合结果。

在构造真实客户端前调用组合provider作来源预检，避免native执行器将来源不足吞成一般结果；返回值仅短时内存，不保存/日志。预检不能替代wrapper及actual-attempt的逐次检查。整个native调用/两类semantic调用始终在病例scope内，finally恢复，继承lease禁止退出后延迟子task继续发送。不同病例不得复用已包装client/provider；共享底层客户端可复用，每病例wrapper新建。

调用方拥有真实collector生命周期，脚本仅借用并关闭自身scope，不提前close外层collector；上游既有worker finally/重试负责清空。固定合成collector由该脚本创建并在每scenario finally关闭。原身份不进入selector/case-map/record/bundle/ledger/JSON/trace/log或返回接口。

## 精确文件与改动所有权

| 唯一拟写文件 | 最小接缝与行为 |
|---|---|
| `backend/scripts/run_luxian_0609_consultation_ordinary_shadow_validation.py` | `_run`追加私有collector和可选内存llm_client参数；客户端创建延迟到病例来源预检成功后。现有session后至native调用/ledger构建套source scope，组合材料provider，使用 `_RecordingClient(wrapped_client,capture)`，保持既有stage capture。main/_run入口内没有合法来源可传，必须在该函数现有source读与runtime客户端构造前固定安全文案、非零退出（不覆盖顶层导入）；内部已来源正常接口仍按病例运行。无参数文件/CLI原身份输入。业务规则和ledger字段不变。 |
| `backend/scripts/review_luxian_0609_semantic20.py` | `build_semantic20_review`追加私有collector，现有llm_client/row_loader注入保留。每case source scope覆盖copy及consultation，材料provider只枚举本case已读三类缓存行的明确字段，不递归author_name/正文抓姓名；可用已有programmatic_timeline.structured_source_rows内存形状，不加入返回合同。每次生成前guard，来源失败或隐私拒发写固定 `privacy_boundary_error` 到现有_PARSE_ERROR_CODES，review_status=review_error/state=evaluation_unknown/agreement=None；不用transport_error掩盖，不记异常正文、不计completed。call_count在预检通过之后增加。main函数内没有合法来源可传，必须在构造runtime客户端或读输入前固定失败退出（不覆盖顶层导入）；内部函数来源失败仍使用安全review_error，不把它计为completed/验收通过。 |
| `backend/scripts/run_luxian_0609_028_synthetic_golden.py` | `_run`追加可选内存llm_client以离线运行，默认既有真实client路径只在明确运行时使用；仅接受硬编码SCENARIOS中的原对象（identity membership，不是名称或相等值），_session_for对新建/覆写Scenario固定拒绝；不增加scenario/材料/JSON/row_loader/来源flag参数或CLI输入入口。固定每scenario创建本地collector，只采固定合成姓名及SYNTHETIC-I/P/label，姓名不加入session文书或输出。套同样source scope+session材料provider+wrapper→native，finally close collector。保留原rules/reduce/expected及临床值；输出privacy_safe不能仅看repr，需与实际发送边界验证分开，不因拒发计passed。 |
| `backend/tests/privacy_closure_20261008/test_script_boundaries.py`（新增专属） | 只执行三脚本当前AST接缝/纯privacy模块，fake selector/session/row_loader/业务结果以及实际client attempt内存transport，避免脚本import应用config/DB。不改旧共享断言。 |
| `backend/tests/privacy_closure_20261008/offline_support.py` | 仅新增三入口AST加载支撑，不改已有002加载语义；与固定002的67项隔离。 |
| `docs/acceptance/engine-audit-20261008/privacy003-repair.md/.json`（新增专属） | 来源限制、红绿记录、正常/拒发证据和真实hook历史。 |

普通真实collector由已有调用方传入的内部接口扩展是必要条件；本次不新增worker调用脚本的集成路径、不增PG查询。若需要让独立CLI对真实输入继续模型执行，必须另行批准并找到现有合法已读身份传递入口；当前约束下不能宣称独立CLI的正常真实模型路径已完整恢复。

## 拟合成验证与验收边界（待测试槽，不现在执行）

- 三入口正常控制：完整CaseRef、活动collector、合成原姓名/病案号/联系方式，安全或已隐私处理临床文本；内存actual attempt到达transport，130mg、1.5h保留，规则/复核输出由明确business doubles验证合同，不伪装临床验收。
- 真实入口拒发控制：缺collector、仅三ID/遮罩姓名、holder错病例/缺病例、source异常、关闭collector；source预检或最终gate前observation/capture/transport均0，固定安全错误，无business completed/通过。
- 残留控制：原姓名/病案号/联系方式仍在普通自然文本且不能由通用规则消除；wrapper/gate固定拒发；可识别姓名标签先隐私处理后允许发送。原始值不出现在safe ledger/error/repr。
- semantic两条独立generate路径都覆盖，缺上下文不能被通用except改成成功；正常parsed business结果保留。两case并发/同visit不同完整CaseRef、嵌套、取消/异常、retry第二attempt和delayed child覆盖隔离与lease。
- 028每scenario固定合成来源，正常临床发送及包含SYNTHETIC-ID/姓名的残留反例；失败不计passed，来源关闭后的子task不发送。注入client使测试0环境/PG/模型/网络。
- 反例先用固定4232旧三入口接缝证明绕过，再用新scope+wrapper证明相同输入拒发；保留至少一个正常transport对照。失败拒发不是业务验收通过，也不是全面禁用模型的替代方案。

拟检查仅专属合成pytest、目标Ruff及真实标准hook；任何测试/提交都等待主协调窗口，不启动全前端。surgery/exam-lab其他golden仅继承初始审计索引，本方案不扫改、不追加安全结论。


## 全仓调用者复核补充

精确四个入口名全仓文本检索（排除依赖、锁文件和本轮报告）已完成exit0；后续用AST逐个核对找到的Python调用。结论是没有现有worker/service/route/任务配置接入这三个脚本，也没有已经存在的同操作collector可透传。

- ordinary：脚本自身main:266→_run:204→selector:179(existing SQL208–216)→session218→episode240→RecordingClient117→SichuanQCLLMClient.generate。唯一外部Python import为unit/test_luxian_0609_consultation_ordinary_shadow_validation.py:6，三个测试只测safe ledger/capture helpers，不调用_run。
- semantic：自身main:646→build_semantic20_review:436→现有row_loader460→generate482/524。唯一外部生产之外调用为unit/test_luxian_0609_semantic20_review.py的12处测试调用（159/172/179/189/221/239/263/288/325/335/351/361），均只传合成case-map、fake client、fake row_loader，不传合法真实source。其_case_map25–39只是三ID，_Client79–138是响应替身；这些事实不能触发生产“synthetic”绕过。文档中的引用仅说明复用历史_context，不是执行调用。
- 028：自身main:161→_run:102→固定10项SCENARIOS49–60→_session_for63→native108。当前main无argv/文件输入，未找到外部代码调用；Scenario是frozen dataclass，SCENARIOS是tuple。新方案保留无CLI材料覆写，不把SYNTHETIC字符串当来源认证。

因此003阶段只能认领三个已知入口的拒发边界修复及固定合成正常路径。两个真实脚本的独立CLI功能仍未恢复；需要另行有合法来源的上游接入，不能标PRIV003全部完成。

旧semantic单测在来源成为必需后不会再隐式获得正常模型结果。拟另申请该unit/test_luxian_0609_semantic20_review.py的**测试fixture/调用参数**所有权：以本测试固定20病例创建合成collector，并显式传至上述12处；不修改业务断言或放松隐私断言，取消/完成后close。若不批准该fixture扩展，应如实保留旧测试合同不兼容，不能通过识别fake client或row_loader来静默信任合成身份。ordinary旧helper单测不需改；028新增专属测试即可。

新增明确负向矩阵：ordinary/semantic使用SYNTHETIC-I/P或golden-01标签仍不能绕过缺collector要求；028 _session_for接受一个新建Scenario（即便标签与硬编码相同、但含任意材料）必须拒绝；_run不接收scenarios/row_loader/材料文件参数，main仍无材料输入。不能把Python内部替身身份字符串作为真实来源已验证的证据。


## 获批003边界子项的先红实施计划
主协调仅批准边界子项及固定合成正常路径；两个真实CLI来源未接，003功能不签收。已准备8项专属红测，未运行，生产3文件冻结。
1. 测试槽获批后仅运行 test_script_boundaries.py：ordinary缺源2例（真实坐标/合成标签伪装）、semantic两个generate分支缺源2例、028实际attempt残留1例、028新建同标签/合成标签Scenario2例，以及直接替换SCENARIOS tuple1例（必须在任何attempt前拒绝）。预期旧脚本触及内存发送或接受伪场景；环境/PG/真实模型/网络均0。若出现加载/替身错误先修测试支撑，不能把测试基础设施失败称隐私红。
2. 得到可信红后才修改获批3脚本：真实入口必需私有合法源、CLI固定拒发、已有scope/provider组合/wrapper；028固定原SCENARIOS对象、不引入可覆写输入。002公共模块不动。
3. 扩充专属正常transport控制、错误分类、并发/异常/取消/lease/重试反例；semantic旧12调用仅追加固定合成collector fixture参数，业务断言原样。测试/提交各等主协调窗口，不启动Node或全量。
4. 报告分别记录拒发边界绿、正常合成发送绿、真实CLI功能未恢复，保留未读专有身份限制；不得以技术拒发算业务验收成功。
冻结生产SHA256：
- `apps/medqc-web/backend/scripts/run_luxian_0609_consultation_ordinary_shadow_validation.py`：`3eb50465f78dd02a973e3c6b67cd89342fad290e45af349ef6f99858fa9d92af`
- `apps/medqc-web/backend/scripts/review_luxian_0609_semantic20.py`：`3f852842ee84611b20da91190052c8726ac6a112b8fe39c1e180b93072467a54`
- `apps/medqc-web/backend/scripts/run_luxian_0609_028_synthetic_golden.py`：`366ca26ca472910cba3f96efe160a0e472b38d22068f3730012c728d8086f1a0`

028实施还需固定私有基线tuple引用，入口核对公共SCENARIOS未被替换，并按基线原对象identity membership校验；专属红测直接替换SCENARIOS，证明不能仅校验当前全局列表中的同label对象。此处仍仅方案/红测，生产未修改。


独审后勘误：ordinary顶层导入app.database.connection可能在main前load_dotenv；本文“配置/source前拒发”均限定隔离的main/_run函数体，不证明真实完整CLI导入零环境读取。生产增量未新增env读取不等于既有脚本从不读env。固定d2e1718bb的根受控124绿（旧67+新47+真实import unit10，dotenv替换且PG/socket/.env阻断）只证明受控测试可运行；实际CLI可信身份来源未接、功能未恢复继续开放。详见privacy003-repair.md/.json。
