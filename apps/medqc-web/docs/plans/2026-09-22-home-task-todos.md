# 首页个人任务待办 Implementation Plan

**Goal:** 打通全部场景的个人任务待办、24 小时内到期提醒及列表下钻，先修复创建人身份写入。

**Architecture:** 任务与分配关系继续由 qc_tasks / qc_task_records 唯一持有。任务路由统一计算待办标签，首页只展示计数，任务列表复用相同条件。暂不推断任务场景，不修改质控规则或数据库。

**Tech Stack:** FastAPI、现有 PostgreSQL 适配器、Vue 3、TypeScript、Ant Design Vue、pytest、Vitest。

## 1. 主代理核实证据

- 基线 `e26da7fdc`，工作区干净；延续已获授权的 Sol / Medium 并行开发方式。
- `backend/app/routers/tasks.py:124` 创建任务读取 user_id，而认证和个人查询优先使用 id。复用现有 `_get_task_scope_user_id` 即可修正，不改历史数据。
- `backend/app/schemas/tasks.py:60` 与 `supabase/migrations/010_add_qc_task_management.sql:9` 无任务场景字段；抽样器也没有场景过滤（`backend/app/services/task_sampling_service.py:55`）。不能仅靠任务名称或当前出院状态反推创建时场景。
- 真实只读核查：qc.qc_tasks 共 11 条，1 条空 creator_id，7 条有 deadline；实际 deadline 为 text，并非旧迁移脚本的 timestamptz。因此禁止直接依赖字符串比较实现到期过滤。
- `src/views/workstation/QCOverviewView.vue` 无个人待办；`src/router/index.ts:188` 已有 `/dashboard/tasks/my`。复用已有列表，不新增平行任务页。
- 已向用户询问是否本批扩大到三场景合同；未得到扩大范围答复前按推荐的全部场景最小闭环实施。三场景不计为交付。

## 2. 固定合同

1. 新增 `GET /api/v1/tasks/todo-stats`，仅统计当前用户收到的任务；沿用 READ 权限与实际认证身份。返回 `{as_of, assigned, in_progress, due_soon}`，放入既有 success envelope。
2. `assigned` 即未开始；`in_progress` 即进行中；`due_soon` 是独立待办标签，范围为 assigned/in_progress 且 `as_of < deadline <= as_of + 24h`。过期、完成、取消、草稿、抽样中不纳入到期提醒。
3. 到期文案明确为“24 小时内到期”，不把这个工程定义伪装成手册已明确的自然日口径。带时区 ISO 时间统一 UTC；旧无时区时间按 Asia/Shanghai（固定 UTC+8）；旧日期按当天 23:59:59.999999。空值/非法值不算到期，不转为 epoch 或伪造时间。
4. stats 的 as_of 由服务端生成；列表新增 `todo=assigned|in_progress|due_soon` 及可选带时区 ISO `as_of`，同时要求 `tab=received`。所有到期判断复用后端同一 helper。首页下钻携带返回的 as_of，避免阈值随跳转漂移；并发任务状态变化仍可能改变计数，不承诺跨请求数据库快照。
5. 列表分页在待办过滤之后进行，total 为完整匹配数量；不允许固定抓前 N 条后宣称完整。普通无 todo 列表和原 stats 输出保持兼容。
6. 空分配是成功零；身份缺失 401；非法 todo/as_of 或非 received 搭配 todo 为 422；数据库不可用/异常保持非 2xx。页面加载和失败不显示 0，可重试，过期响应不得覆盖新状态。
7. 首页模块独立于全院临床概览加载，明确“我的任务待办 / 全部场景”，不受旁边科室筛选影响。零数量点击提示“没有待处理的事项”；成功非零跳已有个人列表。
8. 列表展示可清除的待办范围提示，重置清除 URL 中 todo/as_of；浏览器返回/切换 query 会同步列表。失败清空旧列表与 total，避免旧任务冒充新范围；请求序号防止旧响应覆盖。
9. 首页挂载模块前复用 authStore.userRoles 判断任务 READ 角色（admin/qc_manager/qc_staff/doctor）。仅有 sync_admin/super_admin 的首页用户不发任务请求；不扩大现有后端权限。路由待办参数非法时不得静默退成全量；切换页内快捷状态需先清除旧待办参数。

## 3. 分工与验收

### A 后端任务合同

所有权：`backend/app/routers/tasks.py`、`backend/tests/unit/test_task_todos.py`。不得修改其他 agent 文件。

1. 使用轻量 FastAPI app、认证依赖覆盖和内存数据库替身写反例；禁止使用 full app/login fixture 或真实数据库写入。
2. 覆盖创建 id 优先与旧 user_id 兼容、无身份不 insert、统计个人隔离与去重、非法查询、空值/非法日期、时区/日期边界、过期/完成排除、分页前过滤、统计列表一致及失败非成功。
3. 最小实现固定合同。新增生产代码预计少于 200 行，沿用现有路由局部 helper，不建注册表/状态机。
4. 运行 `python -m pytest tests/unit/test_task_stats_scope.py tests/unit/test_task_todos.py -q`，主代理独立复核后统一提交。

### B 首页与下钻

所有权：`src/api/tasks.ts`、`src/views/workstation/QCOverviewView.vue`、新 `src/views/workstation/HomeTaskTodos.vue`、`src/views/dashboard/tasks/MyTasksView.vue` 及对应专属单测。

