# 质控首页概览与病历池准商用改造实施方案

> **执行要求：** 使用 `executing-plans` 按任务顺序实施；每个任务独立提交、复核并暂停，未经重新授权不得连续推进。

**目标：** 将现有“质控首页概览”和“病历池”改造成可接入医院真实数据的可信工作入口，保证全量统计、病历身份、数据范围、最新质控结果和运行状态均来自服务端权威合同。

**架构：** 继续使用现有 CDM、质控任务、Canonical 结果和工作台接口，不新增第二套病历资料链、Bundle、统计平台或通用数据中台。病历池先建立真实病历清单和最新质控摘要；首页只对同一查询口径做服务端聚合，不从前端当前页、截断列表或文案关键词反推统计事实。

**技术栈：** FastAPI、SQLAlchemy、PostgreSQL/CDM、Vue 3、TypeScript、Ant Design Vue、Vitest、Pytest。

---

## 执行优先级

准商用阶段先保证“看不到不该看的病历、看到的病历身份准确、统计来自同一真实范围”，再调整视觉和首页分析。固定顺序为：

1. Task 0：只读冻结真实数据、权限字段、病历身份、同步状态和最新正式质控结果来源；
2. Task 1A：生产环境彻底关闭演示病历；
3. Task 1B：接口认证、机构/科室范围和三坐标身份；
4. Task 2：病历池服务端全量统计与最新质控投影；
5. Task 2 验收门禁：使用真实数据对账病历池；
6. Task 3：病历池前端准商用界面；
7. Task 4：病历池稳定后，首页使用同一查询口径做服务端聚合；
8. Task 5：质控首页前端收敛；
9. Task 6：最后处理旧 Dashboard、真实趋势、审计和性能。

权限与机构隔离和演示数据隔离属于同级生产门禁。Task 0 未证明当前用户如何约束 `institute_id/department/record` 之前，不得开发 Task 1B、Task 2 或任何首页 UI。

## 一、适用范围与默认假设

首版默认面向：

- 质控科、病案科管理员；
- `admin`、`qc_manager` 等可查看全院或授权范围的角色；
- 默认规则包为当前正式启用的全病历质控规则包，具体 `rule_set_key/version` 必须由任务或接口回显，不能由页面写死；
- 科室质控员的“本科室/我的待办”作为后续角色适配，不在本轮新增个人工作台平台。

如果真实上线角色不是上述人员，Task 0 必须先调整数据范围和首页 KPI，不得直接开发。

## 二、当前证据与问题边界

| 问题                         | 当前证据                                                                    | 准商用风险                                      |
| ---------------------------- | --------------------------------------------------------------------------- | ----------------------------------------------- |
| 首页 KPI 来自截断列表        | `get_home()` 先取最多 50 条热点、12 条待办，再由 `_build_home_kpis()` 统计  | KPI 最大值受列表上限影响，不是全量统计          |
| 首页包含静态信息             | `QCOverviewView.vue` 中存在固定涨跌幅、静态趋势曲线和固定用户信息           | 客户会把演示数据当成真实业务数据                |
| 首页风险分类依赖前端关键词   | 页面根据标题/摘要关键词推断编码、首页、结算、时效风险                       | 文案变化即可改变统计分类                        |
| 首页主数据不是全病历质控结果 | 当前首页热点主要来自通知和 frontpage/coding/settlement 工作流               | 与用户当前使用的全病历质控任务口径不一致        |
| 病历池 KPI 按当前页计算      | `WorkstationV4ListView.vue` 从当前 `workbenchRows` 计算待处理、超时、处理中 | 翻页后数字变化，无法代表筛选范围                |
| 生产环境仍可能混入演示病历   | 配置文件可将 `include_demo_records` 设为 `true`，覆盖环境默认值             | 真实病历与样例无法可靠区分                      |
| 病历池接口缺少明确访问范围   | `/api/medical-records/workstation` 当前路由未显式注入当前用户               | 存在越权查看真实病历风险                        |
| 病历行主键过窄               | 真实记录当前将 `id` 设置为 `visit_id`                                       | 多机构或重复 visit_id 时可能碰撞                |
| 数据状态与质控状态混合       | 当前风险、资料缺失、队列状态在前端组合显示                                  | “源资料未同步”“规则 data_gap”“技术异常”容易混淆 |

