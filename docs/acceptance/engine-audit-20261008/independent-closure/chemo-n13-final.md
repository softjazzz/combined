# N13 59b3 最终候选独立复核

固定目标 `59b3d7cbc83ee5d3de946f08409d04fc9357dc57`，实际父 `e8f7dcb746a413d7736986535939f00d1573dad3`；本轮回归对照基线为已交付 `e256e8ea926f0bcb19cb000cd826dd781e157eaf`（D01已包含、N13未包含），不能将未交付e8误记为业务基线。当前仅静态准备，尚未运行。

相对e8生产差异只删除clinical_dates函数与owner中日期排除；所有医嘱竞争归属及不同药排除仍在。无新增词表，未改剂量算法、公开mapping/count合同。相同药或缺药名竞争事件不能用正文日期排除，因此原同药同日与无关复查日期风险预计退回保守gap；运行前不声称通过。

复用三个原冻结oracle，均不修改。四项复查日期反例×正逆序共8观察，应消除错误NC；保护不同药独立真缺病程/120vs130的NC、不假matched、缺名/日期、文书/提交时间歧义以及N01/N07剂量反例。

三项原明确给药日期NC业务期望×正逆序共6观察（different_day_explicit_mismatch、different_day_relative_mismatch、partial_missing_name_different_day_explicit）仍为NC。若e256和最终均输出gap，会记录为尚未达到业务能力，不能改gap称通过或全关N13。另different_day_explicit_matched原冻结DG并指定unresolved_count=0，若最终count变化也保留差异原貌。

计划方法：单stdlib Python，git show真实函数AST及SourceMaterial形状替身、真实纯public mapping；比较e256和最终，固定确认目标实际父e8。不执行pytest/全工程/PG/模型/.env。无正式native-bind-Finalizer或SQLite/保存验证，开发通过数不算独立证据。等待root测试槽。
## 独立轻量执行结果

固定源码AST单Python验证已完成。汇总：{"target_event_observations": 47, "target_event_matches": 39, "target_contract_observations": 20, "target_contract_matches": 20, "n01_n07_both_versions": 14, "n01_n07_matches": 14}。

未符合冻结预期的目标观察：[{"case_id": "different_day_explicit_mismatch", "order_variant": 0, "expected": "non_compliant", "observed": "data_gap", "facts": {"verification_kind": "chemotherapy_order_course_comparison", "order_count": 2, "field_results": {"drug_name": "unknown", "dose": "unknown", "route": "unknown", "time": "unknown"}, "missing_order_fields": ["dose"], "missing_order_event_count": 1, "unresolved_event_count": 1, "missing_course_event_count": 0, "unknown_time_event_count": 0}}, {"case_id": "different_day_explicit_mismatch", "order_variant": 1, "expected": "non_compliant", "observed": "data_gap", "facts": {"verification_kind": "chemotherapy_order_course_comparison", "order_count": 2, "field_results": {"drug_name": "unknown", "dose": "unknown", "route": "unknown", "time": "unknown"}, "missing_order_fields": ["dose"], "missing_order_event_count": 1, "unresolved_event_count": 1, "missing_course_event_count": 0, "unknown_time_event_count": 0}}, {"case_id": "different_day_explicit_matched", "order_variant": 0, "expected": "data_gap", "observed": "data_gap", "facts": {"verification_kind": "chemotherapy_order_course_comparison", "order_count": 2, "field_results": {"drug_name": "unknown", "dose": "unknown", "route": "unknown", "time": "unknown"}, "missing_order_fields": ["dose"], "missing_order_event_count": 1, "unresolved_event_count": 1, "missing_course_event_count": 0, "unknown_time_event_count": 0}}, {"case_id": "different_day_explicit_matched", "order_variant": 1, "expected": "data_gap", "observed": "data_gap", "facts": {"verification_kind": "chemotherapy_order_course_comparison", "order_count": 2, "field_results": {"drug_name": "unknown", "dose": "unknown", "route": "unknown", "time": "unknown"}, "missing_order_fields": ["dose"], "missing_order_event_count": 1, "unresolved_event_count": 1, "missing_course_event_count": 0, "unknown_time_event_count": 0}}, {"case_id": "different_day_relative_mismatch", "order_variant": 0, "expected": "non_compliant", "observed": "data_gap", "facts": {"verification_kind": "chemotherapy_order_course_comparison", "order_count": 2, "field_results": {"drug_name": "unknown", "dose": "unknown", "route": "unknown", "time": "unknown"}, "missing_order_fields": ["dose"], "missing_order_event_count": 1, "unresolved_event_count": 1, "missing_course_event_count": 0, "unknown_time_event_count": 0}}, {"case_id": "different_day_relative_mismatch", "order_variant": 1, "expected": "non_compliant", "observed": "data_gap", "facts": {"verification_kind": "chemotherapy_order_course_comparison", "order_count": 2, "field_results": {"drug_name": "unknown", "dose": "unknown", "route": "unknown", "time": "unknown"}, "missing_order_fields": ["dose"], "missing_order_event_count": 1, "unresolved_event_count": 1, "missing_course_event_count": 0, "unknown_time_event_count": 0}}, {"case_id": "partial_missing_name_different_day_explicit", "order_variant": 0, "expected": "non_compliant", "observed": "data_gap", "facts": {"verification_kind": "chemotherapy_order_course_comparison", "order_count": 2, "field_results": {"drug_name": "unknown", "dose": "unknown", "route": "unknown", "time": "unknown"}, "missing_order_fields": ["dose", "drug_name"], "missing_order_event_count": 1, "unresolved_event_count": 1, "missing_course_event_count": 0, "unknown_time_event_count": 0}}, {"case_id": "partial_missing_name_different_day_explicit", "order_variant": 1, "expected": "non_compliant", "observed": "data_gap", "facts": {"verification_kind": "chemotherapy_order_course_comparison", "order_count": 2, "field_results": {"drug_name": "unknown", "dose": "unknown", "route": "unknown", "time": "unknown"}, "missing_order_fields": ["dose", "drug_name"], "missing_order_event_count": 1, "unresolved_event_count": 1, "missing_course_event_count": 0, "unknown_time_event_count": 0}}]

