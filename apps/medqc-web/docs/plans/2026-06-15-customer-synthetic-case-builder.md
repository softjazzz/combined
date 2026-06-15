# 客户自建测试病历工作台 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 `/workstation-v4/customer-sample-validation` 增加“客户自建测试病历”能力，让客户通过模板和复制粘贴创建可质控的测试病历，并保存到独立样本池后立即验证泸县0609质控点。

**Architecture:** 前端从当前抽屉式表单升级为独立全屏工作台页面，页面负责模板选择、多文书编辑、质控点预期结果维护和预览；后端复用现有 `/api/v1/qc/sample-pools/test-records` 创建链路，并逐步扩展 payload 以保存 golden answer、结构化事件和非文书证据。第一阶段不改正式质控任务表，不混入真实样本池。

**Tech Stack:** Vue 3 + Ant Design Vue + Vite；FastAPI + Pydantic + SQLAlchemy/PostgreSQL；现有 `manual-case-sample-service.ts`、`qc_sample_pools.py`、`CustomQCSamplePoolService`。

---

## 设计原则

- 不再使用抽屉创建长病历。抽屉只保留为旧入口兼容或删除。
- 使用独立页面承载长文本编辑：`/workstation-v4/customer-sample-validation/synthetic-case/new`。
- 采用 `medqc-workstation-design` 的工作台语言：浅灰画布、白色玻璃面板、紧凑工具栏、Lucide 图标、清晰的“模板 / 文书 / 预期结果 / 预览”分区。
- 支持两种客户输入方式：
  - 模板驱动：选择规则族模板，一键生成多文书初稿。
  - 自由粘贴：客户可逐文书粘贴和修改时间、正文、医师、科室。
- 结果必须写入独立样本池，例如 `客户自建测试病历`，不能污染真实生产病历。
- golden answer 是测试样本的核心资产，必须支持记录 `LX0609-xxx`、期望状态、触发事实、证据关键词和人工理由。

## 现状依据

- 当前页面：`D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\CustomerSampleValidationView.vue`
- 当前创建测试病历入口仍是 `a-drawer`，标题为 `创建测试病历`。
- 当前前端 API：`D:\LLM\LX888\apps\medqc-web\src\services\manual-case-sample-service.ts`
  - `createManualTestMedicalRecord(payload)`
  - 请求路径：`POST /api/v1/qc/sample-pools/test-records`
- 当前后端路由：`D:\LLM\LX888\apps\medqc-web\backend\app\routers\qc_sample_pools.py`
  - `TestRecordCreateRequest`
  - `TestRecordBasicInfo`
  - `TestRecordDocument`
- 当前后端服务：`D:\LLM\LX888\apps\medqc-web\backend\app\services\custom_qc_sample_pool_service.py`
  - `create_customer_test_record`
  - `_test_record_document_table`

---

## Phase 1：路由与页面骨架

### Task 1: 新增独立创建页面路由

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\src\router\index.ts`
- Create: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\customer-sample-validation\SyntheticCaseBuilderView.vue`

**Step 1: 增加子路由**

在 `customer-sample-validation` 同级增加：

```ts
{
  path: 'customer-sample-validation/synthetic-case/new',
  name: 'WorkstationV4SyntheticCaseNew',
  component: () => import('@/views/workstation-v4/customer-sample-validation/SyntheticCaseBuilderView.vue'),
  meta: { title: '创建测试病历', permission: ['admin', 'qc_manager'] },
}
```

**Step 2: 页面骨架**

页面采用三栏布局：

- 左侧：模板库和文书目录，宽 260px。
- 中间：文书编辑主区，自适应。
- 右侧：质控点预期结果与覆盖状态，宽 360px。
- 底部固定操作栏：保存草稿、预览病历包、保存到测试样本池、保存并立即验证。

**Step 3: 验证**

Run:

```bash
npm run type-check
```

Expected: 路由类型无错误，访问 `/workstation-v4/customer-sample-validation/synthetic-case/new` 不报错。

**Step 4: Commit**

```bash
git add src/router/index.ts src/views/workstation-v4/customer-sample-validation/SyntheticCaseBuilderView.vue
git commit -m "feat: 新增客户自建测试病历工作台路由"
```

---

## Phase 2：抽离现有抽屉表单逻辑