## 三、权威数据合同

### 3.1 唯一主链

```text
CDM真实病历
→ 病历池服务端查询
→ 稳定病历三坐标
→ 现有质控任务/Canonical结果投影
→ 病历池列表
→ 首页服务端聚合
```

禁止：

- 从 Scene/Domain Bundle 判断医院资料是否完整；
- 从前端当前页计算全量 KPI；
- 从客户文案或规则标题猜测风险分类；
- 为首页新增第二套结果表、第二份质控状态或隐式回退数据源；
- 为了显示“数据就绪”而按文书数量、Bundle 条数或字段非空进行猜测。

### 3.2 病历身份

每条真实病历必须同时返回：

```json
{
  "record_key": "<institute_id>|<patient_id>|<visit_id>",
  "institute_id": "...",
  "patient_id": "...",
  "visit_id": "..."
}
```

规则：

- `record_key` 只用于页面行身份和接口定位，不替代原始三坐标；
- 缺失任一坐标时不得生成看似稳定的假键；
- 多机构场景不得只用 `visit_id`；
- 路由进入病历详情时必须携带或可安全解析三坐标。

### 3.3 病历池返回合同

在现有 `/api/medical-records/workstation` 响应中向后兼容增加：

```json
{
  "scope": {
    "hospital_id": "...",
    "department": null,
    "scene": "all|running|final",
    "generated_at": "2026-08-08T10:00:00+08:00"
  },
  "summary": {
    "records_total": 0,
    "qc_not_run_total": 0,
    "qc_running_total": 0,
    "qc_completed_total": 0,
    "qc_technical_error_total": 0
  },
  "facets": {
    "departments": [],
    "scenes": [],
    "qc_statuses": []
  },
  "records": []
}
```

单条记录增加：

```json
{
  "record_key": "...",
  "source_state": {
    "status": "ready|syncing|partial|failed|unknown",
    "last_sync_at": null,
    "reason": null
  },
  "latest_qc": {
    "status": "not_run|running|completed|failed",
    "rule_set_key": null,
    "rule_set_version": null,
    "finished_at": null,
    "non_compliant_count": 0,
    "data_gap_count": 0,
    "uncertain_count": 0,
    "technical_error_count": 0
  }
}
```

约束：

- `source_state` 只能来自现有同步状态或已持久化的来源观测；没有权威事实时必须返回 `unknown`；
- `latest_qc` 只投影最新完成或正在运行的正式任务，不重新解释规则状态；
- `data_gap` 属于质控结果，不能等价为 `source_state=partial`；
- `technical_error` 属于执行健康状态，不能显示成医疗质量缺陷；
- `summary` 必须由同一筛选条件的服务端聚合查询生成，不能从本页 `records` 计数。

### 3.4 首页返回合同

继续使用 `/api/v1/workstation/home`，但将全病历质控作为主视图，返回：

```json
{
  "scope": {
    "hospital_id": "...",
    "department": null,
    "scene": "all|running|final",
    "rule_set_key": "...",
    "date_from": "2026-08-08",
    "date_to": "2026-08-08",
    "generated_at": "2026-08-08T10:00:00+08:00",
    "source_snapshot_at": null,
    "is_stale": false
  },
  "kpis": {
    "records_total": 0,
    "qc_pending_total": 0,
    "qc_completed_total": 0,
    "high_risk_review_total": 0
  },
  "data_health": {
    "source_sync_status": "healthy|delayed|failed|unknown",
    "source_error_total": 0,
    "technical_error_total": 0,
    "running_task_total": 0,
    "last_successful_qc_at": null
  },
  "priority_items": [],
  "department_distribution": [],
  "rule_family_distribution": [],
  "trend": null
}
```

