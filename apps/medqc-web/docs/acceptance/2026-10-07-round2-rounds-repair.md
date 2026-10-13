# 2026-10-07 第二批查房008/009修复

基线HEAD：`57b863d2b328b2d93b004ffb6e49da55be76d804`。只修复独立审查确认的两个合成缺陷，不引用失效真实预期作验收结论。

## 改动

- `backend/app/services/luxian_0609/course_quality/rules_008_009.py`：008复用现有正文/模板壳校验，只有有效正文的病程才能贡献日期。008/009医嘱按完整权威本地时间排序并配对开始/解除，配对后才转为自然日；同时校验停止时间不早于开始时间。既有自然日覆盖口径不变。
- `backend/tests/unit/test_luxian_0609_round2_severity_regressions.py`：新增9项脱敏测试，经正式快照、执行器、Binding/Reducer、Finalizer检查最终状态；复用既有纯合成会话助手，不修改原测试。
- 未修改共享Renderer、合同、来源读取器或业务状态后处理。无提交、stash、reset、重启、真实模型调用或PG写入。

## 红绿证据

命令在backend运行：

```powershell
python -m pytest tests/unit/test_luxian_0609_round2_severity_regressions.py -q --disable-warnings
```

修复前 **4 failed / 5 passed**：空正文、待补充模板壳、病重同日重开、病危同日重开四项均实际返回compliant而预期non_compliant。正常非空病程、跨日重开、解除后未重开的五项对照通过。修复后 **9 passed**。

聚焦已有执行器及新测试：

```powershell
python -m pytest tests/unit/test_luxian_0609_native_course_quality_execution.py tests/unit/test_luxian_0609_round2_severity_regressions.py -q --disable-warnings
python -m ruff check app/services/luxian_0609/course_quality/rules_008_009.py tests/unit/test_luxian_0609_round2_severity_regressions.py
```

结果 **233 passed**，15项既有依赖弃用告警；Ruff **All checks passed**。没有扩大运行全量测试。

## 原反例回放

无PG、无模型的原私有合成回放12场景13裁决也已重跑：

| 合成反例                                             | 修复前Finalizer      | 修复后Finalizer                                                    |
| ---------------------------------------------------- | -------------------- | ------------------------------------------------------------------ |
| 病重1/1–1/7，仅1/1、1/3、1/5、1/7空正文壳            | compliant            | non_compliant / threshold_exceeded                                 |
| 病重1/1 08:00开始、10:00解除、15:00重开，仅1/1有病程 | compliant            | non_compliant / threshold_exceeded                                 |
| 同上病危                                             | compliant，误称仅1天 | non_compliant / requirement_violated，正确为1/1–1/7七天，缺1/2–1/7 |

正常非空病程仍合规；无病程和跨日重开仍不合规；005的48小时边界/无时间、006恰好72小时及原先资料不足输出保持原状。回放不触发模型，新增测试显式断言llm_call_count=0。

## 范围与限制

未重跑真实病例或PG保存链。前审查C04阴性预期失效、提交时间兜底与007来源不足等限制仍保留，不把该批真实观察升格为验证通过。仅证明这两个合成确定性缺陷在本地正式执行和Finalizer路径修复；未声称临床验收、服务已更新或上线。

本次修复使用diagnosing-bugs流程。CodeGraph本次成功，另已读AGENTS与CONTEXT。根因分别是008未使用正文门控、生命周期事件在排序前丢失时分秒；Finalizer保持了执行器裁决，不是根因。新增跨最终客户结果的反例测试可防止同类回退，无需新增共享架构。
