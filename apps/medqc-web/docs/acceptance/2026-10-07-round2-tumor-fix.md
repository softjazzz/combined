# 肿瘤026/027边界修复记录（2026-10-07）

已修复第二轮审计确认的两项工程漏报。修复起点为 `57b863d2b328b2d93b004ffb6e49da55be76d804`；此前审计基线为 `c3a87a4f820259bca37a01764522ea1f3f485a3c`。本轮未修改客户规则定义、共享Renderer或合同，未运行真实模型、未写PG、未重启或提交。

## 改动

- 026：新增 `_chemotherapy_dose_matches`，使用Decimal比较完整数值，保留正负号和小数点，要求原单位完整匹配。130mg不再匹配1130mg、13.0mg、-130mg或130mg/m²；130.0mg和+130mg与130mg保持数值一致。未加入医学单位换算。药名、用法、时间以及多事件关联逻辑保持原路径。
- 027：新增 `_is_future_discharge_treatment_clause`。当治疗词处于“入院后、住院期间、既往、已完成”等明确历史语境时，“继续/建议”不再单独证明出院后计划；后续明确“出院后/后续”等时间范围可重新建立计划语境。沿用已有否定、待定计划约束。
- 新测试 `backend/tests/unit/test_round2_tumor_dose_discharge_boundaries.py` 直接通过正式材料会话、原生执行器、绑定归约和canonical finalizer验证状态及公开事实。禁止模型客户端一旦被调用即失败。

## 红绿验证

首次运行新增14项边界测试：**8失败、6通过**。明确复现130/1130子串、13.0小数点丢失、负号丢失、单位分母丢失和历史化疗误作未来计划；同时发现130.0mg与130mg错误不一致。

最小修复后14项新测试与111项既有肿瘤执行器测试：**125通过**。补充5项正负小数数值保护后，同一聚焦范围为 **130通过**，Ruff检查执行器与新测试均通过。未运行全量测试。

运行命令：

```text
python -m pytest backend/tests/unit/test_round2_tumor_dose_discharge_boundaries.py backend/tests/unit/test_luxian_0609_native_tumor_pathology_execution.py -q --tb=short
python -m ruff check backend/tests/unit/test_round2_tumor_dose_discharge_boundaries.py backend/app/services/luxian_0609/native_tumor_pathology_execution.py
```

原始冻结四例再回放：

| 用例            | 修复前    | 修复后        | 正常对照/反例       |
| --------------- | --------- | ------------- | ------------------- |
| dose_control    | compliant | compliant     | 130mg一致           |
| dose_substring  | compliant | non_compliant | 130mg与1130mg不一致 |
| future_control  | compliant | compliant     | 明确出院后继续化疗  |
| historical_only | compliant | non_compliant | 仅住院已实施化疗    |

全部正式执行结果模型调用量为0。最终公开剂量事实及肿瘤治疗计划事实与状态一致。原始审计反例使用Git只读导出的c3基线模块再次离线执行，结果SHA-256与审计时保存的原始哈希完全一致；修复后结果单独保存，没有改变冻结预期。

## 范围与未解决项

本次只修复已证明的数值边界和明确历史时间语境。未扩展药品别名归一、单位换算、复杂自然语言计划抽取或新的临床治疗计划定义。既有多药/多事件、否定/待定治疗等测试随聚焦文件通过；不能声称所有多疗程或全部语义边界已验收。024未改，真实适用例不足的限制继续见审计报告。

没有开展真实模型或客户PG新任务验证，不声称真实病例全部通过或已上线。0910患者源记录仍仅在私有目录。测试中的负剂量仅用于验证符号保真，不表示临床用药合理性。

私有产物位于 `.tmp/0910-full-audit/round2-tumor-private/`：`fix-green-private.log`、`engineering-results-fixed-private.json`、`run_engineering_fixed_private.py`，原冻结与基线输出保留。该目录文件不提交。

并发病理代理负责同文件其他病理函数；本代理只修改Decimal导入、026剂量助手/比较点、027未来语境助手/调用点，不回退其他代理改动。主协调须对共享文件最终diff独立复核。

## 独立交叉复核后的Unicode单位边界补修

主协调提出130mg医嘱与130mg／m²、130mg·m⁻²仍会错误合规。先增加两个正式执行至最终输出反例，结果2失败；随后只扩展单位后缀边界的Unicode斜线、分数斜线及乘点字符，不做单位换算。新增肿瘤测试整体21通过，Ruff通过。补修未触碰并发病理函数或共享合同。红绿日志为私有目录的 `unicode-red-private.log`、`unicode-green-private.log`。