约束：

- KPI 查询与列表 `limit` 完全解耦；
- `priority_items` 只是 KPI 的明细切片，不能反过来计算 KPI；
- `high_risk_review_total` 的规则由受控状态、缺陷等级或规则主数据确定；
- 无真实历史序列时 `trend=null`，前端隐藏趋势区；
- 环比/同比没有服务端基线时返回 `null`，前端不得显示固定涨跌幅；
- frontpage/coding/settlement 可以作为辅助入口，但不得与全病历质控 KPI 混算。

## 四、页面设计

### 4.1 质控首页概览

首屏回答：“当前哪里需要处理？”

```text
范围栏：医院 / 时间 / 场景 / 科室 / 规则集 / 数据截至时间

纳入病历 | 待质控 | 已完成 | 高风险待复核

优先处理队列（主区）             数据运行状态（侧栏）
- 患者、科室、问题、期限          - CDM最后同步时间
- 高风险、超时、技术异常          - 同步延迟/失败
- 进入病历或查看结果              - 任务积压/技术异常

科室分布 | 高频规则族 | 真实趋势（有数据才显示）
```

视觉要求：

- 使用 `workstation-v4` 浅色医疗工作台风格；
- 首页只有一层主工作面，不堆叠装饰卡片；
- 蓝色用于主操作和选中态，红橙只表示真实风险；
- “技术异常”进入数据运行状态，不和不合规合并；
- 加载、无数据、无权限、查询失败、数据过期均有明确状态；
- 移除静态 SVG 趋势、固定用户姓名、固定涨跌幅和“AI 洞察”装饰。

### 4.2 病历池

病历池定位为“真实病历资产清单与质控入口”，不再复制首页驾驶舱。

筛选：

- 患者姓名、住院号、病案号；
- 在院/已出院；
- 入院科室、出院科室；
- 入院/出院日期，必须显式选择日期字段；
- 数据状态：已就绪、同步中、部分、失败、未知；
- 质控状态：未质控、执行中、已完成、失败；
- 规则集和结果版本作为高级筛选。

表格：

| 列       | 展示内容                             |
| -------- | ------------------------------------ |
| 患者     | 按权限脱敏姓名、性别年龄、住院号     |
| 住院信息 | 科室、病区、主管医师、入出院时间     |
| 数据状态 | 同步状态、最后同步时间、受控缺口说明 |
| 最新质控 | 状态、不合规/数据不足/技术异常数量   |
| 结果版本 | 规则集版本、完成时间                 |
| 操作     | 查看病历、查看结果、开始或重新质控   |

交互：

- 所有筛选、排序、分页均由服务端执行；
- URL 保留筛选条件，进入病历后可原样返回；
- 批量操作复用现有底部工作条；
- 行内不展示内部 reason code、Prompt、Token 或原始模型字段；
- 超过授权范围的病历不能只在前端隐藏，后端必须不返回。

## 五、实施任务

### Task 0：冻结真实数据和权限合同（只读）

**文件：**

- Create: `docs/audits/2026-08-08-medqc-home-record-pool-data-contract.md`
- Read: `backend/app/services/medical_records/query_service.py`
- Read: `backend/app/services/workstation/worklist_service.py`
- Read: `backend/app/routers/medical_records_query.py`
- Read: `backend/app/routers/workstation.py`
- Read: 现有同步任务、质控任务和 Canonical 结果持久化代码

**步骤：**

1. 冻结当前 Git HEAD、后端配置、测试机构和三份真实住院记录三坐标。
2. 用 CodeGraph 记录“病历池 → 病历详情 → 启动质控 → 保存结果 → 首页聚合”的真实调用链。
3. 确认真实病历的唯一键、机构字段、入出院时间和科室权威来源。
4. 确认 `source_state` 可使用的现有同步状态；无法证明的字段固定为 `unknown`。
5. 确认最新正式质控任务、Canonical 结果、规则集版本和完成时间的唯一查询来源。
6. 确认 `admin/qc_manager` 与科室角色的数据范围字段；证据不足时停止，不开发前端遮罩式权限。
7. 统计当前首页和病历池的静态数据、截断统计、当前页统计和演示数据入口。
8. 核对接口当前是否强制认证，以及用户、机构、科室、病历范围第一次生效的位置。
9. 输出字段字典、SQL来源、空值语义、权限范围、首次丢失层和性能基线。
10. 根据审计证据冻结 Task 1B 和 Task 2 的准确文件白名单；不能在计划阶段猜测公共权限文件。
11. 只提交审计文档并暂停。

