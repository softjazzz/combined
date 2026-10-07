# N-07 / N-11 化疗剂量与未比较事实修复

日期：2026-10-07；代码基线：1f9f7f703。仅 LX0609-05-02-01，工程合成夹具；0真实模型、0客户PG访问或写入，未提交、推送、重启。不作为临床人工结论或真实准确率。

## 最终方案与权威边界

N-11存在两种错误初始matched事实：关联不唯一时四字段未核对；完全无目标药候选时仅药名标mismatched，剂量/途径/时间却保留matched。最终方案由执行器完成逐事件比较后，将未比较事件造成的剩余matched汇总为unknown，保留已确认mismatched。汇总在循环后进行，避免顺序影响。

原unresolved_event_count不足以区分两种unknown原因：目标药未記载导致字段未比较（已确认缺陷），以及已比较事件缺有效时间（真实资料缺口）。因此增加两个受控整数：missing_course_event_count、unknown_time_event_count，均在实际事件分支计数，不能从展示文案反推。完整医嘱下只有缺目标药时保持non_compliant/requirement_violated；有真实关联不明或已比较时间未知时优先data_gap，沿用原执行器原因。已确认不一致与其他未比较字段同时展示，不伪造全部一致。

早先mapping-only允许全matched+count→data_gap的未提交方案已撤回。当前白名单拒绝正关联缺口携带任何matched，全未关联必须全unknown；全matched仍仅允许compliant。严格校验三种计数为真整数（拒绝bool/字符串/小数/负数），合计不超过正整数医嘱数；缺医嘱字段不能同时声明已执行关联/时间比较；缺目标药必须药名mismatched、不能携带matched，并必须显式提供实际时间未知计数；全部缺目标药时其他三项必须unknown。旧无计数事实按旧合同处理，不擅自补计数；私有字段仍剔除。

已通过严格校验的正关联缺口且无matched可为data_gap，保护“已知四项全mismatch + 另一未关联”组合；不为避免技术错误而丢弃已知不一致。发布/保存层只验证受控事实与执行器状态一致，不重新裁决。

N-07：一律拒绝剂量前字母造成L-OHP130mg、Oxaliplatin130mg、ivgtt130mg回退。现在只分隔d/D+数字+逗号日程前缀，再读取完整数值和单位，一般字母不阻断剂量。d1,130及中文逗号恢复，1,130不等于130、负数、小数、单位延续及分母保护保持，不做单位换算。

## 红绿与实际保存

- 原strict xfail使用`--runxfail`复现data_gap被Finalizer转technical_error。
- 第五轮新增6个红例：K01全未关联、K02已知剂量不一致+另未关联（两种顺序）、3个字母前缀，修复前全部失败。
- 收尾零目标药候选新增4个红例：缺目标药保持NC但其他字段应unknown；缺目标药+真实时间未知两种顺序应gap。先红后修，已移除临时strict xfail。
- K01四字段unknown；K02 dose=mismatched其余unknown。四项全mismatch+另未关联同时保留不一致及资料不足。单病程正常合规；缺目标药独立事件及与正常已比较事件混合保持NC；与时间未知混合保持gap，均覆盖顺序反转。
- 上述15个正式组合各自走快照→执行器→绑定归约→Finalizer→生产CanonicalResultStore.replace_for_job，实际写隔离SQLite并commit，关闭写Session，新Session通过生产load_selected回读。状态、理由、文案、完整customer_display_facts与保存前相等，不仅是Envelope构造。
- 新受控字段测试覆盖非法/负数/超范围/冲突计数、假matched、原因计数与字段冲突、NC/gap优先级，以及私有字段不泄漏。
- 最终9文件相关回归：859 passed、0 xfail（15条既有依赖警告）；4个责任代码/测试文件Ruff通过。覆盖native tumor、mapping、freeze、renderer、Finalizer、canonical delivery及剂量保护。此前32/818、41/827、41+1xfail、853 passed为中途历史，不作为最终验收数。

收尾顺序保护：零目标药候选、已比较时间未知、已比较时间不一致三事件的6种排列，修复前3失败/3通过。原因是后续unknown覆盖既有time=mismatched。仅将时间字段汇总改为mismatched优先，unknown_time_event_count仍按真实未知事件累加并决定gap；修复后6排列均保留药名/时间不一致、计数missing_course=1/unknown_time=1/unresolved=0、data_gap/source_unavailable，且生产SQLite新Session回读相等。最终859通过包含这些6项，不扩大其他范围。

## 精确交付文件

1. `backend/app/services/luxian_0609/native_tumor_pathology_execution.py`：仅剂量matcher与026比较汇总/原因计数段。
2. `backend/app/services/luxian_0609/tumor_pathology_result_mapping.py`：仅026事实白名单与状态一致性校验。
3. `backend/tests/unit/test_round4_chemo_dose_and_findings.py`：26项正式链/正常对照，其中15个组合实际SQLite新Session回读。
4. `backend/tests/unit/test_026_association_contract.py`：46项受控事实保护及保存辅助函数。
5. `docs/acceptance/2026-10-07-026-association-contract-fix.md`：本记录。

没有修改病理、074、Renderer、Finalizer、目录、Prompt或他人文件。历史第四轮未关闭记录保留，最终状态以本轮证据为准。

私有证据位于`.tmp/0910-full-audit/semantic-next-preparation-private/`：`026-contract-red.log`、`n07-n11-red.log`、`n11-missing-red.log`、`n11-missing-green.log`、`n11-complete-regression.log`、`n11-time-precedence-red.log`、`n11-time-precedence-final.log`。其余中途green/xfail日志是历史，不混作最终结论。

## 限制

第五轮0910源统计化疗医嘱为0；本轮没有真实化疗病例准确率结论，没有扩展多疗程临床关联判据。无目标候选是当前执行器已确认的药名缺陷口径，本轮保留其终态，纠正其余未核对字段及跨层合同。客户PG、线上任务/UI未验收，不声称已部署。
