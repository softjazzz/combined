# 病案首页自动生成（不含 ICD 编码）功能设计说明

> 版本：v0.1（骨架设计）  
> 目标：在不引入诊断/手术编码知识图谱的前提下，只用 LLM + 规则，从全病历自动生成「住院病案首页草稿」（非 ICD 字段），并提供统一 API 供前端展示和后续编码系统调用。

---

## 1. 背景与目标

- 目前首页信息由医生/编码员手工录入，重复劳动多，且易与正文不一致。
- 项目已有：
  - 完整的四川规则质控管线（LLM + 规则）。
  - 部分病历结构化和文书分类能力。
  - 独立的 ICD/手术编码知识图谱系统（未来通过 API 对接）。
- 本轮目标：
  - 在 **medqc-web** 中新增一个「病案首页自动生成草稿」服务，仅覆盖**非 ICD 编码字段**；
  - 对诊断/手术编码字段只输出原文，为后续编码系统提供输入；
  - 提供统一的后端 API，前端可在 Dashboard 中展示首页草稿（包括 A4 打印样式）。

---

## 2. 统一输出结构（FrontPageDraft）

后端定义统一的首页草稿结构，作为从全病历抽取后的主数据模型（不含 ICD 编码）。

```ts
// 仅示意，具体字段可按现有 frontpage JSON 调整
interface FrontPageDraft {
  basic_info: {
    patient_name: string
    gender: '1' | '2'
    gender_text: '男' | '女'
    birth_date: string
    age_years: number
    nationality?: string
    ethnicity?: string
    marital_status?: '1' | '2' | '3' | '4' | '9'
    marital_status_text?: string
    id_number?: string
    occupation?: string
    current_address?: string
    contact_name?: string
    contact_relation?: string
    contact_phone?: string
  }

  hospitalization: {
    hospital_name?: string
    admission_times_in_hospital?: number
    medical_record_no?: string
    payment_method?: string              // 编码值，如 "1"
    payment_method_text?: string         // 文本，如 "城镇职工基本医疗保险"
    admission_way?: string               // 入院途径编码
    admission_way_text?: string          // 入院途径文本
    admission_dept?: string
    admission_ward?: string
    admission_datetime?: string          // "YYYY-MM-DD HH:mm:ss"
    discharge_dept?: string
    discharge_ward?: string
    discharge_datetime?: string
    actual_hospital_days?: number
  }

  diagnoses: {
    // 只存原文，ICD 部分留给编码系统
    ed_diagnosis_texts: string[]             // 门/急诊诊断
    discharge_main_diagnosis_text?: string   // 出院主要诊断
    discharge_other_diagnoses_texts: string[]

    ed_diagnosis_codes?: string[] | null     // 预留给编码服务
    discharge_main_icd?: string | null
    discharge_other_icds?: string[] | null

    admission_condition?: '1' | '2' | '3' | '4' | null  // 入院病情
  }

  procedures: {
    main_procedure_text?: string
    main_procedure_date?: string
    main_procedure_level?: string
    surgeon_name?: string
    assistant1_name?: string
    assistant2_name?: string
    anesthesia_method?: string
    anesthetist_name?: string
    incision_healing_grade?: string

    main_procedure_code?: string | null      // 预留
  }

  other_medical_info: {
    pathology_text?: string
    pathology_no?: string

    drug_allergy_flag?: '1' | '2'
    drug_allergy_flag_text?: string
    drug_allergy_drugs?: string[]

    abo_blood_type?: string                  // "A/B/O/AB/不详/未查"
    rh_blood_type?: string                   // "1/2/3/4"
    rh_blood_type_text?: string              // "阴/阳/不详/未查"

    ventilation_hours?: number               // 机械通气总小时数

    icu_type?: string                        // ICU 类型
    icu_enter_time?: string
    icu_leave_time?: string

    brain_injury_coma_in?: {
      before_admission_hours?: number
      after_admission_hours?: number
    } | null
  }

  staff: {
    dept_director?: string
    chief_physician?: string
    attending_physician?: string
    resident_physician?: string
    responsible_nurse?: string
    coder?: string
  }

  costs: {
    total_cost?: number
    self_paid?: number
    // 24 类费用先从 HIS 聚合，结构可后续补充
  }

  // 证据与置信度，辅助人工复核
  evidence?: Record<string, string>      // 每个字段的原文片段
  confidence?: Record<string, number>    // 每个字段的置信度 0~1
}
```

