# Workstation V4 新首页融合版设计方案

## 背景

当前 `workstation-v4` 已具备两类基础能力，但首页定位仍不稳定：

- 一类是“当天问题集中点 / 通知聚合 / 批量汇总”
- 一类是“病历池 / worklist / 直接进入质控处理”

如果首页只做管理看板，会偏“看数据”，不利于质控员快速处理。  
如果首页只做列表队列，又缺少当天风险全貌、个人待办、团队状态。

因此首页需要采用“融合版”设计：

- 上层保留管理驾驶舱视角
- 中层以问题队列为主工作区
- 下层承接当天批量汇总与团队分布

目标是让 `/workstation-v4` 真正成为 `admin / qc_manager` 的执行型首页，而不是单纯报表页或单纯病历池。

## 目标

- 将 `/workstation-v4` 首页定位为“病案质控工作台”
- 首页第一屏同时回答两件事：
  - 今天最该处理什么
  - 我应该先点进哪条病历
- 将“当天问题集中点”与“我的待办”明确区分，但放在同一首页协同展示
- 保留现有 `worklist` 作为病历池二级入口，不删除原执行链路
- 不新增复杂任务系统，首版基于现有聚合能力完成首页落地

## 适用角色

首页主视图默认面向：

- `admin`
- `qc_manager`

其他角色策略：

- `doctor / coder` 不默认进入该首页
- 可继续保留原 `workstation-v4` 执行页或裁剪版本

## 首页定位

首页不是纯 BI 看板，也不是纯病历列表。

统一定位为：

- 指挥台：给出当天总体风险与执行负载
- 作战台：提供问题列表、待办、立即处理入口
- 管理台：补充批量汇总、科室分布、workflow 状态分布

## 页面结构

### 一、顶部指挥区

组件建议：

- `HomeHeroBar`

展示内容：

- 页面标题：`病案质控工作台`
- 副标题：`当天问题集中点、我的待办与批量执行概览`
- 日期选择
- 科室筛选
- workflow 筛选
- 刷新按钮
- 可选导出按钮

职责：

- 提供当天范围与全局筛选上下文
- 统一控制首页各子区数据刷新

### 二、KPI 条

组件建议：

- `HomeKpiStrip`

建议固定 6 张卡：

- 当天问题集中点
- 高风险问题
- 我的待处理
- 我的进行中
- 已超时
- 当天批量汇总

设计要求：

- 采用强数字、强层级卡片样式
- 卡片只做摘要，不承载复杂图表
- 点击卡片可驱动主列表筛选或滚动到对应模块

### 三、第一屏主工作区

第一屏是首页核心，不允许被图表抢走注意力。

布局建议：

- 左侧 `65%`：问题集中点主列表
- 右侧 `35%`：详情区 + 我的待办

#### 左侧主列表

组件建议：

- `HotspotListPanel`

作用：

- 展示当天最值得优先处理的问题病历
- 提供快速筛选、排序、选中、进入处理

#### 右侧详情区

组件建议：

- `HotspotDetailPanel`

作用：

- 展示当前选中问题的完整上下文
- 提供“立即处理”动作

#### 右侧待办区

组件建议：

- `MyTodoSummaryPanel`
- `MyTodoListPanel`

作用：

- 展示当前用户的待处理摘要
- 给出最近待办列表
- 支持直接进入处理

### 四、第二屏团队视角

组件建议：

- `TeamSummaryPanel`

建议承载三类内容：

- 当天批量汇总
- 科室风险分布
- workflow 状态分布

可后续扩展：

- 趋势图
- 问题类型分布
- 科室排行榜

原则：

- 第二屏才放图表
- 第一屏不放大面积趋势图

## 主列表设计

问题集中点列表要采用“执行队列”语义，而不是通知消息列表语义。

### 表头建议

- 患者信息
- 科室
- 流程
- 风险级别
- 问题摘要
- 活跃缺陷
- 最新状态
- 最近时间
- 操作

### 行内容建议

- 患者姓名 + `visit_id`
- 科室
- `workflow_type`
- 风险级别标签
- `summary` 或 `risk_reason`
- `active_defect_count`
- `queue_status + latest_qc_grade`
- `latest_created_at`
- `查看详情 / 立即处理`

### 顶部筛选建议

- 搜索：患者名 / 病历号 / `visit_id`
- 风险级别筛选
- 科室筛选
- workflow 筛选
- 排序切换

