# IML02 固定提交独立复核：轻量范围通过，可合入

固定提交 `0628782191861460bbf24edbf848eb601829876c`，工作树 `F:/MedQC-worktrees/qc-fix-critical-v2-20261008`。只读审阅5个生产文件及修复测试。未修改生产或原测试，未调用pytest、PG、.env、网络或模型。轻量测试槽已释放。

## 可追溯输入与输出

原冻结预期 `expected.json` SHA256：`d9041cbdcec154a7e98d3465c5425d2c958f32bbd05fdc87a240860dbf485eea`，15项×2规则共30条状态/原因核对，30/30符合。

补充事件键预期 `eventkey-expected.json` 在执行前独立冻结，SHA256：`1c4c49bd52d0abddb78ae5263ca98428f1f113754f2e3c5c1f15e548e803844a`；7项×2规则共14条，14/14符合。

执行脚本 `fixed_blob_probe.py`，结果 `fixed-062878219-results.json`。脚本用git show读取固定blob，stdlib AST加载原始纯函数；原生行解析→危急值判定→安全事实映射→精确Finalizer危急值分支→客户finding纯函数。每个读取文件的SHA256记录在结果中；无生产模块导入、数据库或fixtures。第一次私有探针接线错误地把内部事实直接交付公开Finalizer，立即被合同拒绝；改为原先既定的safe映射后再执行，未改冻结预期或生产代码。

## 已核对

- 空/缺失报告别名，即便record_time存在，仍为authoritative_time_missing；非法单字段、有效与非法组合及反向顺序均不回退或静默覆盖。
- 空白别名与唯一有效别名正常；Z与+08表示同一时刻不冲突，保持1小时正常处置；有效但不同时间的别名为authoritative_time_conflict。
- 非PL/PH项目不因时间冲突触发规则；not_applicable/trigger_absent_complete。此路径合法没有危急值展示事实，结果中的mapping_safe=False/status_contract_valid=False只是低层映射函数不接收空事实，不是交付失败；Finalizer返回None符合该路径。
- 独立A已确认未处置+B时间冲突、反向输入以及A明确7h超时+B冲突均保留A的non_compliant；052与053原因分别threshold_exceeded和required_document_missing。053对A已处置/B仍冲突保留data_gap。A正常不能代替B的冲突裁决。缺失报告时间也不掩盖独立已确认A缺陷。
- 正规test_id:A/B及匹配report_id关联正常；无键/未知键处置、同键时间歧义、无键项目及跨字段同值（report_id:A与test_id:A）不能因删除资料而伪造确定缺陷。052窗口未成熟保持data_gap；053按存在性合同不继承052的6h成熟窗。
- 公开冲突事实正确data_gap逐值保持；compliant冲突状态、额外原始report_time被拒绝。混合已确认缺陷+缺口摘要只接受non_compliant，不接受空/compliant/data_gap/technical_error；摘要内部event_key、report_time被拒绝。共13/13公开合同断言符合。
- 客户finding明确分开“已确认问题：合成血钾A”及“另有合成血钾B的报告时间字段冲突，暂无法核对”；单冲突不编造处置缺失或早于报告。合成证据引用保留实际项目行，A7h超时另保留处置行，不把horizon变成文书证据。

## 源码判断与限制

此前工作区patch的全局冲突优先级会遮蔽独立确定缺陷；固定提交已用 `_confirmed_independent_time_outcomes` 修正，且明确阻止无键/未知键处置、同键混合报告时间被错误拆分。没有发现本次范围新的阻断。

renderer混合结果建议分支已只读审阅，其建议要求整改确认问题，另列时间缺口先核查后重新评估，并明确“不得据此认定处置缺失”。本次执行覆盖finding纯函数，没有执行整个render函数及其suggestion分支；不能宣称独立验证native→Reducer→完整Finalizer/Renderer→存储链路，也不继承修复者pytest计数作为本次计数。全链路与存储应以root/修复者对应固定SHA的既有离线门禁证据为准。

本报告是固定SHA、纯合成的关闭复核，可支持IML02源码合入；没有当前真实模型复验。旧危急值合同4d5322c4a修复仍独立分列；本次关闭的是报告起算来源、别名冲突及其独立事件优先级。
