# SURGERY-029030 两条原正常材料：当前定向复核

两条未改原 C 冻结在当前真实执行器 → Binding/Reducer → Finalizer 均通过，当前无新增阻断。责任规则原生执行/映射仍固定 `e5f5696f559b4571b0d2a7d339d0d65485f8344b`；实际执行 HEAD `2f44aa44e86251acda81383e1b2bd84423008451`。共享 Finalizer/Renderer 已有 070 专属差分，固定 `35909964a36289d64a381301865b0a407e97184d`；完整 diff 与双版本 hash 明列于 manifest，不冒称共享文件仍 byte-identical e5f。当前129源超集在执行前核commit blob、执行后hash未变，实际app模块均来自目标树。

|原case / 原预期|当前逐层事实与证据|保留的问题|
|---|---|---|
|029_two_orders_two_summaries / C|native applicable/sufficient/satisfied → reduced C → Finalizer C，观察 reason=requirement_satisfied；facts=文书存在、目标presurg_summary、手术医嘱已确认。5个绑定fact_ref；证据精确含医嘱A/B及sumA(6/30 16:00)/sumB(7/2 16:00)原正文。|760旧固定C；未集成D候选gap/association_failed。候选仅取结构化名称或“手术名称/方式:”标签，普通“本次7月1日…术前小结”取不到名称。不是当前root回退；自由正文事件抽取需要批准语义合同，不能用标签控制替代原C。|
|030_orderB_own_record / C|native applicable/sufficient/satisfied → reduced C → Finalizer C，观察 reason=requirement_satisfied；facts=文书存在、目标surgery_record、已实施手术确认。1个绑定fact_ref；S3(7/3 12:00) record_content证据精确为原合成正文。|760旧固定C；未集成D候选gap/association_failed。候选对当前B医嘱/记录覆盖后，再要求MR A/B全病例事件关联，A无正式记录导致降gap，属候选范围问题。MR实际查询白名单没有application_id/document_id，合成注入A3不能证明adapter提供身份键；不能据此承诺简单安全关联修法。|

输入/预期复制自已公开 `next-triage/fixed-actuals.json` 与 `candidate-actuals.json`，两者rows及frozen_expectation逐值相同；未读取private原件。仅延用旧actuals.py的MR begin/end_datetime fromisoformat转换，其他键和值不改。原冻结只有C、没有reason oracle，观察到的reason不升格预期。冻结SHA：`1a4dfef87332d51b2a01dac408fbe39975fca0f465cff2e538d2076584d01332`。

run-04：exit0，2/2。模型calls/tokens=0；env/private/network/database/model/foreign_write guard计数全0。guard前只读commit blob核验及stdlib平台元数据缓存；guard后禁止全部subprocess、外部写、网络、真实DB驱动/SQLite。run-01/02/03各0案例，分别是Windows argv、executable与平台metadata/devnull的探针支撑失败，完整原日志保留，不能称首过。测试槽已释放。

仅合成row_reader；三个系统模块替身settings、database.connection、bundles.assembly明确披露，customer_rule_package仅AST静态定义。证据是Finalizer保存前customer_evidence的合成source ID，未验证HTTP、Store/API脱敏、真实适配器或实际病例，不作临床验收结论。

继承fad649错误MR fixture修复及354绿色，不重复记缺陷、不重跑354。旧负向“两个医嘱只有一个小结 / 当前B仅旧A记录”的事件覆盖仍待独立闭环，本轮未执行负向、不关闭该问题。两条正常gap旧线索应归未集成候选保护失败，而非当前root实测阻断。

产物：`original-rows-expected-v1.json`（未改原冻结）、`manifest-v1.json`（责任/超集/shared差分）、`prepared-runner-v4.py`、`observed-run-04.json`、`review-v1.json`、四次原日志；无生产编辑。
