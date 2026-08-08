# 泸县 0609 统计分析 Dashboard 验收记录

日期：2026-08-08

## 验收范围

- 页面：`/workstation-v4/stats`
- 统计来源：已完成根任务、当前规则版本的 Canonical Envelope，以及三坐标病历身份。
- 时间口径：根任务 `finished_at`；页面标注为“按质控完成时间”。

## 真实资料复核

| 项目                          | 结果 |
| ----------------------------- | ---: |
| 已完成 Canonical 事件         |   72 |
| Dashboard 去重病历数          |    5 |
| 同范围病历池服务端下钻病历数  |    5 |
| 可展示的真实日时间桶          |    7 |
| 无效或缺失 Canonical Envelope | 1704 |

“无效或缺失 Canonical Envelope”只在资料健康度展示，不并入临床不合规、数据不足或合规结论。技术异常同样不计作临床不合规。

科室分布的去重病历数之和同为 5，和 KPI 一致。规则模块只展示 Top 10，因此其 `evaluated_count` 不能与全量结果结构直接求和；全量状态结构仍由服务端有效 Canonical 条目聚合。

## 下钻合同

Dashboard 下钻统一带 `analytics_scope=final`，病历池服务端再按根任务完成时间、规则和结果状态筛选。默认统计范围也会进入 Canonical + 三坐标筛选；前端不以本页数组过滤病历。

接口响应只提供聚合计数、日期桶、科室/规则聚合与资料健康度；未包含病历正文、提示词、LLM 原文或完整规则结果列表。

## 性能

使用同一真实数据库连续调用统计服务 10 次：

| 指标 |     耗时 |
| ---- | -------: |
| P50  | 156.9 ms |
| P95  | 180.2 ms |

满足 P95 不超过 2 秒的验收门槛。

## 自动化验证

- 后端聚焦：`test_luxian_0609_analytics_service.py`、`test_workstation_analytics_router.py` 共 9 通过；`test_workstation_query_service.py`、`test_workstation_analytics_drilldown_router.py`、`test_workstation_analytics_router.py` 共 25 通过。
- 前端聚焦：`usePatientRecords.spec.ts`、`LuxianQcAnalyticsView.spec.ts`，共 9 通过。
- `npm run type-check`、目标 ESLint、编码与 diff 检查通过。

## 剩余风险

- 当前是全院临时范围；用户—机构—科室权限尚未接入，后续接入时须在统计与下钻查询的同一服务端边界增加约束。
- 资料健康度基于现有任务/Envelope 留存，不应解释为医院原始资料完整度。
