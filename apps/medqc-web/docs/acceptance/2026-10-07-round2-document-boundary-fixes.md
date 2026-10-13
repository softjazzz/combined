# 第二轮文书边界四类修复验证

日期：2026-10-07。修复起点HEAD：`57b863d2b328b2d93b004ffb6e49da55be76d804`。原审计基线为 `c3a87a4f820259bca37a01764522ea1f3f485a3c`。本轮在共享D盘工作区局部修改，保留其他代理改动；没有提交、推送、重启、模型调用或PG写入。

## 结果

已修复四类经正式链确认的问题：

| 规则与边界                                 | 修前                                      | 修后                                  |
| ------------------------------------------ | ----------------------------------------- | ------------------------------------- |
| 037 麻醉访视只有空字段标题                 | compliant                                 | non_compliant / requirement_violated  |
| 037 麻醉/术前事件A与术后事件B拼接          | compliant                                 | data_gap / association_failed         |
| 065 既存上级查房无权威时间，72小时窗口成熟 | non_compliant / required_document_missing | data_gap / authoritative_time_missing |
| 067 出院前窗口内病程仅有带姓名签名         | compliant                                 | data_gap / required_field_missing     |

037非法时间补充探针也由compliant改为non_compliant。正常完整访视、有效阴性描述、术后一天有效上级查房、实质出院前病程均保持compliant。

## 最小变更与所有权

- `native_surgery_document_execution.py`：只在访视完整性中排除纯标题；记录时间复用已有合法分钟级时间解析；按同名 `application_id/anesthesia_id/surgery_id` 检查麻醉、术前、术后的明确冲突。跨来源不同document_id不作为冲突，无业务键单事件的既有兼容控制保留。
- `native_extended_document_execution.py`：只改065分支，未能满足窗口时保留既存无时间查房，绑定该记录为证据并返回data_gap；已有有效时间的合格查房不会被另一份无时间记录阻断。复用 `postoperative_senior_round_window_unavailable` 现有受控事实，不新增合同或Renderer分支。
- `extended_document/discharge_course.py`：在原有空正文/纯签名标签排除上识别带姓名、职称的签名行；多行纯签名仍为缺正文，含临床短句的正文保持有效。
- 独立新增 `backend/tests/unit/test_luxian_0609_round2_document_boundaries.py`，不改共享旧测试文件。

已与抗菌药和疑难病例代理协调同一个扩展执行器的局部区块所有权；本记录不认领其变更。

## 红绿与保护集

首先运行新测试文件：**9失败、8通过**，失败症状分别覆盖空标题、非法时间、三种业务键跨事件、无时间/非法时间查房、两种带姓名签名。065夹具显式保存评价时点，修正过初次测试接线错误后才记录这组红结果。

修复后17项转绿，另补多行纯签名控制，最终新测试 **18项通过**。扩展保护曾暴露2个067回退（空格分隔标签、签名标签后临床短句），已收窄签名匹配并重新验证；未修改既有测试预期。

最终以下9个聚焦文件共 **654项通过**（7.44秒），15个既有依赖弃用/命名警告，没有失败：

```text
python -m pytest
  backend/tests/unit/test_luxian_0609_round2_document_boundaries.py
  backend/tests/unit/test_luxian_0609_native_surgery_document_execution.py
  backend/tests/unit/test_luxian_0609_native_extended_document_execution.py
  backend/tests/unit/test_luxian_0609_postop_audit_regressions.py
  backend/tests/unit/test_luxian_0609_predischarge_course_body.py
  backend/tests/unit/test_luxian_0609_postoperative_result_mapping.py
  backend/tests/unit/test_luxian_0609_surgery_document_result_mapping.py
  backend/tests/unit/test_luxian_0609_surgery_document_precise_fact_refs.py
  backend/tests/unit/test_luxian_0609_surgery_record_event_coverage_regression.py
  -q --tb=short --disable-warnings
```

命令展示换行为便于阅读，实际同一次pytest调用。3个源码文件和新增测试文件的Ruff检查通过。未运行全量前后端测试。

## 原审计回放与实际限制

保留原始冻结预期和原始结果；修后输出另存 `.tmp/0910-full-audit/round2-surgery-documents-private/afterfix-*`。

- 手术文书6例×5条的30个Finalizer结果逐项完全相等，含状态、原因、受控事实及公开证据。
- 出院术后6例×5条的30个原审计回放结果逐项相等，含状态、原因、公开事实和调用量。
- 原始合成反例及正常对照按同输入复跑，得到上表结果；全部真实/合成回放模型调用与Token均为0。
- 汇总：`afterfix-validation-private.json`；手术文书：`afterfix-results-private.json`；出院术后：`afterfix-dp-engineering-results-private.json`、`afterfix-dp-real-replay-results-private.json`。

真实资料覆盖限制仍然有效：本地麻醉访视表无行不证明临床缺失；真实术后材料缺少手术结束时间的门禁仍保留。没有将合成反例当真实病例错误或批准上线。

## 065纯签名查房补充闭环

协调方随后明确要求一并修复已确认的065纯签名查房错误。补充只修改065分支，复用067已有的正文存在检查；没有修改共享 `_course_row_has_body`（其还服务064三日覆盖），没有引入临床充分性判定。窗口内仅空正文、纯签名标签、带姓名/职称签名或缺少record_content键，均为data_gap/required_field_missing，并绑定该既存文书；已有有效查房不会被同窗口的纯签名行阻断。没有把正文缺口输出成“未查到上级查房”。

补充红测试8项：4失败、4正常控制通过；父复核指出缺正文键兼容分支仍可放行后，追加第9项缺key红测试并移除该生产兼容。最终独立新文件共 **27项通过**。正常短句、“医生签名:继续观察。”及正文后附签名均保持合格。

五个旧正常控制测试原来仅提供查房时间、标题、作者，现仅给其14条senior_course_record输入补充实质正文；AST核对全部原状态、原因及事实断言未变。新增改动的旧测试文件只有：`backend/tests/unit/test_luxian_0609_native_extended_document_execution.py`。所涉函数为：

- `test_065_binds_surgery_senior_round_and_evaluation_horizon_sources`
- `test_064_065_count_formal_surgery_records_as_distinct_events_not_mr_rows`
- `test_065_multievent_compatible_summary_reaches_customer_conclusion`
- `test_065_partial_multievent_delivery_summarizes_unmet_count`
- `test_065_does_not_allow_one_surgery_senior_round_to_cover_another`

最终补修保护为独立新测试、native_extended、postop_audit_regressions、predischarge_course_body、postoperative_result_mapping共 **504项通过**（11.99秒），源码及两测试文件Ruff通过。前述654项为此前四类修复的验证记录，不冒称为新增补修后的计数。原审计065_signature_only回放已变为data_gap/required_field_missing、模型调用0，正常065/067保持合格。文件冻结交由协调方统一复核提交，未提交、重启或写PG。
