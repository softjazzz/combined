# 任务详情病历清单 Implementation Plan

**Goal:** 从“我的任务”和“全部任务”打开真实任务详情，展示同一任务范围内的病历分配与处理状态；收到范围不得混入他人病历。

**Architecture:** 复用现有 `GET /api/v1/tasks/{id}`，增加可选 tab=all/created/received，默认 all 保持旧合同。复用已有个人范围身份与任务过滤；收到范围同时过滤关联 assignee_id。前端两个入口共用一个完整职责的详情抽屉，读取单个详情响应，不再把列表缓存与另一份进度响应拼成详情。

**Tech Stack:** FastAPI、现有 Supabase 兼容读取层、Vue 3、Ant Design Vue、Vitest、pytest。

## 证据与取舍

- 上一 Goal 轮次为 progress，提交 `742cc0736`；本批开始工作区干净。
- 主代理亲读 AllTasksView 的 handleViewDetail，仅有 message.info；MyTasksView 的详情仅展示列表行及 getTaskProgress，没有调用 getTaskDetail，也没有病历清单。子代理只读检索确认 getTaskDetail 没有实际页面消费者。
- 后端 get_task_detail 已有任务和关联读取，但不接受个人范围；若直接接“我的任务”，会暴露同任务分配给其他人的病历。因此必须先修复这一真实读取合同。
- 可选方案：复制两个详情 UI 会重复请求状态管理；新增一套任务详情 API 会与现有所有者重复。选择扩展现有读取合同并复用一个抽屉。
- 三坐标身份调查发现旧 record_id 不能安全定位跨机构/多次就诊病例。本批不会按单 record_id 跳转文书，不以显示清单等同于完整场景抽样、质控执行或病历审核交付。病例身份持久化与安全文书入口仍需后续独立合同。
- 新抽屉可能超过 200 行，原因是完整承载详情异步生命周期、信息区、清单筛选分页、加载/空/错误/重试及响应式布局，而不是逐函数碎片；两个旧入口不再各自拥有详情状态机。

## 固定合同

1. tab 省略或 all：保持全任务详情兼容；created：creator_id 必须为当前用户；received：任务必须含当前用户分配，records 只含当前 assignee_id。已有 READ 权限不扩大，广义角色权限审计不混入本批。
2. 使用认证 id 优先、user_id 兼容。个人范围缺身份 401；非法 tab 422；任务不存在或不在所选范围统一 404，不能暴露任务名或关联；数据库不可用 503，查询异常固定 500，不泄露 SQL，不伪造零条。
3. 任务 total_records/progress 保持主表口径，不改成“我的病历”。records 是所选范围内实际关联，按 created_at/id 稳定排序；关联 id 是列表 key，不能按可能重复的 record_id 合并。
4. `TaskRecordItem` 明确声明现有字段与可空值，`TaskDetail` 使用 records: TaskRecordItem[]；不扩大 any。字段缺失显示未记录，不把缺失 score/defect_count 当 0。病例处理状态 pending/in_progress/completed/skipped 与任务状态分开映射。
5. 抽屉支持真实加载、空清单、错误重试、关键字/处理状态本地筛选与分页。重新打开、切换任务或范围、关闭时清除旧详情；晚到响应不得覆盖新任务或复活已关闭抽屉。
6. 首页“我的任务”传 tab=received，“全部任务”传 tab=all。显示全任务元信息与当前清单范围；不得根据列表行伪造详情成功或混用全任务进度统计为个人病历计数。
7. 本批只有只读展示，不新增写操作按钮、不开放单 record_id 文书跳转、不新增数据库结构。

## 分工与验收

- 主代理：`backend/app/routers/tasks.py` 的 get_task_detail、`backend/tests/unit/test_task_detail_scope.py`、本文/PRD/滚动计划；先写双用户同任务反例、created/received/all、缺身份、错误和稳定 key，再改路由。
- Sol / medium 前端代理：`src/api/tasks.ts`、新 `src/components/qc/TaskDetailDrawer.vue`、两个任务视图及专属测试。遵循 medqc-workstation-design，保留原列表/筛选/创建行为，不更改其他模块。
- 独立审查代理：只读验证范围隔离、状态域、响应竞态、NULL/零值、关键 diff，不自行扩展。
- 主代理独立跑相关 pytest/Vitest、全量编码/lint/type-check/unit；业务数据库仅只读核查真实详情数量与个人分配数，浏览器验证两个入口及移动布局。
- 数据库迁移45与真实 PostgreSQL 写验收已单独询问，未收到批准前不执行；本批与该授权无依赖。

## 状态

已完成代码与只读验收。PRD 总目标保持完整；本批不把“收到任务列表”中的审核流程、三场景抽样或身份迁移标记完成。

## 主 Agent 验收与修正

- 后端聚焦测试 146 passed，覆盖双用户同任务隔离、created/all 兼容、缺身份、非法范围、异常语义、稳定关联顺序，以及两次读取间撤销分配的反例。该竞态原本可能留下任务元信息，现收到范围的关联若已为空则统一 404。
- 前端聚焦测试 5 文件 117 passed；类型检查通过，lint 为 0 errors / 953 warnings。全量单测 1154 passed / 4 failed：原有两个质控组件的 3 条断言失败，另 1 条 CustomerSampleValidationView 用例在聚焦重跑通过。本批没有修改这些无关模块，不声称全量门禁全绿。
- 真实数据库只读事务确认 `transaction_read_only=on`。以 5 个用户、13 组任务-用户组合调用实际详情路由，收到范围的关联 ID 集合均与库中分配关系一致，且主表总病历数未被个人范围改写；范围外和不存在任务均为 404。冷请求约 123ms，后续约 8–14ms；无业务数据写入和 LLM 调用。
- 浏览器验证“全部任务”与“我的任务”均能打开详情；前者展示全任务关联，后者仅展示个人关联。核查了关键字/状态过滤、真实错误及重试、390px 移动布局；窄屏仅表格横向滚动，不使整个抽屉溢出。真实任务最多 10 条，25 条分页行为由真实 Ant 表格组件测试验证。
- 独立审查曾提出 `.single()` 空结果可能抛 PGRST116；主 Agent 核对当前 `supabase_client.py` SQLAlchemy 适配器，空结果返回 `data=None`，并用真实只读路由核实 404，因此该推断不适用于当前部署。广义 `tab=all` READ 权限沿用旧合同，角色授权边界须另列审计，不能以个人详情隔离代替完整 RBAC。
- 当前历史任务关联仍以单个 `record_id` 表示病例，无法唯一定位跨机构或多次就诊文书。抽屉不提供文书跳转或审核写操作；下一批先固定 `(institute_id, patient_id, visit_id)` 的持久化和读取合同，再推进场景候选与真实执行链。迁移及写入验收仍待明确授权。