这个结构既服务于：

- 前端首页草稿编辑页面；
- A4 打印样式（`FrontPageDemoView`）；
- 后续与编码系统对接时的输入（只需把 diagnoses/procedures 中的文本字段丢给编码 API）。

---

## 3. API 设计（骨架）

### 3.1 自动生成首页草稿

- **URL**：`POST /api/v1/frontpage/auto-generate-draft`
- **说明**：
  - 输入一次住院的 ID 或文书列表；
  - 后端从 EMR/HIS 拉取全病历，调用 LLM/NLP 抽取非 ICD 字段；
  - 输出 `FrontPageDraft`（ICD 字段为 `null` 或省略）。

#### 请求体

```jsonc
// 模式一：按住院号 / visit_id 触发（推荐）
{
  "visit_id": "ZY2025-0001"
}

// 模式二：直接传文书列表（便于测试）
{
  "documents": [
    {
      "type": "admission_record",
      "content": "入院记录全文...",
      "meta": { "created_at": "2025-10-15 14:30:00" }
    },
    {
      "type": "discharge_record",
      "content": "出院记录全文...",
      "meta": { "created_at": "2025-10-28 10:00:00" }
    },
    {
      "type": "operation_record",
      "content": "手术记录全文...",
      "meta": { "performed_at": "2025-10-20 09:30:00" }
    }
    // ...
  ]
}
```

#### 响应体（成功）

```jsonc
{
  "success": true,
  "data": {
    "frontpage": { /* FrontPageDraft */ },
    "visit": { /* 可选：统一 Visit 结构，后续统计/上报用 */ }
  },
  "message": "自动生成病案首页草稿成功"
}
```

#### 响应体（失败）

```jsonc
{
  "success": false,
  "error": "LLM 调用失败：...",
  "trace_id": "..."       // 复用现有追踪 ID 方案
}
```

> **注意**：本阶段不调用任何 ICD 编码 API，`diagnoses.*icd*` 与 `procedures.main_procedure_code` 字段由编码系统后续补全。

---

## 4. 抽取流程（仅 LLM + 轻规则）

### 4.1 文书准备

1. 从现有接口获取文书：
   - `GET /api/v1/medical-records/{visit_id}/documents`
   - 按 `document_type` 分类：入院记录、出院记录、急诊记录、手术记录、麻醉记录、ICU 病程、病理报告等。
2. 组合为 `documents: [{type, content, meta}, ...]`，传给抽取服务。

### 4.2 按模块拆分 LLM 调用

为保证可控性，不采用“一次 Prompt 生成全首页”，而是按模块拆分：

- 模块 A：基本信息 & 住院信息（如有 HIS 结构化数据，可只做校对）。
- 模块 B：诊断原文 + 入院病情（不含 ICD）。
- 模块 C：手术/操作信息（名称/日期/级别/术者/助手/麻醉等，不含编码）。
- 模块 D：其他医疗信息（病理、药物过敏、血型、ICU、呼吸机、昏迷时间等）。
- 模块 E：人员信息。

每个模块：

1. 选择相关文书（例如：模块 B 只看急诊/入院/出院记录）。
2. 用 **强约束 Prompt** + JSON 输出格式执行一次 LLM 调用。
3. 将结果合并到 `FrontPageDraft` 对应字段。

示例：模块 B（诊断 + 入院病情） Prompt 片段：

```text
你是一名熟悉中国病案首页规范的病案信息员，只负责抽取诊断“原文”，不做 ICD 编码。

【可用文书】
- 门/急诊记录：
{ed_text}
- 入院记录：
{admission_text}
- 出院记录：
{discharge_text}

【任务】
1. 找出门/急诊诊断的原文（可能多条）。
2. 找出出院主要诊断的原文。
3. 找出其他出院诊断的原文列表（不含主要诊断）。
4. 根据入院时病情描述判断入院病情（仅输出 1/2/3/4）：
   1=有，2=临床未确定，3=情况不明，4=无。

【输出要求】
以 JSON 格式输出：
{
  "ed_diagnosis_texts": ["..."],
  "discharge_main_diagnosis_text": "...",
  "discharge_other_diagnoses_texts": ["...", "..."],
  "admission_condition": "1" | "2" | "3" | "4"
}
```