### Task 2: 抽离测试病历类型和默认值

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\CustomerSampleValidationView.vue`
- Modify: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\customer-sample-validation\types.ts`
- Create: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\customer-sample-validation\syntheticCaseBuilder.ts`

**Step 1: 类型迁移**

把当前页面里的下列类型移到 `types.ts` 或新文件：

- `ManualTestRecordDocument`
- `ManualTestRecordBasicInfo`
- `ManualTestRecordCreateRequest`
- `ManualTestRecordCreateResult`
- `TestRecordDocumentForm`
- `TestRecordForm`

新增扩展类型：

```ts
export type SyntheticCaseExpectedStatus =
  | 'non_compliant'
  | 'compliant'
  | 'not_applicable'
  | 'data_gap'
  | 'uncertain'

export type SyntheticCaseGoldenAnswer = {
  id: string
  qc_point_id: string
  expected_status: SyntheticCaseExpectedStatus
  trigger_facts: string[]
  evidence_keywords: string[]
  human_reason: string
}
```

**Step 2: 默认值工具函数**

在 `syntheticCaseBuilder.ts` 中提供：

- `createDefaultSyntheticCaseForm()`
- `createSyntheticDocument(type?: string)`
- `documentTypeLabel(type: string)`
- `normalizeSyntheticCasePayload(form)`

**Step 3: 原页面兼容**

`CustomerSampleValidationView.vue` 中原抽屉逻辑先复用这些 helper，不立刻删除。

**Step 4: 测试**

Run:

```bash
npm run type-check
```

Expected: 原客户样本验证页面仍能打开。

---

## Phase 3：模板库与多文书编辑

### Task 3: 建立规则族模板库

**Files:**

- Create: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\customer-sample-validation\syntheticCaseTemplates.ts`
- Modify: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\customer-sample-validation\SyntheticCaseBuilderView.vue`

**Step 1: 定义模板结构**

```ts
export type SyntheticCaseTemplate = {
  key: string
  name: string
  family: string
  description: string
  suggestedRuleIds: string[]
  documents: Array<{
    document_type: string
    title: string
    record_time_offset_hours?: number
    submit_time_offset_hours?: number
    content: string
  }>
  golden_answers: SyntheticCaseGoldenAnswer[]
}
```

**Step 2: 首批模板**

首批模板至少覆盖：

- 基础时限类
- 病重病危查房类
- 抢救记录类
- CT/MRI 与细菌培养类
- 复制病历类
- 会诊质量类
- 手术麻醉类
- 肿瘤病理化疗类
- 输血类

**Step 3: 页面交互**

左侧模板点击后：

- 填充基本信息。
- 添加多份文书。
- 自动写入建议 `golden_answers`。
- 右侧显示预计覆盖的 `LX0609-xxx`。

**Step 4: 验证**

手工打开页面，切换三个模板，确认文书和预期结果能同步更新。

---

## Phase 4：预期结果 / Golden Answer 面板

### Task 4: 实现右侧预期结果编辑

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\customer-sample-validation\SyntheticCaseBuilderView.vue`

**Step 1: 列表展示**

右侧显示：

- 质控点 ID：`LX0609-xxx`
- 规则名称
- 期望状态
- 触发事实数量
- 证据关键词数量

**Step 2: 编辑能力**

支持：

- 新增质控点预期。
- 删除质控点预期。
- 修改期望状态。
- 编辑触发事实。
- 编辑证据关键词。
- 编辑人工判定理由。

**Step 3: 校验**

保存前校验：

- 至少 1 条文书。
- 每条文书必须有文书类型、标题、正文。
- 选择 `non_compliant` 时必须有触发事实和证据关键词。
- 禁止在正文中出现明显自我提示：`备注：未分析`、`这里缺失`、`本条为反例`。

**Step 4: 验证**

Run:

```bash
npm run type-check
```

---

## Phase 5：后端 payload 扩展

### Task 5: 支持 golden answer 持久化

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\backend\app\routers\qc_sample_pools.py`
- Modify: `D:\LLM\LX888\apps\medqc-web\backend\app\services\custom_qc_sample_pool_service.py`
- Test: `D:\LLM\LX888\apps\medqc-web\backend\tests\unit\test_qc_sample_pools_router.py`
- Test: `D:\LLM\LX888\apps\medqc-web\backend\tests\unit\test_custom_qc_sample_pool_service.py`

**Step 1: 增加 Pydantic DTO**

```py
class TestRecordGoldenAnswer(BaseModel):
    qc_point_id: str
    expected_status: Literal["non_compliant", "compliant", "not_applicable", "data_gap", "uncertain"]
    trigger_facts: list[str] = Field(default_factory=list)
    evidence_keywords: list[str] = Field(default_factory=list)
    human_reason: Optional[str] = None