**验收：**

- 每个首页 KPI 和病历池字段都有唯一来源；
- 明确哪些字段当前只能是 `unknown`；
- 证明没有通过 Bundle 判断资料完整性；
- 明确认证、机构、科室和病历范围的服务端合同；
- 明确最新正式质控任务和同步状态的唯一来源；
- 没有生产代码修改。

### Task 1A：生产环境演示数据失败关闭

**文件：**

- Modify: `backend/app/services/frontpage_settings.py`
- Modify: `backend/app/services/medical_records/query_service.py`（仅在必要时增加来源标记）
- Test: `backend/tests/unit/test_frontpage_settings.py`
- Test: `backend/tests/unit/test_workstation_query_service.py`

**步骤：**

1. 写失败测试：`ENV=production` 且配置文件写入 `include_demo_records=true` 时，病历池仍不得返回演示病历。
2. 运行测试，确认现状失败。
3. 在演示数据策略边界增加生产环境失败关闭；保留开发/测试环境显式演示能力。
4. 对演示记录保留 `is_demo=true`，真实记录固定 `is_demo=false`。
5. 运行聚焦测试，确认生产、开发和真实数据阈值三种场景。
6. 运行 `git diff --check`，形成中文提交并暂停。

**测试命令：**

```powershell
python -m pytest backend/tests/unit/test_frontpage_settings.py backend/tests/unit/test_workstation_query_service.py -q
```

**验收：**

- 生产环境任何配置都不能混入演示记录；
- 不删除演示数据构造器；
- 不修改正式 CDM 数据；
- 不新增配置中心。

### Task 1B：病历池访问范围与稳定身份

**文件：**

- Provisional: `backend/app/routers/medical_records_query.py`
- Provisional: `backend/app/services/medical_records/query_service.py`
- Provisional test: `backend/tests/unit/test_workstation_query_service.py`
- Provisional test: `backend/tests/unit/test_medical_records_service.py`

以上文件仅为当前调用链候选。Task 0 必须先确认真实认证、用户组织范围和查询入口；如需其它公共权限文件，先重新评审白名单，不得由开发者边做边扩。

**步骤：**

1. 写失败测试：未认证请求被拒绝；全院角色获得授权范围；科室角色不能读取其他科室。
2. 写失败测试：相同 `visit_id`、不同机构或患者的记录生成不同 `record_key`。
3. 写失败测试：缺失三坐标时不得生成可用于详情路由的伪造键。
4. 运行测试，确认现状失败。
5. 为 `/api/medical-records/workstation` 注入当前用户和服务端数据范围。
6. 在序列化边界返回三坐标和稳定 `record_key`，保留旧 `id/visitId` 兼容字段。
7. 确保筛选后的 `total`、科室 facet 和记录列表使用同一权限条件。
8. 运行聚焦测试和既有病历查询回归。
9. 中文提交并暂停，使用真实的两个机构/科室账号复核。

**停止条件：**

- 无法从当前用户合同获得机构或科室范围；
- 需要在前端猜测权限；
- 需要复制一套用户/组织架构。

### Task 2：病历池服务端全量摘要与最新质控投影

**文件：**

- Provisional: `backend/app/routers/medical_records_query.py`
- Provisional: `backend/app/services/medical_records/query_service.py`
- Provisional test: `backend/tests/unit/test_workstation_query_service.py`
- Provisional test: `backend/tests/unit/test_medical_records_service.py`