### 行为建议

- 单击行：更新右侧详情
- 双击行或点 CTA：进入病历处理
- 当前选中行需要有明显 active 态

## 右侧详情设计

右侧详情不能只是消息正文，要体现“是否值得立即处理”和“处理后将进入哪个 workflow”。

建议字段：

- 标题
- 风险级别
- workflow
- 患者姓名
- `visit_id`
- 科室
- 问题摘要
- 活跃缺陷数
- 最新质控评分
- 最新质控等级
- 队列状态
- 最新通知时间
- 最近一次消息摘要

建议按钮：

- `立即处理`
- `查看病历池`
- 可选 `标记已读`

## 我的待办设计

“我的待办”不是“问题集中点”的副本，必须明确它是“当前用户可执行事项”。

### 待办摘要

建议展示：

- 待处理
- 进行中
- 已超时

### 待办列表

每条建议展示：

- 患者姓名 + `visit_id`
- 科室
- workflow
- 当前任务状态
- 优先级
- 摘要
- 进入处理按钮

建议首页只展示最近 `8-12` 条。

## 第二屏团队视角设计

第二屏承接管理驾驶舱能力，但不影响第一屏执行效率。

建议模块：

- 当天批量汇总列表
- 科室风险分布
- workflow 状态分布

后续可扩展：

- 问题类型分布
- 7 日趋势
- 科室排行榜

## 数据口径

### 一、问题集中点

定义：

- 面向“今天最该关注的问题集合”
- 更偏问题视角

建议数据主源：

- `notifications`
- `qc_defects`
- `qc_results`
- `workflow_queue_state`

特点：

- 可按病历聚合，也可按同类问题聚合
- 首页首版建议以“病历维度热点项”为主

### 二、我的待办

定义：

- 面向“当前用户负责处理的具体事项”
- 更偏执行视角

首版口径建议：

- `notifications.recipient_id = current_user`
- 当前角色可处理的活跃 `qc_defects`
- `workflow_queue_state` 中对当前角色有意义的 `pending / failed / running`

注意：

- 首版不新建 `qc_tasks`
- 先以聚合口径形成“准待办”
- 后续口径稳定后再评估是否下沉任务表

### 三、当天批量汇总

定义：

- 面向当天批量生成、批量质控的执行概览

建议来源：

- `notifications` 中 `*_batch_summary`
- 或已有批量持久化聚合结果

### 四、团队视角

定义：

- 面向质控管理人员查看今天整体风险、状态分布、处理负载

建议来源：

- `hotspots`
- `my_todo_items`
- `workflow_queue_state`
- `batch_summaries`

## 首页主接口方案

首页不要依赖前端本地拼多个旧接口，应提供统一聚合接口。

### 主接口

- `GET /api/v1/workstation/home`

返回建议：

- `kpis`
- `hotspots`
- `my_todo_summary`
- `my_todo_items`
- `batch_summaries`
- `department_options`
- `team_summary`

### 子接口

- `GET /api/v1/workstation/home/hotspots`
- `GET /api/v1/workstation/home/todos`

后续可选：

- `GET /api/v1/workstation/home/{record_id}/launch-context`

## 字段映射建议

### KPI

- `当天问题集中点` <- `kpis.hotspot_total`
- `高风险问题` <- `kpis.high_risk_total`
- `我的待处理` <- `kpis.my_pending_total`
- `我的进行中` <- `kpis.my_in_progress_total`
- `已超时` <- `kpis.my_overdue_total`
- `当天批量汇总` <- `kpis.batch_summary_total`

### 热点列表字段

- 患者信息 <- `patient_name + visit_id`
- 科室 <- `department`
- 流程 <- `workflow_type`
- 风险级别 <- `severity`
- 问题摘要 <- `summary`
- 活跃缺陷 <- `active_defect_count`
- 最新状态 <- `queue_status + latest_qc_grade`
- 最近时间 <- `latest_created_at`
- 操作上下文 <- `record_id + launch_action + launch_stage`

### 右侧详情字段

- 标题 <- `title`
- 摘要 <- `summary`
- 科室 <- `department`
- workflow <- `workflow_type`
- 风险级别 <- `severity`
- 缺陷数 <- `active_defect_count`
- 最新评分 <- `latest_qc_score`
- 最新等级 <- `latest_qc_grade`
- 队列状态 <- `queue_status`
- 未读数 / 消息 <- `unread_count + latest_notification_id`