比较器及真实公开sanitize/status合同层级；没有完整正式链或保存验证。独立结果SHA-256：`d08351bc0734a063c4ebbeb3aecbdfe7272537f188a17828c8e68b5ce1d13516`。方法、固定源码hash与全部观察见results-final-independent.json。

## 最终分类与有限继承结论

独立固定blob执行完成，目标47观察中39完整符合原冻结期望，8项未达如实保留。可以继承“不虚报matched、独立已确认NC保留、竞争事件不能借无关日期排除”的有限正确性修复；不能全关N13或称47通过。三个原oracle未改；冻结、脚本和结果hash见 hashes-final-independent.json。

| 核对范围 | 结果 | 验收解释 |
| --- | --- | --- |
| 四项无关复查日期用例×正逆序 | 8/8最终DG、全unknown、unresolved1 | 中间e8的错误NC消除；未凭复查日期虚造給药归属 |
| 同药同日完整+partial | 正逆序均DG | 已修歧义保护保留 |
| 不同药独立120vs130/真缺病程+partial | 正逆序均NC | 不因缺字段吞掉已确认缺陷，不把所有partial blanket gap |
| 明确日期原NC三用例×正逆序 | 6/6仍实际DG | 原期望NC不改，e256和最终状态均gap，记业务能力未达；不能计通过 |
| different_day_explicit_matched×正逆序 | 状态DG符合；unresolved期望0实际1 | 另2项计数预期差异，未计完整通过 |
| 公开合同目标 | 20/20 | 新计数范围/bool/总和/状态及老facts兼容保护 |
| N01/N07交付基线/最终 | 14/14 | 剂量正常与反例保护未扩算法 |

六项能力未达来自 different_day_explicit_mismatch、different_day_relative_mismatch、partial_missing_name_different_day_explicit 各两医嘱顺序。e256因缺字段整段退gap且有false matched残留；最终所有字段unknown、missing_order_event_count1、unresolved1。两版实际gap不等于达到NC业务要求，也不是相对已交付e256的新状态回退。未交付中间e8此前将这6项判NC，但存在跨事项日期错误排除，不能把它当已验收基线。

额外两项计数差异：different_day_explicit_matched冻结状态DG、unresolved0；最终状态仍DG但unresolved1。保守未归属的计数区别已保留，不悄悄修改期望、也不据此称两项全通过。

正式链/native bind/Finalizer、SQLite/保存、真实gold及模型/PG未独立执行。单短进程已退出并即刻释放槽给root67，归档期间未启动更多范围。

独立结果SHA-256 `d08351bc0734a063c4ebbeb3aecbdfe7272537f188a17828c8e68b5ce1d13516`；目标源SHA-256 `3e2299951c92f9835da0787f8c24fc5ef49b51a39b350429d654351411890264`。最终机器结论见 verdict-final.json。
## root 集成决策所需明确结论

本次冻结47项观察内，未发现相对已交付e256新增的确认误判阻断；支持仅有限工程子项净差分集成，N13总体仍开放。独立不同药NC、不假matched及8项错误归属保护符合；6项原NC业务能力未达在e256和最终均gap。

另2项unresolved计数0→1：当前实现撤除不可靠日期推断，尚未建立目标给药日期与医嘱的绑定，因此同药partial仍是竞争事件。计数1准确表达当前实现未证明独立归属的技术缺口；不能以此推翻原业务期望0。仍保留冻结差异并归日期归属能力未达，不强改答案、不计完整通过。未证明归属是当前引擎能力描述，不能据此宣称明确正文日期永远不够或改业务政策。

“没有新增确认误判阻断”仅覆盖此次固定blob AST冻结矩阵，不关闭既有其他剂量/语义审计问题，也不替代真实gold/正式全链/保存验收。