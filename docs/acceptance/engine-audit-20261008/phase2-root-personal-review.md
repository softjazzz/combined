# 主代理亲自复核：输血运行支撑与当前终态

日期：2026-10-09。用户要求主代理亲自检查后接手；子代理仍停止，原三次失败及计数不覆盖。此次为主代理一次接线修正及一次执行，不是生产修复，也没有重置子代理轮次。

## 亲自核实的接线问题

`source_evidence_reader.py`的`SnapshotSourceRows.create`明确要求`truncated`。原测试reader漏传，第三次26个TypeError均发生在业务判断之前。现有正式单元测试对完整合成来源明确传`truncated=False`。主代理此前审阅漏掉了这个必填参数，此处补正。

在新独占目录`.tmp/phase2-root-review/`制作副本：仅补完整合成来源`truncated=False`、日志序列化保持与case文件一致、支撑错误改非零退出；仍采用无I/O协程直接驱动，不创建Windows事件循环。保留26项原输入、原预期、时间、来源及所有业务函数，不修改生产实现，不按病例或文书ID改变结论。`TF1`仅为原合成证据身份。

原失败基线`4dbcd8e819f439c576262eebd1565f0eab0774e2`与本次运行HEAD `203fb819a`之间只有上批文档提交。执行前逐项验证原manifest全部app Python及data JSON源码hash仍相同；本次运行前后hash也相同，加载app均来自集成树。冻结原预期完全相等。

## 一次执行得到的当前结果

命令：`python .tmp/phase2-root-review/run_root.py`。产物目录：`.tmp/phase2-root-review/formal-direct-1791531081483531800/`。26项均走到native→binding/reducer→Finalizer，支撑错误0；真实模型调用0，人工模型客户端调用也为0。因此本轮误判不是人为模型答案造成的。

| 规则 | 组合数 | 符合冻结断言 | 不符 | 主代理检查结果 |
| --- | ---: | ---: | ---: | --- |
| 043 | 5 | 5 | 0 | 最终均DG。计划等场景的required_field_missing表明已进入下游；尚不能用这些样本证明终态错误，也不能凭DG宣布共享根因已修 |
| 044 | 5 | 1 | 4 | 计划、拒绝、延期、完整计划均错误NC/requirement_violated，事实称缺输血前评估 |
| 045 | 6 | 3 | 3 | 计划、延期、完整计划错误C/requirement_satisfied，performed_transfusion_confirmed=true、record_count=1；拒绝/取消DG及实际输注C正常 |
| 046 | 5 | 1 | 4 | 计划、拒绝、延期、完整计划错误NC，performed_transfusion_confirmed=true，错误进入已实施记录的字段缺项检查 |
| 047 | 5 | 5 | 0 | 最终均DG；与043相同，本批未证明错误终态，仍需保护共享门控改动的影响 |
| 合计 | 26 | 15 | 11 | 是规则×场景组合统计，不是规则通过率或完整验收数 |

043和047在四个错误门控场景的最终reason为required_field_missing，取消场景则为source_unavailable。状态同为DG不代表判定路径正确；本轮没有设置独立reason预期，不能把15项符合状态/事实断言升级为完整语义正确。

## 产品根因及修复范围

主代理直接读取当前`native_transfusion_execution.py`：

- `_dedicated_record_supports_performance`仅用有限否定正则排除后，直接以`len(content) >= 16`返回真。
- `_performed_source_state`将此真值认作present，使计划、拒绝、延期文本进入实际输血的后续判定。
- 045的`_is_substantive_transfusion_course_entry`继续按长度与临床信号共现判实质记录，未验证动作是否实际发生，因而计划中的成分/剂量也可得到C。
- 046在已有正文时进入字段检查，最终产生不该出现的NC；044进入实际输血后的评估要求判缺。

因此修复目标应是共同的实际实施事实与有效记录归属，而不是补几个计划/拒绝关键词，也不是改正文长度阈值。当前已证错误终态优先为044/045/046；043/047作为共享改动的关联保护。048的术中事件边界仍单列，不用住院其他输血事实替代。既有候选尚需按用户批准的新合同验证，不能凭本次复现直接集成。

## 结果与引用复核

主代理运行`verify_results.py`只读核对26份case产物：原输入/预期不变；native和reduced的fact_refs相等；reduced与final状态/reason相等；每份客户引用仍是原bloodtrans_record/TF1且引用正文逐字等于冻结输入。045错误C确实引用了“拟于明日输注……”的计划正文，引用能定位原文不代表结论正确。

该核对产物为同目录`root-verification.json`，包含每份case SHA256；运行manifest记录源码/runner/test/frozen/guard身份。未运行数据库、真实LLM、任务保存/API/页面/导出。无产品修复或新增缺陷关闭。此次结论补齐此前043–047缺失的限定工程终态观察，不抹去原三次支撑失败。
