# 会诊意见逐项处置书写质控

> 2026-10-16：继续修复 C08 本科室拟加药句被重列为会诊建议的问题，三轮真实逐项复验通过。当前提示版本 v4，另保留一次保护性验证的模型格式失败。详见[最新修复记录](2026-10-16-consultation-disposition-role-fix.md)。

> 最新：首轮真实资料发现的三项核心问题已修复，同集 30 例和关键 6 例完成真实复验，相关后端 639 项通过。保留 C08 一处角色归属边界（不阻断）；尚未重启或打包。当前两阶段协议与准确性限制以[修复与复验记录](2026-10-15-consultation-disposition-fixes.md)为准；下文保留最初实现及验证历史。

## 已确认的业务范围

新增 `LX0609-03-01-05`「会诊处置记录：未逐项具体说明会诊意见的处置情况」。客户确认同一次会诊须逐条检查；只具体写了用药，其余建议笼统写遵嘱，仍报记录不具体。

本点从会诊执行记录正文内引用的意见取建议，不要求另有原始会诊单。检查的是本科室如何书面记载处置，与 `03-01-04` 检查医嘱、记录等实际执行证据分开。一项可有执行医嘱，同时处置书写仍不具体。

- 仅「遵照执行」「以上已遵嘱」「其余遵嘱执行」不算具体处置。
- 明确写了具体处理、具体检查安排，可算书写具体；安排不代表已经实际执行。
- 明确写了不采纳或暂缓的项目及原因，可算具体处置；患者拒绝本身可作为原因。
- 「继续上述药物治疗」只有在同份正文指代明确时可计入。
- 意见没有提供、归属不清、抽取无法核实，判资料不足；不凭资料缺口报临床缺陷。

