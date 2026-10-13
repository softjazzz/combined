# CT-02 独立预期冻结 v1

固定基线 bb3d0b5c3762ea7a0c8aa0580af8ec666794347b；owner树 F:/MedQC-worktrees/qc-fix-critical-v2-20261008。仅050/LX0609-03-02-01候选病程时间缺失误判NA，CT-01词命中、CT-03空白讨论及CT-R02提前讨论关联均不在本修。0916排除。

来源：原course-timing报告与原expected.json（只读、不覆盖）；owner树 apps/medqc-web/docs/acceptance/2026-10-08-course-timing-minimal-closure-design.md。未读取owner新测试。独立预期expected-v1.json冻结28组输入与判定，以及公开状态/证据文案约束，尚未执行任何测试。

缺时或不可解析的既有诊断候选应data_gap/authoritative_time_missing；有讨论行不能证明未知候选已满七天。另一行已定位成熟强候选缺讨论时NC仍NC，两种行序均须一致；成熟C允许安全缺口摘要，不能声明未知候选也已完成核对。正常七天秒界限、四正式时间别名、同一时刻UTC与+08表达、局部scope_uncertain、无候选和源/入院错误优先保持原行为。

新公开kind独立冻结为uncertain_diagnosis_course_time_gap（设计示例名）；仅可配data_gap，正整数缺时候选数排除bool，讨论数为非负整数；非法状态、未知kind及伪造/污染资料不得通过公开读回。若owner在实施前另选名称，需root明确记录命名映射，仅名称映射不改变语义与状态预期。旧C/NC/NA/局部uncertain没有新摘要时逐值兼容，非050与RR-PUB冻结不动。

证据仅用实际消费的合法文书/来源引用；无文书ID只用既有source/snapshot锚，不补造ID、时间或正文。公开facts不含原文或内部文书ID。gap文案应解释权威病程时间未能定位七天窗并要求核对源时间/同步，不能说完整资料未触发或催补已存在讨论。纯gap须贯通native→Binding→Finalizer→Renderer→新实例合成Store回读；此次只冻结预期，未声称这些链已通过。

执行边界：只读生产，不改owner测试，不运行测试，不读.env、PG、原始患者或真实模型。等待固定修复commit和root测试槽后再独审。当前准备不能用于关闭CT-02，更不能关闭CT-01/CT-03。
时点限制：预期写入完成后的只读git status显示owner四生产文件已修改；本审未读其diff或新测试。预期独立来自bb3基线与设计，不声称其冻结早于owner实际开始修改。
