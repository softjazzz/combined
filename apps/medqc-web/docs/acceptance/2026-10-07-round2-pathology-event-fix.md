# 第二轮病理跨事件误合规修复

基线 `57b863d2b328b2d93b004ffb6e49da55be76d804`。本轮仅修复 LX0609-06-02-02（取材记录）、LX0609-06-02-03（病理结果记录）的 typed 正式执行路径。没有提交、重启、真实模型调用或 PG 写入。

## 已修复行为

原实现将整次住院的任一取材记录、任一病理诊断词命中视为全规则合规。新增逐报告关联：明确同命名空间病理业务键/文书中的病理号，或唯一标本及对应诊断与时间共同建立关系。标本名冲突、重复事件不能区分、缺少记录时间、报告前的结果记录均保持 `data_gap / association_failed`，不升级为医生缺项。

唯一标本的取材事实必须与该标本出现在同一语句，不能借同篇另一检查的取材事实。结果记录必须不早于该报告；提交时间不替代记录时间。单事件语义兜底只接收已经关联的目标文书，多事件无法逐一证明时不采用全住院整体模型布尔结论。合规证据保留所有实际被覆盖的报告及各自支持文书，取材展示事实只列真正支持该事件的来源。

业务依据：`docs/0602/泸县0609质控点-业务标准基线-v1.md:80` 要求有对应结果记录，`:87` 要求病理报告事件与记录同次关联，无法关联返回资料不足。

## 红绿证据

新增 `backend/tests/unit/test_luxian_0609_pathology_event_association.py`。首次修复前运行：**3 failed、2 passed**；三个红例为第二报告未记录仍合规、报告前一个月的记录仍合规、其他标本的取材记录替代当前标本。两个正常单事件对照通过。

修复后补充同篇不同句、同标本重复诊断、记录时间缺失且只有提交时间、主表与报告标本冲突、正常多报告逐一记录、明确病理号区分重复诊断、公开来源与证据选择，共 **14 项通过**。新增边界均走正式 snapshot → native executor → binding/reducer → Finalizer，人工合成输入，未调用真实模型。

最终聚焦命令：

```text
PGOPTIONS=-c default_transaction_read_only=on
python -X utf8 -m pytest --confcutdir=tests/unit -p no:cacheprovider tests/unit/test_luxian_0609_pathology_event_association.py tests/unit/test_luxian_0609_pathology_report_gap.py tests/unit/test_luxian_0609_native_tumor_pathology_execution.py tests/unit/test_luxian_0609_tumor_pathology_freeze.py -q --disable-warnings --tb=short
```

结果：**145 passed，1 warning，2.26s**。四个变更 Python 文件的 `ruff check --no-cache` 通过。为保留已有正常路径、模型缺失/输出错误等保护测试的原目的，旧 typed 夹具补上了明确病理号与记录时间，原状态、证据、模型调用量及 Token 断言均保留；缺归属/缺时间行为由新增测试独立验证。未运行全量测试。

原审计脚本离线复验：三个原始反例现均为 `data_gap / association_failed`；两条正常结果仍 `compliant / requirement_satisfied`。此前已冻结的六例源行共12条病理判定仍为 `data_gap / required_field_missing`，最终诊断字段缺口未被掩盖。源行读取自私有 JSON，修复阶段没有再次查询 PG，也没有重新调用真实模型。最终输出保存于 `.tmp/0910-full-audit/round2-pathology-micro-private/pathology-formal-repro-after-private.json`。

## 范围及限制

- 生产变更只在 `native_tumor_pathology_execution.py` 的新增病理时间/关联助手、两条 typed 病理分支，以及 `_typed_decision_from_outcome` 中仅针对这两条规则的新原因码映射。并行肿瘤代理的化疗剂量、出院计划函数未修改。
- 保留原取材规则要求最终诊断/报告时间的前置门控。原019目录强调取材，但业务基线还含结果要求；本轮没有足够合同依据去删除该门控，仍列高置信度工程限制待业务确认。
- legacy 兼容路径保留原行为。培养两规则未改，亦未将此前培养旧测试计入本修复覆盖。
- 六例真实来源均因最终字段缺口先行退出，不能据此声称真实完整多报告关联已验收。本轮证明的是合成工程边界与既有保护合同，完整真实病理报告及标本关联仍需另补覆盖。
- 本轮对无法逐一关联的多事件采取资料不足；没有增加模型轮次来猜测归属，也没有扩大最终结果规则的文书来源合同。

变更测试：新增事件关联专项；局部更新 `test_luxian_0609_native_tumor_pathology_execution.py` 与 `test_luxian_0609_tumor_pathology_freeze.py` 的病理夹具。没有患者原文进入本记录。