规范依据：[《病历书写基本规范》第二十二条（十）](https://www.nhc.gov.cn/wjw/c100175/201002/b1bec53d90f243e0861529723f00221a.shtml)要求申请会诊医师在病程记录中记录会诊意见执行情况；[《医疗质量安全核心制度要点》会诊制度](https://www.nhc.gov.cn/yzygj/c100068/201804/42ab2552298047679cd6ec733f233862.shtml)要求会诊意见的处置情况在病程中记录。逐项具体、笼统遵嘱不算等细化判据来自本轮客户确认，不冒充规范原文，也不新增统一反馈时限。

## 本机资料观察

以只读事务读取本机 `cdm.consultation_record` 802 行，按正文去空白精确去重为 664 段文本。库中含演示、测试材料，该数字不代表独立患者或会诊次数，不据此计算缺陷率。

观察到的常见写法包括：先复述专科建议再写笼统遵嘱；具体停药、加药；约定次日检查；有理由地暂缓检查；明确回指上述药物。建议与反馈常混在同一段，不能仅搜索治疗动作或「执行」二字。原始排查材料留在 `.tmp/0910-full-audit/20261015-consultation-disposition-audit-private/`，不提交、不展示到客户事实、不发送真实模型。

## 实现边界

`consultation_disposition_record.py` 独立拥有新点判定。旧会诊执行器保留原逻辑，入口仅分派新点并汇总结果；新点只读 `consultation_record`，不读取医嘱或后续病程。

最多两次模型调用，不再叠加协议修复重试：

1. 独立提取正文内会诊建议清单，要求行动核心为连续原话；检查、用药等独立措施分别列出，部位、穴位、目的不单列。
2. 按固定清单编号，逐项返回本科室反馈类别和完整原话。程序核对编号完整且不重复、引文在同份正文中、笼统遵嘱不被模型的具体处置标签放过。

第二步不重复输出建议原话，也不再重复摘录一个动作字段，避免模型扩写建议、重组并列动作造成无谓校验失败。共用原因和并列反馈可逐项引用同一连续整句。清单漏答、协议错误或无法关联均返回 `data_gap / semantic_extraction_unresolved`；不沿用合规，不判未执行。

结果只绑定来源材料引用，Renderer 生成受控的独立书写质量说明，不把模型引文写入客户事实。规则目录、客户规则包、typed decision 证据绑定和判定说明均已接入；没有改动旧点的启停状态。

## 验证记录

最终实现的后端定向回归 **580 项通过**，覆盖新增点、旧会诊执行、逐措施核对、原生派发、目录、合同、证据绑定、客户投影及最终结果校验。新增点自身 27 项，包括漏答、重复编号、来源引文、并列暂缓原因、来源引用异常不崩溃，以及不读取医嘱的执行器测试。

运行目录 `apps/medqc-web/backend`：

```powershell
py -3.10 -m pytest tests/unit/test_luxian_0609_consultation_disposition_record.py tests/unit/test_luxian_0609_native_consultation_episode_execution.py tests/unit/test_luxian_0609_consultation_measure_check.py tests/unit/test_luxian_0609_rule_catalog.py tests/unit/test_luxian_0609_rule_extension_boundary.py tests/unit/test_luxian_0609_rule_master.py tests/unit/test_luxian_0609_native_package.py tests/unit/test_luxian_0609_phase_scope.py tests/unit/test_luxian_0609_consultation_public_boundary.py tests/unit/test_luxian_0609_consultation_023_engine_replay.py tests/unit/test_luxian_0609_consultation_family_architecture_freeze.py tests/unit/test_luxian_0609_consultation_customer_projection.py tests/unit/test_luxian_0609_canonical_result_finalizer.py tests/unit/test_luxian_0609_native_execution.py -q --tb=short
```

真实模型只使用无身份信息的合成文本，禁用数据库连接和额外长度重试，温度 0。最终 4 个场景 × 2 轮，**8/8 符合预期，16 次调用、12,048 Token**：

| 合成别名 | 场景                                         | 两轮结果                   |
| -------- | -------------------------------------------- | -------------------------- |
| C01      | 中药贴敷建议后仅写遵照执行                   | 均记录不具体               |
| C02      | 有症状依据地暂缓两项检查，具体记载另一项检查 | 均书写合规                 |
| C03      | 三项建议，只具体记录用药，其余遵嘱           | 均记录不具体               |
| C04      | 明确次日检查安排                             | 均书写合规，不宣称实际执行 |

探索失败保留：初版及第一次两步抽取均曾只匹配 6/8，混合建议被模型合并、漏项；随后严格复写字段又退为 4/8，原因是建议扩写和重复动作摘录不连续。最终按固定编号回填完整反馈，修正这两个已观察问题。合成验证不能代表真实病例准确率，也不能保证第一步永远不漏建议。

前端及静态检查（运行目录 `apps/medqc-web`）：

- `npm run check:encoding`：通过，扫描本次暂存的 17 个文本文件。
- `npm run lint -- --no-fix`：0 错误、1,361 条既有警告。
- `npm run type-check`：通过。
- `npm run test:unit`：本机 Chicago 时区 1,331 通过、3 失败，均为日期/展示时间断言；设置 `TZ=Asia/Shanghai` 后，对应两个文件共 32 项全部通过。未声称原始全量运行零失败。
- Ruff：新增模块及其余修改 Python 文件通过；`customer_renderer.py` 全文件检查仍报原有第 246 行 `LX0609-05-01-04` 重复键 F601，已核对 HEAD 中同样存在，本轮未改该处。

日志保留在 `.tmp/consultation-disposition-*.log`，不提交生成物。没有跑全规则真实模型回归，没有写业务库、保存临床结果、重启服务或打包客户发布版。

## 后续验收（更新）

同集真实资料复验已完成，详见页首修复记录；仍需在更新后端后确认目录可见、新点书写结论与旧执行证据结论并列展示。角色识别及建议提取完整性仍须观察，不能用整份结论一致替代逐项或客户验收。
