# 质控结果反馈演示版 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** 由同一个功能演示账号在单病历质控结果页中提交“准确 / 有误 / 补充说明”，并在同一账号、同一页面回看自己提交的当前反馈。

**Architecture:** 第一阶段只做演示账号内的小闭环，不建设开发者工作台、处理状态机或多角色审批。反馈作为质控结果的附属记录持久化，按根任务引用、客户安全病历引用和规则编号绑定；它不修改 Canonical、质控状态、证据或 Token。

**Tech Stack:** FastAPI、SQLAlchemy Core、PostgreSQL/Alembic、Vue 3、TypeScript、Ant Design Vue、Vitest、Pytest。

---

## 1. 第一阶段范围

### 1.1 仅支持功能演示账号

现有工作站功能演示账号映射为：

```text
admin@medqc.com
user_id = admin-001
roles = admin, qc_manager
```

第一阶段：

- 提交反馈和查看反馈均使用同一个功能演示账号，不区分反馈提交方与反馈处理方。
- 反馈入口只在该演示账号的质控结果页显示。
- 后端接口必须校验登录态和演示账号身份，不能只靠前端隐藏。
- 不新增医生、科室质控员、开发者、审核员等角色。
- 不新增独立菜单和全院反馈工作台。
- 非演示账号访问反馈接口时返回 `403`，但不影响正常查看质控结果。
- `production` 环境本来就禁止默认演示账号启动，因此该能力不会自动成为正式生产功能。

### 1.2 页面内完成反馈和回看

每条展开的质控结果底部显示：

```text
这个质控结果准确吗？  [准确] [有误] [补充说明]
```

提交后在原位置显示：

```text
你已反馈：结果有误
期望结果：不适用
说明：本次没有进行 CT/MRI 检查。
[修改反馈]
```

第一阶段不提供其他账号查看、开发处理状态、开发者备注、待办统计、反馈指派、历史修订时间线、消息通知、附件或导出。

### 1.3 反馈类型

```text
correct    结果准确
incorrect  结果有误
note       补充说明
```

- `correct`：说明可选。
- `incorrect`：期望结果、错误类别、说明必填。
- `note`：说明必填，不暗示原结论错误。

期望结果只允许：

```text
non_compliant
compliant
data_gap
not_applicable
evaluation_unknown
not_executed
```

错误类别只允许：

```text
wrong_status
wrong_reason
wrong_evidence
missing_data_read
wrong_suggestion
rule_definition
other
```

### 1.4 明确不做

- 不修改质控结果的状态、原因码、事实、证据或处理建议。
- 不写入或覆盖 Canonical Envelope。
- 不重新调用规则执行器或 LLM。
- 不设置患者姓名、电话、身份证、住院号、三坐标或病历正文等独立字段，也不接收 Prompt 或模型响应；自由说明仍按下述最小隐私检测失败关闭。
- 不把反馈作为人工金标或模型训练数据。
- 不复用现有 `/api/v1/demo/feedbacks`；该旧接口包含 `medical_text`，身份合同也不适合逐条 Canonical 结果。

## 2. 最小结果绑定合同

前端提交：

```text
root_job_id + record_ref + rule_id
```

服务端必须按这三个字段从 Canonical Envelope 唯一确认该结果存在，再保存反馈。不能把根任务 ID 当成实际子任务 Envelope 的 `job_id` 查询。

失败语义：

- 根任务不存在或用户无权读取：`404`。
- 对应结果不存在：`404`。
- 匹配到重复 Envelope：`409`。
- 反馈表尚未迁移：固定安全文案 `503`，质控结果页仍可正常使用。

该绑定校验仍然保留，因为即使是演示版，也不能把反馈挂到错误规则或错误病例上。

## 3. 最小数据合同

新增表 `qc_result_feedback_demo`，只保存当前反馈，不把它描述为正式审计记录：

```text
id                    UUID / PK
root_job_id           VARCHAR(64) NOT NULL
record_ref            VARCHAR(96) NOT NULL
rule_id               VARCHAR(32) NOT NULL
original_status       VARCHAR(32) NOT NULL
feedback_type         VARCHAR(16) NOT NULL
expected_status       VARCHAR(32) NULL
error_category        VARCHAR(32) NULL
comment               VARCHAR(500) NULL
result_digest         CHAR(64) NOT NULL
created_by            VARCHAR(64) NOT NULL
created_at            TIMESTAMPTZ NOT NULL
updated_at            TIMESTAMPTZ NOT NULL
```

唯一约束：

```text
UNIQUE(root_job_id, record_ref, rule_id, created_by)
```

演示阶段允许该账号修改自己的当前反馈，保留 `created_at`，更新 `updated_at`。不声称具备不可变审计历史；正式发布前如需医院与开发者协作，再单独升级为修订记录。

数据库 `CHECK`：

- 类型和状态字段必须属于受控枚举。
- `incorrect` 必须有期望状态、错误类别和说明。
- `note` 必须有说明。
- `correct` 不允许填写期望状态。

`result_digest` 只绑定受控字段：

```text
rule_id + status + reason_code + customer_display_facts + customer_evidence
```

采用字段白名单、排序后的紧凑 JSON、UTF-8 和 SHA-256。演示阶段不保存完整结果快照，因为页面只回看当前结果和当前反馈，不提供脱离原结果的历史详情页。

## 4. 最小 API

### 4.1 按病历加载反馈

```http
GET /api/v1/qc/sichuan/workspace/result-feedback-demo
    ?root_job_id=...
    &record_ref=...
```

返回该病历按 `rule_id` 索引的当前反馈。结果面板打开时请求一次，禁止 75 张卡片各发一次请求。

