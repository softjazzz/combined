# V3.6 工作表现排名合同（P1-B）

> 日期：2026-09-27。对应 PRD 第 2 节“工作表现：质控缺陷排名 / 质控病历排名”。

> 2026-09-28 更新：本文的“质控病历排名”计数与场景段落已由
> `2026-09-28-v36-record-ranking-design.md` 替代。质控病历现在按审核人和病例三坐标去重，
> 并可按审核时冻结的真实场景筛选；本文的“质控缺陷排名”口径不变，具体场景仍不可归属。

## 1. 证据

`dashboard_api.py` 的 `/performance` 现状有以下问题：

- 两个排名都按旧 `qc_results.analyzed_by` 计结果行数，口径相同，没有区分“缺陷”和“病历”；
- `last_week` 只设了开始时间、没有结束时间，会把本周也算进去；
- 读取异常被吞掉；
- 读不到数据时返回写死的示例排名（虚构人名和数字）。

这违反“未知不伪造”的规则，本批全部替换。

## 2. 口径（每个事实只有一个 owner）

**质控病历排名**：数据来源是 `qc_record_reviews`。

- 在统计窗口内，按 `reviewer_id + institute_id + patient_id + visit_id` 去重统计审核病历数：
  - `count` 为去重病例总数；
  - `initial_count`、`recheck_count` 分别按同一三坐标去重；
  - 两种审核上下文（任务、病历列表）都计入。
- 同一病例可同时有初审与复审，因此两个阶段数不能相加替代 `count`。

**质控缺陷排名**：数据来源是任务人工缺陷。

- 谓词与人工缺陷审核相同。
- 在统计窗口内，按 `manual_created_by` 统计创建数，时间取 `manual_create` 历史的 `created_at`。
- 另给出其中已通过（`approved`）和已驳回（`rejected`）的数量，对应 PRD 质控员分析里的“驳回数”。
- 自动缺陷无法归属到具体的人，不计入。

**统计窗口**：按医院时区 Asia/Shanghai 计算，再转换为库内的无时区 UTC 做比较，区间左闭右开。

| period | 起 | 止 |
|---|---|---|
| `this_week` | 本周一 00:00 | 当前时刻 |
| `last_week` | 上周一 00:00 | 本周一 00:00 |
| `this_month` | 本月 1 日 00:00 | 当前时刻 |

非法 period 返回 422。

**场景**：

- 当 `scene=all` 时，给出两个排名。
- 其他场景下，病历排名按审核事件冻结的可信场景精确筛选；历史缺失场景的事件只进入 `all`。
- 人工缺陷仍没有稳定场景 owner，因此缺陷排名返回 `null`，并附
  `unavailable_reason="scene_not_attributable"`；这不影响同一响应中的病历排名。

## 3. 接口

`GET /dashboard/performance`，路径与参数名保持不变。响应 `data` 为：

```
{
  "period": "...",
  "period_label": "...",
  "range": {"start": "<ISO，带 +08:00>", "end": "..."},
  "scene": "...",
  "defect_ranking": [{"user_id", "name", "count", "approved_count", "rejected_count", "rank"}] | null,
  "record_ranking": [{"user_id", "name", "count", "initial_count", "recheck_count", "rank"}] | null,
  "unavailable_reason": null | "scene_not_attributable"
}
```

- 每个排名取前 10 名。
- 排序规则：按 `count` 降序，再按 `user_id` 升序，保证顺序稳定。计数相同时名次相同，采用竞争排名，即 1、1、3。
- `name` 取 `sys_users.display_name`，缺失时为 null，前端改显示 id。
- 数据库故障返回固定脱敏的 503，不再兜底示例数据，也不静默返回空列表。
- 有数据源但窗口内没有记录时，返回空数组，前端显示“本期暂无”。

## 4. 前端（`PerformanceBoard` / `DashboardView`）

- 周期切换：本周、上周。本月可选。
- 排名显示姓名（或 id）和计数；病历排名附“初审 / 复审”，缺陷排名附“通过 / 驳回”。
- `null` 且带不可用原因时，显示“该场景暂不支持”。
- 请求失败显示可重试，不显示示例数据或 0。
