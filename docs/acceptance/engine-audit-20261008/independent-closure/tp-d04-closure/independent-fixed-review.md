# TP-D04 固定源独立复核

当前阶段：固定独审执行完成，35/35通过；只审 TP-D04 / LX0609-05-01-06，没有改生产/测试/独立预期，不扩 N13 或 TP-D05。

生产提交 f2d744f273a1b55fe3ff2bfd29a863f72292741e；test/doc 跟进 HEAD 0162efe65ebe2ae6105080a9eaada7b51b6aa892；树 F:/MedQC-worktrees/qc-fix-critical-v2-20261008，静态读取工作区 clean。

原测试工作副本两树均 SHA256 dace2fad205b0e1e8a4122fa2b57fc756ebd4343aff62fbb071886ad77138e5e；Git LF blob ca9ffc5c58d148c89045c36f91a14df816da73ab16747378f187998e5744bbde。CRLF→LF后逐字相等，AST完全相等。9场景与全部原oracle与独立 expectations.json 等值，其 SHA256 3be945d5414d1396f7014ced5aa5687a0fc75443247446e49f127d199f50e2aa 未变；原NC不改。

固定 native_extended_document_execution.py SHA256 69cbc294eaa9203b7878afcecbc219badc7304d7ac40a5e670346e7b69302f9d；customer_renderer.py b752318f6f41d343f92cb15208bfea212b8204eb24effe5ac1ded256e1e22844。两文件工作字节、0162 Git blob、f2 Git blob均相等。补充test当前 SHA256 0debaf0cfed02fe1a94173ee847b9790091ad5b205b2a259637c645b22cb20a3。详细核对保存 independent-fixed-source.json。

058 fallback只在单事件且现有完整抗菌药目录未识别支持药名时接纳匿名支持；已知别药不再走单事件无条件回退。未加药名/否定/日期词表，未改变临床时间合同。原具名/既有order-ID路径没有扩大，未补造真实投影没有的会诊order字段。目录外未知药仍可能匿名，本次不称识别或排除任意未知药。

实际 matching_rows 同时进入精确文书证据与 associated_expert_support_rows，公开 expert_support_present/time按已关联列表汇总，不借其他药全局最早意见时间。Renderer单药无关联说明未找到可关联到该药计划的支持；多个具名全成功说明逐项支持，不用全局最早时刻逐药断言。原多药半覆盖unmatched分支先于late文案，根提出的原半覆盖晚于文案疑点静态未证实，补正逆2保护未据疑点改生产。f2生产差分只 native058/renderer058；0162不改生产，不改mapping/Finalizer的原8字段合同。

原18 + 补充15 + 多药半覆盖2 = 当前35节点；33为f2阶段总数。本次单次执行原18全部断言和补17（别药早时点干扰8、多个具名成功2、已知普通别药2、合成SQLite新实例3、原多药半覆盖文案2）。独立runner阻断.env/PG/database API/网络，仅允许合成SQLite，固定HEAD及源码哈希并比较原CASES；只包装测试助手记录一次真实native→reducer→Finalizer返回，不改生产或oracle、不重复调用。原red18保留。实际运行结果见下文；静态与动态证据分别记录。


## 独立实际执行结果

2026-10-08 root正式授独占槽后，单次运行 python -X utf8 F:/MedQC-worktrees/review-artifacts/tp-d04-closure/run_independent_fixed.py。35 collected / 35 passed，0失败，1.36秒，exit0；无过滤、skip、xfail，三个SQLite新Engine/Store回读实际执行。执行结束立即释放测试槽，无后续重复测试。XML independent-fixed.xml；35条native/reducer/raw facts/final对象及原合成输入保存 independent-fixed-observations.json，摘取及独立对照 independent-fixed-summary.json。固定源码哈希运行前后均相等。

18条原独立冻结oracle逐条核对实际观察，状态/原因/事实/精确文书证据均符合。原 expert_other_drug 正逆序实际 NC/required_document_missing；expert_support_present=False、expert_support_time=None、support_before_use=False、unmatched=[美罗培南]；公开证据仅synthetic-order，无万古霉素会诊引用。客户文案准确说明未找到可关联到该药计划的支持，不含别药07:00或晚于该时间，也不称启用前已找到目标药支持。

附加其他药06:00干扰的8节点真实观察均不借其时间，不带该文书引用，文案不带06:00；目录内普通药头孢曲松两节点也不冒充匿名支持。35条公开facts与native原值均相等，后续层未重判。全部模型调用/Token0，环境/数据库API/网络guard保持启用，SQL执行仅合成SQLite。

原多药半覆盖及新增正逆两文案保护实际 NC/required_document_missing；facts诚实保留已关联美罗培南07:00支持，未覆盖药物为万古霉素；文案“其中 万古霉素 未找到可关联的计划启用前专家支持记录”，没有错误晚于表述。多个具名全部成功准确说明逐项可关联支持，不以全局最早时间逐药推断；公共文书分别保留本来各自时间。单事件匿名C与多事件匿名DG保护仍通过。

三个SQLite新实例实际保存/回读状态、原因、facts、findings、suggestion，并校验customer-safe keyed source_ref集合、摘录/record_time/record_content与不漏raw ID；不同药NC不保存无关联会诊证据，关联支持C/晚于NC保留实际已关联引用。保存链由测试逐项断言通过，不据泛泛SQLite成功代替产品事实。

## 独审结论与限制

在原已确认TP-D04“已知不同药专家支持误绑”范围内，固定f2生产及0162测试跟进通过独立冻结复核，没有发现本轮新反例；可供root决定受限集成。原红18的2失败/16保护与冻结记录保留，预期未改。目录外未知药物身份/复杂语义不在这份关闭证明内，不能宣称任意药名已排除。TP-D05/N13六业务NC及两计数剩余均继续开放，本次不扩审或修复。