Task 0 查清最新正式质控结果、任务和同步状态的唯一来源后，必须重新冻结本 Task 的准确文件范围。禁止为满足当前候选白名单而复制投影逻辑。

**步骤：**

1. 写失败测试：准备 31 条记录、分页 15 条，`summary.records_total` 必须为 31 而不是 15。
2. 写失败测试：科室、日期、场景和质控状态筛选同时作用于列表、total、summary 和 facets。
3. 写失败测试：同一病历有多个历史任务时只投影最新正式任务；旧任务不能覆盖新结果。
4. 写失败测试：`data_gap`、`technical_error` 和 `source_state` 分别计数。
5. 写失败测试：没有权威同步事实时 `source_state=unknown`，不得按文书数猜 ready。
6. 运行测试，确认现状失败。
7. 使用现有查询和现有任务/Canonical结果构建一次服务端投影；不得为此新建结果表。
8. 将 summary/facets 查询与分页列表解耦，但复用同一筛选条件构造函数。
9. 检查 SQL 查询次数，避免每条病历单独查询最新结果。
10. 运行聚焦回归，记录 1千、1万条等价数据量下的查询耗时或 explain 证据。
11. 中文提交并暂停，用真实病历抽查三坐标、状态、结果版本。

**验收：**

- 任何页码下 summary 不变；
- `records_total` 与相同筛选条件的数据库 count 一致；
- 没有 N+1 查询；
- 没有修改 Canonical、Envelope 或规则状态。

### Task 2 验收门禁：真实病历池对账（只读）

**文件：**

- Create: `docs/audits/2026-08-08-medqc-record-pool-real-data-acceptance.md`
- Read only: Task 2 产生的接口、数据库查询和正式任务结果

**步骤：**

1. 固定 Git HEAD、后端 PID/启动时间、机构、账号、筛选条件和规则集版本。
2. 选取至少三个科室、在院/终末各不少于 20 份真实脱敏病历。
3. 对同一筛选条件逐项核对数据库 count、接口 total、summary 和 facets。
4. 抽查至少 10 条病历的三坐标、数据范围、最新正式任务、规则版本和结果状态数量。
5. 使用全院账号和科室账号验证机构/科室隔离；尝试通过关键词、页码和直接 URL 访问越权病历。
6. 核对 `source_state`、规则 `data_gap`、执行 `technical_error` 没有互相改写。
7. 核对生产响应不存在演示病历或固定展示数据。
8. 记录接口 P50/P95、SQL 数量和最慢查询；本门禁不修改代码。
9. 输出审计报告并暂停。

**通过条件：**

- 权限、total、summary、facets 和逐行身份全部对账；
- 没有把未知同步状态猜成 ready；
- 没有确认的 P1 数据泄漏、统计失真或病历身份碰撞；
- 通过后才允许 Task 3 前端改造。

### Task 3：病历池前端准商用界面

**文件：**

- Modify: `src/views/workstation-v4/types.ts`
- Modify: `src/views/workstation-v4/normalize.ts`
- Modify: `src/views/workstation-v4/composables/usePatientRecords.ts`
- Modify: `src/views/workstation-v4/components/WorkstationV4ListView.vue`
- Modify: `src/views/workstation-v4/components/workbench/BatchTablePanel.vue`
- Test: `tests/unit/views/workstation-v4/usePatientRecords.spec.ts`
- Test: `tests/unit/views/workstation-v4/WorkstationV4ListView.spec.ts`
- Create if needed: `tests/unit/views/workstation-v4/BatchTablePanel.spec.ts`

**步骤：**