```

`TestRecordCreateRequest` 增加：

```py
golden_answers: list[TestRecordGoldenAnswer] = Field(default_factory=list)
template_key: Optional[str] = None
```

**Step 2: 服务层保存**

在 `create_customer_test_record` 中把 golden answers 写入样本 item 的 `raw_payload_json`：

```json
{
  "source": "customer_synthetic_case_builder",
  "template_key": "...",
  "golden_answers": [...]
}
```

如果当前 schema 没有独立 golden answer 表，第一阶段不要新增迁移，先存入 `manual_problem_sample_pool_items.raw_payload_json`。

**Step 3: 单测**

新增断言：

- 创建请求包含 `golden_answers` 时，服务不会丢字段。
- `qc_point_id` 非 `LX0609-xxx` 时返回 422 或服务层 ValueError。
- `expected_status` 非枚举时 Pydantic 拦截。

**Step 4: 验证**

Run:

```bash
cd backend
python -m pytest tests/unit/test_qc_sample_pools_router.py tests/unit/test_custom_qc_sample_pool_service.py -q
```

---

## Phase 6：非文书结构化证据输入

### Task 6: 增加“结构化事件”编辑能力

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\customer-sample-validation\types.ts`
- Modify: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\customer-sample-validation\SyntheticCaseBuilderView.vue`
- Modify: `D:\LLM\LX888\apps\medqc-web\backend\app\routers\qc_sample_pools.py`
- Modify: `D:\LLM\LX888\apps\medqc-web\backend\app\services\custom_qc_sample_pool_service.py`

**Step 1: 前端事件类型**

```ts
export type SyntheticCaseStructuredEvent = {
  id: string
  event_type:
    | 'order'
    | 'exam_report'
    | 'lab_report'
    | 'surgery'
    | 'anesthesia'
    | 'blood_transfusion'
    | 'billing'
  event_time?: string
  title: string
  content: string
  fields: Record<string, string | number | boolean | null>
}
```

**Step 2: UI 表现**

中间编辑区增加 `结构化证据` Tab：

- 医嘱
- 检查报告
- 检验报告
- 手术麻醉
- 输血
- 费用

先做轻量 key-value 表单，不做复杂表格。

**Step 3: 后端写入策略**

服务层按照 `event_type` 写入已有 PG/CDM 表：

- `exam_report` -> `exam_master` / `exam_item_report`
- `lab_report` -> `labtest_master` / `labtest_item_report`
- `order` -> `inpat_drug_order` 或 `inpat_nondrug_order`
- `billing` -> `inpat_bill_item`
- `blood_transfusion` -> `blood_application` / `bloodtrans_record`

如果字段不足，写入 `raw_payload_json` 并标记 `data_gap_candidate=true`，不要假装完整。

**Step 4: 验证**

先用两个模板验证：

- CT/MRI 与细菌培养样本。
- 输血样本。

---

## Phase 7：保存、预览和立即验证

### Task 7: 创建保存闭环

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\customer-sample-validation\SyntheticCaseBuilderView.vue`
- Modify: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\CustomerSampleValidationView.vue`
- Modify: `D:\LLM\LX888\apps\medqc-web\src\services\manual-case-sample-service.ts`

**Step 1: 保存到测试样本池**

调用现有：

```ts
createManualTestMedicalRecord(payload)
```

成功后：

- toast：`测试病历已保存到客户自建测试病历样本池`
- 跳回 `/workstation-v4/customer-sample-validation?poolId=...`
- 自动刷新样本池和病历列表。

**Step 2: 保存并立即验证**

保存成功后自动调用：

```ts
runManualSamplePool(poolId, {
  rule_set_key: 'luxian_0609_qc_v1',
  validation_mode: 'customer',
  record_ids: [createdVisitId],
  max_parallel_records: 1,
})
```

**Step 3: 预览病历包**

预览弹窗使用全屏 Modal：

- 左侧文书目录。
- 右侧合并文本。
- 顶部显示基本信息和预计覆盖规则。

**Step 4: 验证**

手工创建一份测试病历，保存后确认：

- 样本池出现一条新病历。
- `visit_id` 以安全前缀生成，例如 `CUSTOM_SYN_` 或 `LX0609_USER_`。
- 可以单独勾选并发起验证。

---

## Phase 8：替换原抽屉入口

### Task 8: 从客户样本验证页跳转到独立页面

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\CustomerSampleValidationView.vue`