1. 扩充 API 严格类型与编码测试，保留旧无参行为。
2. 新增职责完整的待办模块（独立加载、展示、重试、导航及错误状态），首页仅引入。现有概览 Vue 已大，不把新逻辑继续堆入其脚本。
   新模块格式化后为 201 行，是完整的加载/失败/导航/响应式展示职责；现有首页仅增加 5 行，不为行数拆成转发壳或零碎函数文件。
3. 个人列表读取并显示查询范围，分页保留筛选，重置/返回响应一致；清空失败旧数据并保护请求顺序。
4. 按既有医疗浅色样式实现非装饰性区块，使用已有 Lucide 图标，检查侧栏展开与窄视口布局。
5. 聚焦 Vitest + type-check；禁止跑会改写全仓的 eslint --fix，不暂存或提交。

### C 主代理与独立审查

1. 主代理保存只读 schema / 真实任务数量证据，不打印患者原文或凭据。
2. 独立审查代理只读审查身份隔离、时间边界、分页、错误语义、状态变化和路由兼容；不以 agent 完成声明代替主代理验收。
3. 主代理复跑聚焦测试，真实只读接口与浏览器核对首页计数、零提示、下钻范围、刷新和清除。
4. 提交前 encoding、lint --no-fix、type-check、unit；与上一批已复现的基线失败分开记录。只按本批文件提交，不推送或写库。

## 4. 剩余风险

- 三场景需持久化合同、创建/抽样约束与历史未知处理；未纳入本批默认范围。
- 本地正向到期样本不保证存在；时间边界通过隔离用例，真实数据库验收如为零必须如实记录。
- deadline 为 text；本批按解析后的时间判断，暂不做字段迁移。旧日期按日末的兼容规则需后续产品口径复核。
- received 仍以分配关系定义；任务级状态不是“当前用户所有病历完成状态”，本批不重新解释状态。
- 原有任务权限、任务详情权限及大规模个人任务读取性能需独立评审，不在页面层扩大数据范围。

## 5. 执行状态

- 主代理代码与只读 schema 核查：完成。
- A 后端：完成，主代理复跑两文件 35 条通过；错误详情收敛后再次复跑新文件 18 条通过。
- B 前端：完成，主代理最终复跑四文件 62 条通过；类型检查通过。
- C 独立审查与集成验收：完成，无新增阻断；真实只读接口、浏览器及最终全量回归均已记录。

## 6. 验收证据

- 修复前后同一真实数据库均采用连接级只读事务；5 个分配用户普通列表/统计仍为 1/3/3/3/3，无孤立任务分配。本批没有执行迁移、历史回填或真实创建操作。
- 新接口的 assigned/due_soon 均为 0，in_progress 为 1/3/3/3/3；独立 SQL + 日期解析对比每个用户的三个 todo 列表 ID 集合与 total，全部一致。本地没有当前到期正样本，日期正例及边界由隔离测试覆盖，不能标记为真实到期样本验收。
- 实际物理 SELECT 计数：todo-stats 2 次、每个 todo 列表 2 次；主代理发现并去除 todo 路径无用 COUNT 后，统计加三列表从 11 次降至 8 次。最终整组冷读约 120ms，其余 26–29ms；请求组不同于旧接口基线，不据此声称整体加速百分比。LLM 调用为 0。
- 独立审查促成修复：无任务 READ 角色不挂载首页模块；极端时间输入不触发 500；清除范围立即让旧请求失效；无效、数组、孤立、空或无时区 as_of 不退成全量列表；列表失败持久提示且重试，旧响应不可覆盖新范围。
- 浏览器真实账号验证：待办显示 0/1/0，零值提示“没有待处理的事项”；进行中下钻带服务端 as_of，列表为 1 条；清除范围删除 todo/as_of；非法 as_of 展示链接无效，未展示全量任务。
- 浏览器仅阻断本地读取接口模拟故障：新首页统计故障显示“不可用”而非 0，重试恢复 0/1/0；列表故障清除旧行并显示持久提示，重试恢复 1 条。阻断已清除。820px（侧栏展开）和 390px（侧栏收起）检查新模块 scrollWidth 不大于 clientWidth；视口覆盖与侧栏状态已恢复。
- 只读验收服务关闭了完整 startup 并跳过登录时间更新；原有临床概览在此环境加载失败，新模块仍独立成功。不将该环境结果归因于本批，也未以模拟临床数据掩盖失败；完整临床概览运行时不属于本批验收范围。
- 最终质量检查：类型检查通过；全量 lint 使用 `--no-fix`，0 errors / 953 warnings；最后修改路径再次 lint 为 0 errors。前端聚焦四文件 62 条通过；全量 `npm run test:unit -- --maxWorkers=2 --minWorkers=1` 为 1106 passed / 3 failed（129 文件）。失败仍为 `SingleRecordQcResultPanel.spec.ts` 两条与 `QcRecordReviewPreview.spec.ts` 一条，已在第一批未修改基线复现，本批未更改这些组件/测试；不宣称全量门禁全绿。
- 实现与验收边界到此结束：一次中文提交，不推送、不合并，不顺带处理原有临床概览启动依赖或剩余三场景合同。
- 提交前核对暂存清单，仅本批 12 个文本文件；`npm run check:encoding` 与 `git diff --check` 通过，临时验收脚本、日志、凭据和患者数据均未暂存。