### 待办字段

- 患者信息 <- `patient_name + visit_id`
- 科室 <- `department`
- workflow <- `workflow_type`
- 状态 <- `task_status`
- 优先级 <- `priority`
- 截止时间 <- `due_at`
- 摘要 <- `summary`
- 操作上下文 <- `launch_action + record_id`

### 团队汇总字段

建议补充：

- `workflow_status_distribution`
- `department_risk_distribution`
- `issue_type_distribution`

## 默认排序建议

### 热点列表默认排序

建议后端固定：

- `unread_count desc`
- `severity priority desc`
- `occurrence_count desc`
- `latest_created_at desc`

目的：

- 先暴露未读与高风险项
- 再强调重复触发与最近发生的问题

### 待办默认排序

建议：

- 超时优先
- 进行中优先于待处理
- 失败优先于成功
- 最近更新时间倒序

## 跳转与交互规范

### 首页到病历处理

点击“立即处理”时：

- 跳转到 `/workstation-v4/worklist`
- 附带：
  - `record_id`
  - `action`
  - `from_stage`

### 跳转动作映射

- `frontpage_generate -> generate_frontpage`
- `coding_qc -> qc_coding`
- `frontpage_qc -> qc_frontpage`
- `settlement_qc -> qc_settlement`

### 列表点击规范

- 单击：刷新右侧详情
- CTA：直接进入病历
- 卡片 / 汇总点击：刷新筛选或跳转对应 `stage` 队列页

## 前端改造清单

### 一、首页容器

保留首页容器页，继续收口为编排层：

- `QCOverviewView.vue`

建议补充或强化：

- `HomeHeroBar.vue`
- `HomeKpiStrip.vue`

### 二、主列表

需要重构：

- `HotspotListPanel.vue`

增强点：

- 搜索
- 风险筛选 pill
- workflow 筛选
- active row
- 行内 CTA

### 三、右侧详情

需要增强：

- `HotspotDetailPanel.vue`

增强点：

- 患者上下文
- 最新结果
- 队列状态
- 明确“立即处理”

### 四、我的待办

继续保留并强化：

- `MyTodoSummaryPanel.vue`
- `MyTodoListPanel.vue`

### 五、团队视角

扩展：

- `TeamSummaryPanel.vue`

增强点：

- 批量汇总
- workflow 状态分布
- 科室风险分布

### 六、路由

保持：

- `/workstation-v4` 作为首页
- `/workstation-v4/worklist` 作为病历池

要求：

- 所有“立即处理”统一落到 `/workstation-v4/worklist`
- 原执行链路不回归

## 后端改造清单

### 一、聚合接口

继续使用并扩展：

- `GET /api/v1/workstation/home`
- `GET /api/v1/workstation/home/hotspots`
- `GET /api/v1/workstation/home/todos`

### 二、首页聚合 service

继续在 `worklist_service` 内承担首页聚合职责，首版不要求单独拆出 analytics service。

建议增强：

- 科室风险分布
- workflow 状态分布
- 问题类型分布
- 用户责任归属更清晰的待办规则

### 三、不要做的事

本轮不建议：

- 为首页单独新建物理表
- 新建完整任务中心
- 让前端本地拼 `overview + worklist + todos`

## 实施优先级

### P0

- 首页第一屏结构完成
- KPI + 问题列表 + 右侧详情 + 我的待办跑通
- `立即处理` 跳转链路稳定

### P1

- 团队视角模块增强
- workflow 状态分布
- 科室风险分布
- 待办口径进一步收紧

### P2

- 趋势图
- 导出
- 更细角色裁剪
- 更复杂的排行榜与分析图

## 验收标准

- `admin / qc_manager` 打开 `/workstation-v4` 即进入首页
- 第一屏可完成“筛选问题 -> 查看详情 -> 进入病历处理”
- 我的待办可直接进入对应 workflow
- 第二屏可展示当天批量汇总与团队分布
- `/workstation-v4/worklist` 继续保留病历池能力
- 首页既不是纯看板，也不是纯表格，职责分工清晰

## 假设

- 本轮默认采用“按角色分层”策略，不做全员统一首页
- 首页主区域默认是“问题集中点列表”，不是统计图表
- “我的待办”首版采用聚合计算，不单独建设任务系统
- 首页聚合先落在 service 层，不先建设 SQL view 或 materialized view
- 原病案工作台保留为二级入口，不在本轮删除
