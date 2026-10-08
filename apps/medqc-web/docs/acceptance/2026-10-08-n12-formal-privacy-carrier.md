# N12-PV01 正式隐私发送承载修复

固定起点 `2f44aa44e86251acda81383e1b2bd84423008451`，只修037 helper承载及测试协议。原43直接fake工程证据仍保留；正式helper/wrapper独审10中地址/单位6例吞ASA/神志quote、4普通/电话例保留，10例JSON仍可解析，缺陷不是无效JSON，也不撤销此前限定语义/state结论。

## 原版红与最小修复

原body、GOLD、private前缀逐字继承独审冻结 `review-artifacts/n12-carrier-boundary/expectations-frozen.json`。正式production wrap到delegate的15红实际6failed/9passed、1warning、4.01秒、exit1：原10六损坏/四正常；新增known identity/provider failclosed两例和marker数据三例通过。回执全为合法unknown，不用quote损坏制造fixture异常；红日志/完整性manifest保留 `.tmp/n12-carrier/formal-red15.*`，原独审文件不覆盖。

JSON转义实际换行令全局wrapper第二遍隐私正则越过原行边界，损坏第一医疗片段且改变span。复用已集成TC02长度块策略：INPUT_JSON只含受控ref/source/required_fields、正文字符数与ordered span字符数，不放正文或引文；每个原span按元数据原序独立放SPAN_BEGIN/END真实换行长度块，直接展示原span_id和原text，不重复正文。内部同名marker仍是正文，不提前切换文书；按原序无额外字符拼接spans即原body，原独立换行span也完整保留，present仍为body全局坐标、absent仍覆盖body总长。

Parser仍对第一次受控脱敏body/spans作原same-doc quote/坐标、whole-body absent、unknown校验；正式delegate捕获证明同一view才能认为发送边界闭合。医学response schema/version、必填字段、三态、原判据、原文、调用预算及reason不改；长度只消费数据，不判断医学完整性。

仅三个fake协议reader适配机械承载，全部冻结facts、医疗输入、mutations、状态/缺项/证据等原断言保持。AST逆转reader调用后整个原文件相同，生产 `_parsed_fields`/范围门控AST相同。全局privacy/wrapper/身份provider、native、renderer、Finalizer均不写；不unwrap、不建新client、不加调用，仍逻辑最多1/4096completion/no length retry。本模块逻辑1不能当成下游真实HTTP1。

## 保护与边界

新增20工程保护：原10完整医疗quote/同一body-spans/private removal；known identity和provider异常保持逻辑1/delegate0资料不足；旧`:full`标记/尾空格/字面转义marker三例保持正文（没有验证最终`:sN`同ID尾标记碰撞）；正式native完整已给事实C、跨doc quote/span、错误whole-body absent范围与unknown沿原gap合同五例。实际模型是否理解字符消费/真实输入完整性仍未验；helper ready及returned fullscan不证明模型已通读。

计划沿用原完整354参数及新20，当前基线另已集成TC02权限测试1，实际完整375（355旧节点+20新formalwrapper）；原354节点全部保留，严格离线guard拒绝env/private/DB/network/model/subprocess，结果执行后补录。生产modified仅anesthesia_visit_fact_extraction.py，另三个旧fake reader、新formaltest及本文档共六路径。无PG/env/真实患者/真实模型/网络，工程承载不替代临床金标。

静态证明脚本初次AST路径拼接AttributeError在绿测前修正，未运行测试，不混为生产红或fixture失败。Python Ruff/静态与真实Husky编码按提交门禁。前端无变化，按根资源调度复用同源码lint，不重复前端type-check/unit；本轮不声称这些全量门禁重新执行。

## 首次绿尝试与承载精化

首次按预估374命令实际收集375，370通过、5失败、1warning、30.23秒、exit1。原354保护及新增的既有TC02权限节点通过，原正式wrapper15也全部通过。附加5在完成native/reducer/Finalizer后，旧测试辅助\_run访问真实wrapper不存在的calls属性，尚未到达医学断言；记为新增测试支撑失败，不能计为医学状态通过。日志green374.log、exit及integrity原样保留，未覆盖原15红或五例预期。新增分母来自既有rule_contracts文件已集成的070单调用权限测试，与本任务新增无关。

根亲读要求保留原模型可见信息：首版fullbody+长度字典虽Fake可恢复span，真实模型仍需重建标签，不能据此宣称等价；已精化为逐原span实际换行块，直接显示原span_id和原text。Parser/GOLD/原测试医学断言保持不变。新五例接缝仅在新增文件观察真正delegate.calls，generate绑定正式wrapper原bound method；不伪造计数、不改wrapper或旧\_run、不unwrap。单独冻结span-revision-frozen.json及AST逆转证明，原expectations与supplement不覆写。精化后严格guard完整375实际375通过、1warning、15.64秒、exit0；原354节点与基线TC02额外1均通过，正式wrapper20均到达原断言。375门禁日志green375.log/results/integrity保存，源/测试/冻结预期before-after hash一致。调用与parser结果：原10实际delegate正文/spans/ASA及神志等quote逐字一致；已知身份与provider失败两例逻辑1/delegate0闭gap；三个旧`:full`marker文本完整保留（未验证最终carrier同ID尾标记碰撞）；新增正式native五例实际完成C及跨文书quote/span、整body absent、unknown→gap断言。fake提供人工原子事实，不证明真实模型通读或医学语义。

精化固定helper SHA-256 `e7185348a8c2d6a2aa97444656552485c14a8cf8a8d5b9570491ec8d1de282c0`；新formal测试 `d8f515552ead7c7d8ecfa130ac2d9458338cf6894da2a2cadc5b8c00c4f24b27`；完整375日志 `d4713f752d0420f860e7bb5b10d12e64fa04834b1fa6e80d996af14e8b6aa4ec`。严格离线guard拒绝`.env`及`.env.*`、PG/network/真实发送，仅精确stdlib socketpair开放。375不扩充临床验收：实际真实模型调用0，原有限工程合同与真实模型语义未验边界保留。

提交前exact6暂存diffcheck首次捕获新formaltest两处字符串外尾空格，退出2、commit/hook尚未启动；仅移除格式尾空格，整个AST（全部医疗字符串/原断言）相同，保存staged-format-ast-proof.json。375测试时新test字节hash仍按原日志保留，暂存格式后hash `eeab0d90e91ec57e59201ec47cb9d18b2f74bc744de1f99ce4e76c9bd6404844`；生产helper字节hash保持测试版不变，不冒称测试文件字节完全未变。

标记碰撞限制：原三例在最终逐span carrier下仍是旧`d1:full/d2:full`文本；它们证明该文本完整性，不能当成最终`dN:sN`同ID碰撞已验证。完整375未追加或替换这些用例。同ID尾标记碰撞需后续独立严格构造载体保护，当前保持未验证，不能由length reader通过推称全部碰撞已验。