其他模块类似，只返回原文字段，不涉及编码。

### 4.3 轻量规则校验（不依赖知识图谱）

为了提升稳定性，增加少量**纯业务规则**校验（不涉及疾病知识）：

- 入出院时间、科别优先从 HIS 结构化数据读取；LLM 结果仅作参考。
- 年龄用出生日期与入院日期计算，与 LLM 输出不一致时标记为“需复核”。
- 枚举字段（入院病情、婚姻、血型、Rh、药物过敏标志等）严格限制在固定取值之外，非法值记为 `null` 并提示人工填写。
- 时间字段要求符合 `YYYY-MM-DD HH:mm:ss` 格式，否则置空。

这些校验逻辑可集中写在 `frontpage_extraction_service` 中，保证 LLM 输出的可用性和可预期性。

---

## 5. 与 ICD 编码系统的衔接（后续）

虽然本设计不实现编码，但为后续对接预留好接口与字段：

1. `FrontPageDraft.diagnoses` 中保留诊断原文数组：
   - `ed_diagnosis_texts`
   - `discharge_main_diagnosis_text`
   - `discharge_other_diagnoses_texts`
2. `FrontPageDraft.procedures` 中保留手术原文：
   - `main_procedure_text`
   - `other_procedures_texts`（可后续补充）
3. 将来可新增编码服务：

```http
POST /api/v1/coding/icd
{
  "diagnoses": ["右肺腺癌（早期）", "高血压 3 级 极高危"],
  "procedures": ["腹腔镜阑尾切除术"]
}
```

返回 ICD-10/手术编码后，更新 `FrontPageDraft` 中对应的 `*icd*` / `*code` 字段。

---

## 6. 代码骨架规划

### 6.1 后端目录规划

- `apps/medqc-web/backend/app/services/frontpage_extraction_service.py`
  - `class FrontPageExtractionService:`
    - `async def generate_draft_from_visit(visit_id: str) -> FrontPageDraft`
    - `async def generate_draft_from_documents(docs: List[Document]) -> FrontPageDraft`
  - 内部拆分多个私有方法：`_extract_basic_info`, `_extract_hospitalization`, `_extract_diagnoses`, `_extract_procedures`, `_extract_other_info`, `_extract_staff`。

- `apps/medqc-web/backend/app/routers/frontpage.py`
  - `@router.post("/api/v1/frontpage/auto-generate-draft")`
  - 输入 `visit_id` 或 `documents`，调用 `FrontPageExtractionService` 返回 `FrontPageDraft`。

- LLM 调用可复用现有 `app/core/http.py` 或 `app/services/llm_client.py` 中的能力，后续再具体接线。

### 6.2 前端改造（后续任务）

- `FrontPageDemoView.vue`：
  - 目前从 `/api/v1/demo/frontpage-demo` 读取静态 JSON；
  - 后续可增加一个“用真实接口生成”按钮：
    - 调用 `/api/v1/frontpage/auto-generate-draft` 拿到草稿；
    - 渲染到现有的 A4 打印样式上。

---

## 7. 迭代计划

1. **Step 1：后端骨架**（当前目标）
   - 定义 `FrontPageDraft` Pydantic 模型。
   - 建立 `FrontPageExtractionService` 和 `POST /api/v1/frontpage/auto-generate-draft` 路由（内部可以先返回模拟数据或基于 demo JSON）。

2. **Step 2：真实抽取接入（仅 LLM）**
   - 按模块拆 Prompt，打通 demo 病例的真实抽取流程。
   - 为每个字段补充证据片段和置信度。

3. **Step 3：与编码系统对接**
   - 增加 `/api/v1/frontpage/apply-coding` 或在生成草稿时可选调用编码 API。
   - 编码系统负责返回 ICD/手术编码，填入 `FrontPageDraft` 中对应字段。

4. **Step 4：上线前优化**
   - 增加更多规则校验（空值检测、逻辑一致性检查）。
   - 与现有 LX/LXE 质控规则联动，自动检查“首页字段 vs 正文”的一致性。

---

本文件仅描述「不含 ICD 编码」的病案首页自动生成方案。后续实现时，可在此基础上补充具体数据表映射、Prompt 模版和 LLM 调用细节。 