1. 写失败测试：列表 KPI 使用服务端 summary，不能根据当前 15 行计算。
2. 写失败测试：在院/已出院筛选必须传给后端，不能只过滤当前页。
3. 写失败测试：数据状态、质控状态和技术异常显示为三个独立语义。
4. 写失败测试：无权限、查询失败、空结果、数据过期都有客户可懂状态。
5. 写失败测试：进入病历和返回列表时保留 URL 筛选、页码和排序。
6. 运行 Vitest，确认现状失败。
7. 扩展严格 TypeScript DTO 和 normalize 边界，不使用宽泛 `any` 绕过。
8. 将病历池顶部改为紧凑摘要和单行筛选；移除从当前页推导的假 KPI。
9. 将表格收敛为患者、住院信息、数据状态、最新质控、结果版本、操作。
10. 复用现有底部批量工作条，不新增第二套选择 Store。
11. 运行聚焦测试、ESLint、type-check 和编码检查。
12. 浏览器验证 1440、1080、390 宽度和至少 1000 条服务端分页数据。
13. 中文提交并暂停，先让真实用户试用病历检索和进入详情。

**测试命令：**

```powershell
npm run test:unit -- tests/unit/views/workstation-v4/usePatientRecords.spec.ts tests/unit/views/workstation-v4/WorkstationV4ListView.spec.ts
npm run type-check
npm run check:encoding
```

### Task 4：质控首页服务端权威聚合

**文件：**

- Modify: `backend/app/services/workstation/worklist_service.py`
- Modify only if request parameters change: `backend/app/routers/workstation.py`
- Test: `backend/tests/unit/test_workstation_home_router.py`
- Create: `backend/tests/unit/test_workstation_home_service.py`

**步骤：**

1. 写失败测试：存在 80 条高风险记录且 `priority_items limit=12` 时，KPI 仍返回 80。
2. 写失败测试：KPI、优先队列、科室分布使用相同日期、场景、科室、规则集和权限范围。
3. 写失败测试：技术异常只进入 `data_health`，不增加医疗不合规或高风险数量。
4. 写失败测试：无真实趋势数据时返回 `trend=null`。
5. 写失败测试：无上期统计时比较值为 `null`，不生成涨跌幅。
6. 运行测试，确认现状失败。
7. 将 KPI 改为独立服务端聚合查询，不再接收截断后的 hotspots/todos 作为统计输入。
8. 优先队列仅投影全量查询中的 TopN，保留服务端稳定排序和受控风险分类。
9. 将现有 frontpage/coding/settlement 统计移为辅助信息或兼容字段，不与全病历质控主 KPI 混算。
10. 返回 scope、generated_at、数据健康和最新成功质控时间。
11. 运行聚焦回归和同条件数据库 count 对账。
12. 中文提交并暂停。

**验收：**

- KPI 不受 `hotspot_limit/todo_limit` 影响；
- 首页和病历池相同筛选条件下记录总数一致；
- 风险分类不依赖标题关键词；
- 没有新增聚合平台或重复结果表。

### Task 5：质控首页前端收敛

**文件：**

- Modify: `src/views/workstation/QCOverviewView.vue`
- Modify: `src/views/workstation/components/HomeHeroBar.vue`
- Modify: `src/views/workstation-v4/types.ts`
- Create: `tests/unit/views/workstation-v4/QCOverviewView.spec.ts`
- Test: `tests/unit/views/workstation-v4/WorkstationV4HomeEntry.spec.ts`

**步骤：**

1. 写失败测试：页面不再出现固定用户、固定涨跌幅和静态趋势。
2. 写失败测试：服务端 `trend=null` 时不渲染空趋势卡，而展示优先队列和数据健康。
3. 写失败测试：技术异常、同步延迟和来源失败只出现在数据运行状态。
4. 写失败测试：范围栏显示规则集、日期范围、场景、科室和数据截至时间。
5. 写失败测试：无权限、空数据、过期数据、查询失败均有不同状态和下一步操作。
6. 运行测试，确认现状失败。
7. 按“范围栏 → 4 KPI → 优先队列/数据健康 → 分布/可选趋势”重组页面。
8. 删除关键词风险推断；只展示服务端结构化分类。
9. 使用当前登录用户信息，禁止页面写死姓名和角色。
10. 保留现有详情跳转，不改病历详情和质控执行链。
11. 运行聚焦测试、ESLint、type-check、编码检查和浏览器验收。
12. 中文提交并暂停。

