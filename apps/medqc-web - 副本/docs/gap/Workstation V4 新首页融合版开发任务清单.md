# Workstation V4 新首页融合版开发任务清单

## 背景

本文档是 [Workstation V4 新首页融合版设计方案](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/Workstation%20V4%20新首页融合版设计方案.md) 的实施拆解版。  
目标不是重复设计，而是把“页面、接口、联调、验收”拆成可执行任务，便于开发、联调、提测和验收。

## 范围

本轮范围：

- `admin / qc_manager` 访问 `/workstation-v4` 的首页重构
- `问题集中点 + 我的待办 + 团队视角` 融合首页
- `/workstation-v4/worklist` 继续保留为病历池
- 首页与现有 `record_id / action / from_stage` 进入病历链路打通

不在本轮范围：

- 新建完整任务系统
- 替换所有角色的默认首页
- 首页趋势分析大盘深度建设
- 删除原病历池或旧执行页

## 一、前端开发任务清单

### A. 路由与入口

- 确认 `/workstation-v4` 对 `admin / qc_manager` 默认进入新首页
- 确认 `/workstation-v4/worklist` 保留病历池能力
- 确认带 `record_id / action / from_stage / stage` 参数时，不被首页拦截
- 确认旧 `/workstation-v4/qc-overview` 兼容或重定向策略
- 确认菜单“工作台首页”指向新首页
- 确认“病历池”菜单指向 `/workstation-v4/worklist`

### B. 首页容器

- 收口 `QCOverviewView.vue`，只保留首页编排职责
- 拆出或强化 `HomeHeroBar`
- 拆出或强化 `HomeKpiStrip`
- 统一首页筛选态：
  - `date`
  - `department`
  - `workflow`
  - `severity`
  - `keyword`
- 首页筛选状态与 URL query 保持同步
- 支持刷新后恢复筛选条件

### C. 问题集中点主列表

- 重构 `HotspotListPanel.vue` 为“执行队列表”
- 接入搜索框：
  - 患者名
  - 病历号
  - `visit_id`
- 接入风险级别筛选 pill
- 接入科室筛选
- 接入 workflow 筛选
- 接入排序切换：
  - 默认
  - 最近时间
  - 风险等级
  - 未读优先
- 行内展示字段对齐设计稿：
  - 患者信息
  - 科室
  - 流程
  - 风险级别
  - 问题摘要
  - 活跃缺陷
  - 最新状态
  - 最近时间
  - 操作
- 当前选中行增加 active 态
- CTA 明确区分：
  - 查看详情
  - 立即处理

### D. 右侧详情区

- 增强 `HotspotDetailPanel.vue`
- 展示：
  - 标题
  - workflow
  - 风险级别
  - 患者姓名
  - `visit_id`
  - 科室
  - 摘要
  - 活跃缺陷数
  - 最新质控评分
  - 最新质控等级
  - 队列状态
  - 最近消息时间
- 增加按钮：
  - `立即处理`
  - `查看病历池`
  - 可选 `标记已读`
- 选中项变化时右侧详情同步刷新
- 无选中项时展示空态

### E. 我的待办

- 强化 `MyTodoSummaryPanel.vue`
- 展示：
  - 待处理
  - 进行中
  - 已超时
- 强化 `MyTodoListPanel.vue`
- 每条待办展示：
  - 患者姓名 + `visit_id`
  - 科室
  - workflow
  - 状态
  - 摘要
  - 进入处理按钮
- 同一病历同一 workflow 避免重复刷多条
- 点击待办可直接进入病历处理

### F. 第二屏团队视角

- 扩展 `TeamSummaryPanel.vue`
- 展示：
  - 当天批量汇总
  - 科室风险分布
  - workflow 状态分布
- 无数据时提供简洁空态
- 不允许第二屏抢占第一屏主工作区视觉焦点

### G. 视觉与交互统一

- 首页视觉统一采用“管理驾驶舱 + 执行队列”融合风格
- 第一屏禁用大面积折线图
- 风险标签颜色统一
- active row、hover、空态、loading 态统一
- 首页按钮文案统一：
  - `立即处理`
  - `查看详情`
  - `查看病历池`
- 保证列表、详情、待办三者之间选中态清晰

## 二、后端开发任务清单

### A. 首页聚合接口

- 确认 `GET /api/v1/workstation/home` 返回首页所需完整数据
- 确认 `GET /api/v1/workstation/home/hotspots` 支持分页、筛选、排序
- 确认 `GET /api/v1/workstation/home/todos` 支持当前用户待办查询
- 统一错误返回，不让前端自行推断空态与异常态

### B. 首页主 payload

- `kpis` 字段完整返回
- `hotspots` 字段完整返回
- `my_todo_summary` 字段完整返回
- `my_todo_items` 字段完整返回
- `batch_summaries` 字段完整返回
- `department_options` 正确返回
- `team_summary` 正确返回

### C. 热点列表口径