### 4.2 保存当前反馈

```http
PUT /api/v1/qc/sichuan/workspace/result-feedback-demo/{rule_id}
```

请求体：

```json
{
  "root_job_id": "...",
  "record_ref": "rec_...",
  "feedback_type": "incorrect",
  "expected_status": "not_applicable",
  "error_category": "wrong_status",
  "comment": "本次未进行该项检查。"
}
```

服务端：

1. 校验演示账号。
2. 唯一解析 Canonical 结果。
3. 从服务端结果读取原状态并计算摘要，不信任前端上传原状态。
4. 校验枚举、条件必填和长度。
5. 对自由文本做最小隐私检测：拒绝明显手机号、身份证号、住院号样式和连续长数字串；错误响应、日志和前端提示不得回显原输入。该检测不宣称能够识别所有姓名或自然语言身份信息。
6. 插入或更新当前账号的当前反馈。

## 5. 前端组件边界

`SingleRecordQcResultPanel.vue` 已超过巨型文件预警线，不继续塞入反馈表单。

新增：

```text
src/views/workstation-v4/customer-sample-validation/QcResultFeedbackControl.vue
src/views/workstation-v4/customer-sample-validation/useQcResultFeedback.ts
src/api/qc-result-feedback-demo.ts
```

- `QcResultFeedbackControl.vue`：单条反馈按钮、内联表单、已提交摘要。
- `useQcResultFeedback.ts`：按病历一次加载、按 `rule_id` 更新本地状态。
- API 模块：严格 DTO 与请求函数。
- `SingleRecordQcResultPanel.vue`：只传入当前结果和对应反馈，接收保存事件。
- `QCRecordCompareWorkbench.vue`：透传已有 `jobId`、`recordRef`，不重新构造身份。

反馈服务错误时显示“反馈暂时无法使用，质控结果仍可正常查看”，不得遮挡或改写结果。

## 6. TDD 实施任务

### Task 1：冻结后端身份和 Canonical 绑定

**Files:**

- Modify: `backend/app/routers/qc_sichuan.py`
- Test: `backend/tests/unit/test_qc_result_feedback_demo.py`

先写红测：演示账号可访问；其他账号返回 `403`；单任务和父子任务均按根任务解析；错误根任务、缺失结果和重复 Envelope 失败关闭。

### Task 2：新增最小表和迁移

**Files:**

- Create: `backend/alembic/versions/<next>_add_qc_result_feedback_demo.py`
- Create: `backend/app/services/qc_workspace/result_feedback_demo_store.py`
- Test: `backend/tests/unit/test_qc_result_feedback_demo.py`

先冻结 CHECK、唯一约束、`TIMESTAMPTZ`、延迟 `503`，再实现 Store。Store 只读 Canonical、只写反馈表。

### Task 3：实现 GET/PUT API

**Files:**

- Modify: `backend/app/routers/qc_sichuan.py`
- Modify: `backend/app/schemas/qc_sichuan.py`
- Test: `backend/tests/unit/test_qc_result_feedback_demo.py`

先写枚举、条件必填、隐私拒绝、服务端原状态和摘要红测，再实现最小接口。

### Task 4：实现独立反馈组件

**Files:**

- Create: `src/api/qc-result-feedback-demo.ts`
- Create: `src/views/workstation-v4/customer-sample-validation/QcResultFeedbackControl.vue`
- Create: `src/views/workstation-v4/customer-sample-validation/useQcResultFeedback.ts`
- Modify: `src/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue`
- Modify: `src/views/workstation-v4/customer-sample-validation/QCRecordCompareWorkbench.vue`
- Test: `tests/unit/views/workstation-v4/QcResultFeedbackControl.spec.ts`

先写红测：准确、有误、补充说明、修改当前反馈、只加载一次、接口失败不遮挡结果、非演示账号不渲染。

### Task 5：聚焦验收

```powershell
python -m pytest backend/tests/unit/test_qc_result_feedback_demo.py -q
npm run test:unit -- QcResultFeedbackControl
npm run type-check
npm run lint
npm run check:encoding
```

浏览器验收：

1. 使用功能演示账号打开一份单病历结果。
2. 对三条不同状态结果分别提交准确、有误和补充说明。
3. 刷新页面，反馈仍在对应规则卡片下显示。
4. 修改反馈，`created_at` 不变、`updated_at` 更新。
5. 接口模拟 `503` 时，75 条质控结果仍完整可读。
6. 登录其他账号时不显示入口，直接调用接口返回 `403`。
7. 数据库没有患者身份独立字段、三坐标和病历正文；明显手机号、身份证号及住院号样式无法提交。

## 7. 第一阶段完成标准

- 功能演示账号能对单条结果反馈并在同页回看。
- 一份病历只发一次反馈读取请求。
- 反馈精确绑定根任务、病历引用和规则编号。
- 反馈不会改变 Canonical、状态、证据、处理建议或 Token。
- 非演示账号无法通过后端访问。
- 自由文本包含明显患者敏感标识时失败关闭。
- 未迁移或反馈服务异常不影响质控结果查看。
- 没有新增开发者工作台、处理状态机、角色体系或第二套质控结果平台。

## 8. 正式化时再评审

以下内容明确延期，不属于演示版完成标准：

- 医院质控科与开发者的权限分离；
- 全院反馈列表、统计和筛选；
- 反馈处理流和开发者备注；
- 不可变修订历史和并发版本；
- 当时结果的客户安全快照；
- 消息通知、导出、反馈转金标。

这些能力只有在演示验证确有使用价值后，才另立正式化计划和数据库迁移，不在当前任务中预埋。
