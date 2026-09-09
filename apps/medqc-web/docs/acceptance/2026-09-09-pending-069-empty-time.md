# 069 空申请时间的缺口归因

## 实查与根因

原排障包中两份会诊记录均有request_time字段但值为空；本地CDM只读查询同病例同样2行，request_time和consultation_time非空数均为0，record_time非空数为2。public同病例0行。

现有模型已定义request_time，037迁移提供字段，ETL已将源consult_apply_time映射至request_time；所以不能继续将该病例直接归因“机构数据源未接入”。source_evidence_reader按真实存在列投影，不给不存在的字段补NULL。

实际错误在evaluate_consultation_timeliness：没有有效申请时间且没有申请文书时，一律返回source_unavailable。三种空值（None、空字符串、空白）均在真实native测试中复现，应为authoritative_time_missing。

## 最小改动

仅修改consultation_timeliness既有缺口分支：已有申请时间字段但空值时归为时间缺失；完全没有申请时间字段时保留旧来源不可用语义。customer_renderer在既有规则/原因文案表增加069时间缺失说明。不改配对算法、24小时时限、ETL、数据库或模型调用。

Renderer只补同职责的文案表条目，无新增独立职责；规则模块负责原因码，后续层不重新判定。

## 首次病程的并行核查

002/016/077共用的首次病程，在原包与本地CDM均只有1行，正文、权威时间、病例特点、诊断依据、鉴别诊断和计划为空。目标列存在，既有读取白名单和同步入口未发现明确裁掉这些字段的证据。不能断言是导出损失，也未证明新增alias能修好。

使用已有配置只读连接远端源库超时。没有修改连接配置、同步数据或调用模型。后续须恢复连接，核对同一首程的源字段和映射预览；仅在确认源有值后决定定向同步或最小映射修复。

## 发布边界

本轮没有补造时间，真实069仍是data_gap。旧任务、客户安装包未更新；资料接入缺口未全部解决。

## 实际验收

- 727项会诊时限、扩展文书执行、Renderer及连续性事实测试通过，3.05秒。覆盖None/空串/空白、无字段旧语义及最终提示。
- 主协调审查补充最终建议断言，复现具体建议被通用建议覆盖；在Renderer既有保护列表补069时间缺失，确保核对源系统时间字段与同步映射的建议能保留。
- 主协调复跑原包真实Provider→native→binding→Finalizer，新旧均data_gap，原因source_unavailable→authoritative_time_missing；两次0LLM，定位仍0，本次不宣称恢复定位。
- ESLint 0错误、11条既有格式警告；npm编码检查扫描0，另对本轮6文件严格UTF-8无BOM/LF检查及diff检查。