- 热点项统一返回：
  - `id`
  - `record_id`
  - `visit_id`
  - `patient_id`
  - `patient_name`
  - `department`
  - `workflow_type`
  - `severity`
  - `title`
  - `summary`
  - `occurrence_count`
  - `unread_count`
  - `active_defect_count`
  - `latest_qc_score`
  - `latest_qc_grade`
  - `queue_status`
  - `queue_status_source`
  - `latest_created_at`
  - `latest_notification_id`
  - `launch_action`
  - `launch_stage`
- 同一病历在首页首版以“单行热点项”优先，不做无限拆散
- `workflow_type` 推断逻辑稳定，不混淆首页/编码/结算

### D. 我的待办口径

- 待办明确区别于热点项
- `recipient_id = current_user` 优先
- 活跃缺陷与状态聚合避免重复
- `running / failed / pending` 优先级明确
- 返回字段至少包括：
  - `id`
  - `todo_type`
  - `record_id`
  - `visit_id`
  - `patient_name`
  - `department`
  - `workflow_type`
  - `task_status`
  - `priority`
  - `due_at`
  - `active_defect_count`
  - `summary`
  - `launch_action`

### E. 团队视角口径

- 返回当天批量汇总
- 返回科室风险分布
- 返回 workflow 状态分布
- 可预留问题类型分布字段

### F. 排序与筛选

- 热点默认排序固定为：
  - `unread_count desc`
  - 严重级别优先
  - `occurrence_count desc`
  - `latest_created_at desc`
- 待办默认排序固定为：
  - 超时优先
  - 进行中优先
  - 最近时间倒序
- 明确支持筛选参数：
  - `date`
  - `department`
  - `workflow`
  - `severity`
  - `keyword`

### G. 跳转上下文

- `launch_action` 与 `launch_stage` 返回稳定
- 与现有 `record_id / action / from_stage` 进入病历逻辑兼容
- 暂不强制新增 `launch-context` 接口
- 若后续跳转逻辑复杂，再补专用接口

## 三、联调任务清单

### A. 首页基础联调

- 首页加载时一次性拿到：
  - KPI
  - 热点列表
  - 我的待办
  - 批量汇总
  - 团队视角
- 任一子模块为空时不影响其他模块渲染
- 接口报错时前端空态与错误态可区分

### B. 筛选联动

- 日期切换后：
  - KPI 更新
  - 热点更新
  - 待办更新
  - 批量汇总更新
- 科室筛选后：
  - 主列表与团队视角同步刷新
- workflow 筛选后：
  - 主列表、详情、待办状态一致

### C. 列表与详情联动

- 单击热点行，右侧详情更新
- 切换选中项时，详情不残留上一条数据
- 无数据时右侧为空态
- 点击“立即处理”后能进入对应病历与 workflow

### D. 待办联动

- 待办摘要与待办列表数量口径一致
- 点击待办可直接进入处理
- 从病历返回首页后保留筛选态

### E. 团队视角联动

- 批量汇总点击后能进入对应 stage 队列页
- workflow 状态分布与实际 worklist 状态基本一致
- 科室风险分布与主列表筛选口径一致

## 四、测试与验收 Checklist

### A. 权限与路由

- `admin / qc_manager` 打开 `/workstation-v4` 进入新首页
- `doctor / coder` 不误入后台首页
- `/workstation-v4/worklist` 可正常访问
- 老入口不崩溃

### B. 首页加载

- 首屏渲染稳定
- KPI 正常显示
- 主列表正常显示
- 右侧详情正常显示
- 我的待办正常显示
- 第二屏正常显示

### C. 主列表行为

- 搜索可用
- 筛选可用
- 排序可用
- active row 明确
- CTA 正常
- 列表分页正常

### D. 详情行为

- 详情字段完整
- 风险级别正确
- workflow 正确
- 最新状态正确
- 立即处理跳转正确

### E. 待办行为

- 摘要数量正确
- 列表不重复
- 点击待办跳转正确
- 超时项优先级正确

### F. 团队视角

- 批量汇总正确
- 科室风险分布正确
- workflow 状态分布正确
- 无数据时空态正常

### G. 回归

- 原 `workstation-v4` 病历池能力不回归
- 首页进入病历后首页质控链路不回归
- 编码质控链路不回归
- 结算质控链路不回归
- 通知、缺陷、状态显示不回归

## 五、实施顺序建议

### Phase 1

- 收口首页容器
- 完成 Hero + KPI + 主列表 + 右侧详情

### Phase 2

- 完成我的待办摘要与待办列表
- 打通“立即处理 / 待办进入处理”

### Phase 3

- 完成第二屏团队视角
- 补齐科室与 workflow 分布

### Phase 4

- 做联调修正
- 完成验收清单
- 再评估趋势图、导出、排行榜

## 六、交付标准

- 首页可作为 `admin / qc_manager` 默认入口稳定使用
- 首页第一屏具备明确执行价值
- 数据口径区分“热点”与“待办”
- 病历池继续保留，不丢原能力
- 前后端字段、排序、跳转、筛选口径统一