**Step 1: 替换按钮行为**

当前 `openTestRecordDrawer()` 改成：

```ts
router.push({ name: 'WorkstationV4SyntheticCaseNew' })
```

**Step 2: 删除或隐藏抽屉**

如果新页面完整可用：

- 删除 `testRecordDrawerOpen` 相关模板。
- 删除抽屉专用 CSS。
- 保留 helper 到新页面。

如果需要低风险上线：

- 保留抽屉但不再作为主入口。
- 增加开发开关，默认走新页面。

**Step 3: 验证**

打开 `/workstation-v4/customer-sample-validation`，点击 `创建测试病历`，应进入新页面。

---

## Phase 9：测试与验收

### Task 9: 前端单元测试

**Files:**

- Create: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\customer-sample-validation\__tests__\syntheticCaseBuilder.spec.ts`

**Test Cases:**

- 默认表单至少有 1 份文书。
- 应用模板后生成对应文书和 golden answers。
- `non_compliant` 缺少证据关键词时校验失败。
- 禁止正文出现 `备注：未分析`。
- payload 能转换为后端期望结构。

Run:

```bash
npm run test:unit -- src/views/workstation-v4/customer-sample-validation/__tests__/syntheticCaseBuilder.spec.ts
```

### Task 10: 后端单元测试

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\backend\tests\unit\test_qc_sample_pools_router.py`
- Modify: `D:\LLM\LX888\apps\medqc-web\backend\tests\unit\test_custom_qc_sample_pool_service.py`

**Test Cases:**

- `POST /test-records` 接收 golden answers。
- 非法 `expected_status` 被拒绝。
- 生成的样本池 item 保留 golden answers。
- 生成的 visit 不混入真实 visit。
- 保存后 record 能进入样本池 records 列表。

Run:

```bash
cd backend
python -m pytest tests/unit/test_qc_sample_pools_router.py tests/unit/test_custom_qc_sample_pool_service.py -q
```

### Task 11: 端到端手工验收

**Steps:**

1. 打开 `http://127.0.0.1:3000/workstation-v4/customer-sample-validation`。
2. 点击 `创建测试病历`。
3. 选择 `CT/MRI 与细菌培养样本` 模板。
4. 修改入院时间、报告时间、病程记录时间。
5. 添加 `LX0609-012` 和 `LX0609-014` golden answers。
6. 点击 `保存并立即验证`。
7. 在客户样本验证页打开任务详情。
8. 确认结果能展示命中、证据和建议。

**Acceptance Criteria:**

- 创建长病历时不再受抽屉宽度限制。
- 客户能清楚编辑多文书、时间和证据字段。
- 保存后的测试病历进入独立样本池。
- 可以单独勾选这份病历跑泸县0609规则集。
- golden answer 不丢失，可被后续评估脚本读取。
- 不暴露 prompt、raw_response、embedding。
- 不写正式病案首页、不写正式质控缺陷表。

---

## 必跑检查

前端：

```bash
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
```

后端：

```bash
cd backend
python -m pytest tests/unit/test_qc_sample_pools_router.py tests/unit/test_custom_qc_sample_pool_service.py -q
```

如果改动了样本写入 PG 表字段映射，还要跑：

```bash
python -m pytest tests/unit/test_customer_synthetic_case_builder.py -q
```

---

## 推荐提交拆分

1. `feat: 新增客户自建测试病历工作台页面`
2. `refactor: 抽离测试病历表单类型和模板工具`
3. `feat: 增加泸县0609测试病历模板库`
4. `feat: 支持测试病历 golden answer 保存`
5. `feat: 支持结构化证据事件写入样本病历`
6. `test: 补充客户自建测试病历前后端测试`

---

## 暂不做的事

- 不把客户自建测试病历写入正式生产病历池。
- 不在本任务内迁入 Trigger Gate 或新分桶策略。
- 不做复杂低代码规则编辑器。
- 不强制每个客户自建样本覆盖全部 49 条规则。
- 不在病历正文中自动插入“这里缺失”等自我提示。
