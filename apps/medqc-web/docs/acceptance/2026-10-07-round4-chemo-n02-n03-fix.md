# 第四轮 N-02 / N-03 化疗边界修复记录

日期：2026-10-07。范围：LX0609-05-02-01。工程合成夹具，未调用真实模型或 PG；未修改目录 Prompt、判定合同或保存字段，未提交/重启。其他代理并发修改同文件的病理区，本记录只覆盖下面列明的局部修改。

## 修复与责任文件

- `backend/app/services/luxian_0609/native_tumor_pathology_execution.py`：仅 `_chemotherapy_dose_matches`。剂量数字不能从 d1 的字母后开始；ASCII 千分位整体读取，中文逗号按句读处理。d1，130mg、d1,130mg、体表面积1.7，130mg恢复一致；保留数字正负、小数、单位延续及分母边界，不做单位换算。
- `backend/app/services/luxian_0609/customer_renderer.py`：仅 `customer_finding_from_controlled_facts` 的可选 status 参数与化疗分支。未知字段明确写尚无法核对；同时存在不一致与未知时两者均展示；仅明确全部匹配的正常对照仍写全部一致。
- `backend/app/services/luxian_0609/canonical_result_finalizer.py`：该文案 helper 调用增加最终 status 参数一行，不修改归约/判定。
- `backend/tests/unit/test_round4_chemo_dose_and_findings.py`：新增9项合成工程测试，包含正式执行器→绑定归约→Finalizer，以及可保存 Envelope 签名合同/JSON往返校验。

## 红绿与正常对照

修改前专用红测试：5失败、1通过（3种前缀误拒绝；缺剂量/缺单位2种不实全部一致文案）。最终专用测试为8 passed、1 xfailed（strict=True；未关闭关联合同缺陷）。历史验证曾将现状technical_error断言计为通过，得到9项及既有剂量/出院33项合计42通过；该历史计数不代表关联缺陷关闭，现已改为严格xfail并保留正确data_gap预期。另运行已有 native tumor、tumor freeze、customer renderer、canonical finalizer 与既有33项，共650通过；15条既有依赖弃用警告。4个责任代码/测试文件 Ruff check 全通过。

正常对照保留130mg、130 mg、130mg d1/ivgtt/qd、整值千分位；1,130mg不能匹配130mg，负值、倍数、单位延续及分母边界拒绝仍由既有测试保护。缺剂量和缺单位正式终态data_gap，dose=unknown；剂量120mg且用药时间未知时正式终态data_gap，文案同时陈述剂量不一致和时间尚无法核对。正常130mg正式终态compliant及全部一致文案保持。保存验证是生产Envelope构造/一致性校验和JSON往返，不代表实际PG落库。

证据：`.tmp/0910-full-audit/semantic-next-preparation-private/round4-red-private.log`、`round4-first-green-private.log`、`round4-green-private.log`、`round4-regression-private.log`、`round4-final-xfail-private.log`。

## 独立未关闭工程问题：关联不唯一在Finalizer变技术错误

工程输入：一条2026-04-26奥沙利铂130mg静滴医嘱，两份同日期同剂量病程。执行器事实 `unresolved_event_count=1`，四字段均为初始matched，RuleDecision为data_gap/required_field_missing；绑定归约仍为data_gap。实际Finalizer返回technical_error/model_invalid_output且无findings。

原因：`tumor_pathology_result_mapping._safe_026`未保留unresolved_event_count，状态匹配合同仅允许全matched对应compliant。它在文案前拒绝当前data_gap输入。协调要求本轮不改该合同；专用正式测试保留raw facts与归约前置断言，Finalizer断言正确预期data_gap、reason与归约required_field_missing相同，并标记strict=True xfail。首次按data_gap期望执行该反例确实失败；最终专用测试8 passed、1 xfailed，未把技术错误固化为正常结果。

全matched+data_gap文案防线另有helper直接测试，仅证明展示函数不宣称已全部一致，不能替代上述正式链闭环，也不能作为真实模型/临床准确率。该未关闭问题需要后续独立确认关联事实的白名单与合同表达。本轮无真实样本新准确率结论。