### Task 6：旧 Dashboard、审计与性能收尾

**文件：**

- Modify only if confirmed: `src/router/index.ts`
- Test: 相应路由测试
- Create: `docs/audits/2026-08-08-medqc-home-record-pool-real-data-acceptance.md`

**步骤：**

1. 确认 `/workstation-v4` 是准商用唯一质控首页；旧 `/dashboard` 只做重定向，不继续维护第二套统计。
2. 验证打开病历、启动质控、查看结果、导出操作均有现有审计记录；缺失项单独立项，不在本任务新建审计平台。
3. 基于 Task 2 已验收的真实病历池，对每个首页筛选条件核对数据库 count、病历池 total、首页 KPI 三方一致。
4. 验证生产环境没有样例病历、固定涨跌幅、静态趋势和硬编码用户。
5. 只有服务端存在真实历史序列时才启用趋势；否则继续隐藏。
6. 记录首页和病历池首屏 P50/P95；目标为正常院内网络下 P95 小于 2 秒，超标时先定位 SQL，不引入缓存平台。
7. 记录失败、过期、同步延迟和任务技术异常的客户展示。
8. 输出验收报告并暂停，是否扩大到科室个性化首页另行批准。

## 六、总体测试矩阵

| 场景                        | 首页         | 病历池                          | 预期               |
| --------------------------- | ------------ | ------------------------------- | ------------------ |
| 真实数据 31 条、分页 15 条  | KPI=31       | total=31                        | 不受当前页影响     |
| 高风险 80 条、明细 limit 12 | KPI=80       | 可筛出80                        | 明细截断不改变统计 |
| 无历史趋势                  | 不显示假曲线 | 不受影响                        | `trend=null`       |
| CDM 同步延迟                | 数据健康提示 | source_state=delayed/unknown    | 不形成医疗缺陷     |
| 规则 data_gap               | 进入结果统计 | latest_qc.data_gap_count        | 不等价为同步失败   |
| 模型/执行技术异常           | 数据健康提示 | latest_qc.technical_error_count | 不显示为不合规     |
| 未质控病历                  | 待质控计数   | latest_qc=not_run               | 不伪造结果         |
| 生产环境配置开启 demo       | 不纳入       | 不返回                          | 失败关闭           |
| 科室用户跨科室查询          | 不计入       | 不返回                          | 后端权限生效       |
| 相同 visit_id 不同机构      | 分别统计     | record_key不同                  | 无行身份碰撞       |

## 七、停止条件

出现以下任一情况必须暂停并只记录证据：

- 需要修改 Canonical、Envelope、规则状态或质控执行器；
- 需要新建第二套 Bundle、结果表、资料快照或同步平台；
- 无法从现有用户合同证明机构/科室权限范围；
- 无法证明 source_state 的权威来源；
- 需要通过文书数量或前端关键词猜测业务状态；
- 查询性能不足但尚未完成 SQL/索引证据分析；
- 为了做趋势图需要伪造或回填历史数据；
- 真实数据包含未脱敏内容且测试环境没有合规授权。

## 八、提交与审核边界

- 每个 Task 一个中文提交；
- 每个 Task 完成聚焦测试和真实数据复核后暂停；
- Task 0 只读审计通过后，才分别批准 Task 1A、Task 1B；
- Task 1A、Task 1B 通过后，才允许 Task 2；
- Task 2 必须先通过真实病历池验收门禁，才允许 Task 3；
- 病历池 Task 1A–3 验收后，才启动首页 Task 4–5；
- 不同时改运行病历质控、终末病历质控、规则引擎或客户样本验证；
- 测试数量不能替代服务端 count 对账、权限验证和真实病历抽查。

## 九、推荐批准范围

当前只批准：

1. Task 0：真实数据、权限、字段和最新质控结果来源的只读审计。

Task 1A、Task 1B 和 Task 2 均未获开发授权。Task 0 完成后，先根据机构/科室权限、最新正式任务和同步状态来源冻结准确文件白名单，再逐项批准；当前不得先改首页 UI。
