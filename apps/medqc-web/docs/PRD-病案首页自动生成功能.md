# PRD - 病案首页自动生成功能

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2025-01-19 |
| 文档状态 | 草稿 |

## 目录

1. [产品概述](#1-产品概述)
2. [需求分析](#2-需求分析)  
3. [功能需求详细设计](#3-功能需求详细设计)
4. [技术方案](#4-技术方案)
5. [数据模型设计](#5-数据模型设计)
6. [用户界面设计](#6-用户界面设计)
7. [实施计划](#7-实施计划)
8. [成功指标](#8-成功指标)

---

## 1. 产品概述

### 1.1 产品背景

病案首页是医疗机构上报卫健委和医保部门的核心数据，包含患者基本信息、诊断、手术、费用等关键信息。

**现状痛点**：
- ❌ 医生工作负担重：手工填写病案首页耗时15-30分钟/份
- ❌ 数据质量不稳定：人工填写易出错，信息遗漏、编码错误常见
- ❌ 上报要求复杂：需同时满足医保和卫健委两个部门的不同上报格式
- ❌ 信息冗余录入：全病历中已有的信息需要重复提取和录入

### 1.2 产品目标

**核心目标**：基于全病历自动生成符合规范的病案首页，减少医生填写时长80%以上

**具体目标**：
1. ✅ 自动从全病历中提取并填写病案首页90%以上的字段
2. ✅ 支持ICD-10诊断编码和ICD-9-CM-3手术编码的智能推荐
3. ✅ 同时支持医保结算待遇清单和卫健委病案首页两种格式
4. ✅ 提供医生审核和手工修正机制，确保数据准确性
5. ✅ 建立质控反馈机制，持续优化提取准确率

### 1.3 目标用户

| 用户角色 | 使用场景 | 核心需求 |
|---------|---------|---------|
| **临床医生** | 患者出院时填写病案首页 | 快速、准确、少手工录入 |
| **病案编码员** | 审核和完善病案首页编码 | 智能编码建议、便捷修改 |
| **医保办工作人员** | 医保结算清单上报 | 符合医保要求的数据格式 |
| **病案室管理员** | 卫健委病案首页上报 | 符合卫健委规范的数据格式 |
| **质控人员** | 病案质量检查 | 自动质控、异常提醒 |

---

## 2. 需求分析

### 2.1 上报场景分析

本功能需支持以下三个上报场景：

| 场景 | 主管部门 | 数据格式 | 核心字段 | 上报频率 |
|-----|---------|---------|---------|---------|
| **场景1：医保结算** | 医保局 | 医保结算待遇清单 | 费用明细、诊断、手术、医保信息 | 实时/日报 |
| **场景2：卫健委病案首页** | 卫健委 | 国家标准病案首页 | 完整28页住院病案首页 | 月报/季报 |
| **场景3：医保病案首页** | 医保局 | 医保版病案首页 | 医保版首页（部分字段不同） | 月报 |

### 2.2 病案首页数据结构

参考演示案例 `backend/app/data/frontpage_demo_case.json`，病案首页包含以下核心模块：

```json
{
  "basic_info": {},           // 患者基本信息
  "hospitalization": {},      // 住院信息
  "diagnosis_and_procedures": {}, // 诊断和手术
  "other_medical_info": {},   // 其他医疗信息
  "staff": {},                // 人员信息  
  "costs": {}                 // 费用信息
}
```

---

## 3. 功能需求详细设计

### 3.1 功能模块总览

| 功能编号 | 功能模块 | 优先级 | 复杂度 | 预计工时 |
|---------|---------|--------|--------|---------|
| F1 | 患者基本信息自动提取 | P0 | 中 | 3天 |
| F2 | 住院相关信息提取 | P0 | 低 | 2天 |
| F3 | 诊断信息提取 | P0 | 高 | 4天 |
| F4 | 入院病情自动推理 | P0 | 高 | 3天 |
| F5 | ICD-10诊断编码推荐 | P0 | 高 | 5天 |
| F6 | 手术信息提取 | P0 | 中 | 3天 |
| F7 | ICD-9-CM-3手术编码推荐 | P0 | 高 | 4天 |
| F8 | 其他医疗信息提取 | P1 | 中 | 3天 |
| F9 | 人员信息提取 | P1 | 低 | 2天 |
| F10 | 费用信息汇总 | P1 | 低 | 2天 |
| F11 | 病案首页导出（3种格式） | P0 | 中 | 4天 |
| F12 | 前端编辑界面 | P0 | 中 | 5天 |
| F13 | 疾病诊断和手术操作画像 | P0 | 高 | 5天 |

### 3.2 F1：患者基本信息自动提取

#### 3.2.1 功能描述

从全病历（优先入院记录）中自动提取患者基本信息，包括身份信息、地址、联系方式等。

#### 3.2.2 提取字段清单

| 字段分类 | 字段名 | 字段代码 | 数据类型 | 必填 | 提取来源 | 提取方法 |
|---------|-------|---------|---------|-----|---------|---------|
| **身份信息** | 姓名 | patient_name | string | ✓ | 入院记录 | NER实体识别 |
| **身份信息** | 性别 | gender | string(1) | ✓ | 入院记录 | 关键词："男"→"1", "女"→"2" |
| **身份信息** | 出生日期 | birth_date | date | ✓ | 入院记录 | 日期实体识别 |
| **身份信息** | 年龄 | age_years | integer | ✓ | 入院记录/计算 | 数字提取或计算 |
| **身份信息** | 国籍 | nationality | string(50) | ✓ | 入院记录 | 默认"中国" |
| **身份信息** | 民族 | ethnicity | string(20) | ✓ | 入院记录 | 民族实体识别 |
| **身份信息** | 身份证号 | id_number | string(18) | ✓ | 入院记录 | 18位正则: `^\d{17}[\dX]$` |
| **身份信息** | 职业 | occupation | string(50) | ✓ | 入院记录 | 职业实体识别 |
| **身份信息** | 婚姻状况 | marital_status | string(1) | ✓ | 入院记录 | 关键词匹配 |
| **出生信息** | 新生儿出生体重 | newborn_birth_weight | integer | 条件 | 产科记录 | 数字+单位(克/g) |
| **出生信息** | 新生儿入院体重 | newborn_admission_weight | integer | 条件 | 新生儿记录 | 数字+单位(克/g) |
| **地址信息** | 出生地 | birth_place | json | ✓ | 入院记录 | 地址实体识别 |
| **地址信息** | 籍贯 | native_place | json | ✓ | 入院记录 | 地址实体识别 |
| **地址信息** | 现住址 | current_address | json | ✓ | 入院记录 | 地址实体识别 |
| **地址信息** | 户口地址 | household_address | json | ○ | 入院记录 | 地址实体识别 |
| **工作信息** | 工作单位 | work_unit | json | ○ | 入院记录 | 文本提取 |
| **联系方式** | 电话 | phone | string(20) | ✓ | 入院记录 | 电话正则: `1[3-9]\d{9}` |
| **联系方式** | 邮编 | postal_code | string(6) | ○ | 入院记录 | 6位数字正则 |
| **紧急联系人** | 联系人信息 | emergency_contact | json | ✓ | 入院记录 | 综合提取 |

#### 3.2.3 输出数据结构

```typescript
interface PatientBasicInfo {
  patient_name: string
  gender: "1" | "2"  // 1-男 2-女
  birth_date: string  // YYYY-MM-DD
  age_years: number
  nationality: string
  ethnicity: string
  id_number: string  // 18位
  occupation: string
  marital_status: "1" | "2" | "3" | "4" | "9"  // 1-未婚 2-已婚 3-丧偶 4-离婚 9-其他
  
  birth_place: {
    province: string
    city: string
    county?: string
  }
  
  native_place: {
    province: string
    city: string
  }
  
  current_address: {
    province: string
    city: string
    district: string
    detail: string
    phone?: string
    postal_code?: string
  }
  
  household_address?: {...}
  work_unit?: {
    name: string
    address?: string
    phone?: string
    postal_code?: string
  }
  
  emergency_contact: {
    name: string
    relationship: string  // 1-配偶 2-子 3-女 ...
    address?: string
    phone: string
  }
  
  newborn_info?: {
    birth_weight: number | null  // 克
    admission_weight: number | null  // 克
  }
}
```

#### 3.2.4 LLM提示词模板

```markdown
# 任务
从病历文本中提取患者基本信息。

# 病历文本
{admission_record}

# 输出要求
请严格按照以下JSON格式输出，不要添加任何额外说明：

\`\`\`json
{
  "patient_name": "患者姓名",
  "gender": "1",  // 1-男 2-女
  "birth_date": "YYYY-MM-DD",
  "age_years": 整数,
  ...
}
\`\`\`

# 提取规则
1. 日期格式统一为 YYYY-MM-DD
2. 性别：男→"1", 女→"2"
3. 找不到的字段填 null
4. 身份证号必须18位
5. 电话号码只提取数字，去除分隔符
6. 体重单位统一为克(g)
```

#### 3.2.5 验收标准

- 必填字段提取准确率 ≥ 95%
- 身份证号格式校验通过率 100%
- 地址结构化准确率 ≥ 90%
- 单次提取耗时 < 5秒

---

### 3.3 F3：诊断信息提取（核心功能）

#### 3.3.1 功能描述

从病历中提取门急诊诊断、出院主要诊断和其他诊断，是病案首页的核心内容。

#### 3.3.2 诊断类型

| 诊断类型 | 提取来源 | 编码要求 | 说明 |
|---------|---------|---------|------|
| **门（急）诊诊断** | 入院记录"门诊诊断"部分 | ICD-10 | 患者入院前的初步诊断 |
| **主要诊断** | 出院记录"出院诊断"第一条 | ICD-10 | 对健康危害最大、花费资源最多的疾病 |
| **其他诊断** | 出院记录"出院诊断"其余 | ICD-10 | 并发症、合并症 |

#### 3.3.3 主要诊断选择原则

根据《住院病案首页填写说明》，主要诊断应选择：

1. **内科**：对身体健康危害最大、花费医疗资源最多、住院时间最长的疾病
2. **外科**：患者住院接受手术进行治疗的疾病
3. **产科**：产科的主要并发症或伴随疾病

#### 3.3.4 提取策略

```
步骤1：定位"门诊诊断"/"急诊诊断"章节
  → 使用关键词定位：r"门诊诊断[：:]|急诊诊断[：:]"

步骤2：提取诊断列表
  → 识别序号模式：1. 2. 3. 或 (1) (2) (3)
  → 或按行分割（如无序号）

步骤3：诊断文本标准化
  → 去除括号内容：(早期)、（疑似）
  → 去除不确定标记：？、疑、待查

步骤4：区分主要诊断和其他诊断
  → 第一条 → 主要诊断
  → 其余 → 其他诊断

步骤5：识别并发症
  → 查找关键词："并发"、"继发"、"合并"
  → 标记 is_complication = true
```

#### 3.3.5 输出数据结构

```typescript
interface DiagnosisInfo {
  // 门急诊诊断
  ed_diagnosis: Array<{
    text: string
    icd10?: string  // ICD-10编码（由编码模块填充）
    confidence: number
    is_tcm: boolean  // 是否中医诊断
  }>
  
  // 主要诊断
  discharge_main_diagnosis: {
    text: string
    icd10?: string
    confidence: number
    admission_condition?: number  // 入院病情 1-4（由推理模块填充）
    admission_condition_reasoning?: string
  }
  
  // 其他诊断
  discharge_other_diagnoses: Array<{
    text: string
    icd10?: string
    sequence: number  // 顺序
    is_complication: boolean  // 是否并发症
    confidence: number
    admission_condition?: number
    admission_condition_reasoning?: string
  }>
}
```

---

### 3.4 F4：入院病情自动推理（核心难点）

#### 3.4.1 功能描述

对每个出院诊断，通过对比入院记录和病程记录，自动推理其入院时的病情状态。

#### 3.4.2 入院病情分类标准

根据《住院病案首页填写说明》附件2：

| 代码 | 名称 | 定义 | 典型示例 |
|-----|------|------|---------|
| **1** | 有 | 入院时已明确诊断 | 入院记录："急性心肌梗死"，出院诊断："急性心肌梗死" |
| **2** | 临床未确定 | 入院时临床未确定或可疑 | 入院记录："乳腺癌？"，出院诊断："乳腺癌" |
| **3** | 情况不明 | 窗口期或潜伏期 | 入院记录无提及，但为乙肝窗口期、肺炎潜伏期 |
| **4** | 无 | 住院期间新发生 | 入院记录无此诊断，病程记录第5天出现："术后心衰" |

#### 3.4.3 推理算法

```python
def infer_admission_condition(
    discharge_diagnosis: str,
    admission_record: str,
    progress_notes: list[str]
) -> tuple[int, str]:
    """
    推理入院病情
    
    Returns:
        (condition_code, reasoning)
    """
    # 步骤1：从入院记录中提取诊断
    admission_diagnoses = extract_diagnoses_from_admission(admission_record)
    
    # 步骤2：精确匹配
    for adm_diag in admission_diagnoses:
        similarity = calculate_similarity(discharge_diagnosis, adm_diag.text)
        
        if similarity > 0.9:  # 高度匹配
            if has_uncertainty_markers(adm_diag.text):  # 有"？"、"疑"等
                return 2, f"入院记录中诊断为'{adm_diag.text}'，标记为疑诊"
            else:
                return 1, f"入院记录中已明确诊断为'{adm_diag.text}'"
    
    # 步骤3：模糊匹配（同类疾病）
    for adm_diag in admission_diagnoses:
        if is_related_disease(discharge_diagnosis, adm_diag.text):
            if has_uncertainty_markers(adm_diag.text):
                return 2, f"入院记录中有相关疑诊'{adm_diag.text}'"
            else:
                return 1, f"入院记录中有相关诊断'{adm_diag.text}'"
    
    # 步骤4：检查窗口期/潜伏期疾病
    if is_window_period_disease(discharge_diagnosis):
        return 3, f"{discharge_diagnosis}可能处于窗口期或潜伏期"
    
    # 步骤5：在病程记录中查找首次出现
    first_mention = find_first_mention_in_progress(discharge_diagnosis, progress_notes)
    if first_mention:
        days_after_admission = first_mention.days_from_admission
        if days_after_admission > 0:
            return 4, f"病程记录第{days_after_admission}天首次提及，为住院期间新发"
    
    # 默认：无法确定，建议人工审核
    return 2, "无法明确判断，建议人工确认"


def has_uncertainty_markers(text: str) -> bool:
    """检查是否有不确定性标记"""
    markers = ["？", "?", "疑", "待查", "待排", "不除外", "考虑"]
    return any(marker in text for marker in markers)


def is_window_period_disease(diagnosis: str) -> bool:
    """判断是否为窗口期/潜伏期疾病"""
    window_diseases = [
        "乙型病毒性肝炎",
        "丙型病毒性肝炎", 
        "艾滋病",
        "肺炎",  # 潜伏期
        "肺结核",  # 潜伏期
    ]
    return any(disease in diagnosis for disease in window_diseases)
```

#### 3.4.4 推理示例

| 出院诊断 | 入院记录 | 病程记录 | 推理结果 | 推理依据 |
|---------|---------|---------|---------|---------|
| 急性心肌梗死 | "急性心肌梗死" | - | **1-有** | 入院记录中已明确 |
| 肺炎 | "肺炎？" | - | **2-临床未确定** | 入院记录标记为疑诊 |
| 乙型肝炎 | 无提及 | 无提及 | **3-情况不明** | 可能处于窗口期 |
| 心力衰竭 | 无提及 | 第5天："术后心衰" | **4-无** | 住院期间新发 |
| 肺腺癌 | "肺部占位？" | 第3天："病理确诊肺腺癌" | **2-临床未确定** | 入院时为疑诊 |

#### 3.4.5 验收标准

- 推理准确率 ≥ 80%（专家评审）
- "有"和"无"的判断准确率 ≥ 90%
- 推理依据清晰、可解释

---

### 3.5 F5：ICD-10诊断编码推荐

#### 3.5.1 功能描述

为每个诊断推荐最匹配的ICD-10编码（Top 3候选），辅助编码员快速选择。

#### 3.5.2 编码库来源

- 使用国家标准ICD-10编码库（约2万条）
- 数据表：`icd10_codes`（已在DRG模块中定义）

#### 3.5.3 编码推荐算法

```
输入：诊断文本（如"急性前壁ST段抬高型心肌梗死"）
      临床上下文（性别、年龄、科室）

步骤1：文本预处理
  → 去除括号：(早期) → ""
  → 去除修饰词：急性、慢性、重度等保留
  → 标准化：统一简繁体

步骤2：编码库匹配（多策略）
  
  策略1：精确匹配
    SELECT * FROM icd10_codes 
    WHERE name = '{诊断文本}'
    → 置信度：0.95-1.0
  
  策略2：前缀匹配
    SELECT * FROM icd10_codes 
    WHERE name LIKE '{核心关键词}%'
    → 置信度：0.80-0.95
  
  策略3：模糊匹配（Levenshtein距离）
    SELECT *, levenshtein(name, '{诊断文本}') as distance
    FROM icd10_codes
    WHERE distance < 5
    ORDER BY distance
    → 置信度：0.60-0.85
  
  策略4：语义匹配（向量相似度，可选）
    SELECT *, cosine_similarity(embedding, query_embedding) as sim
    FROM icd10_codes_vectors
    WHERE sim > 0.7
    ORDER BY sim DESC
    → 置信度：0.50-0.80

步骤3：临床上下文过滤
  → 性别限定：过滤不适用的编码（如男性不适用妊娠相关）
  → 年龄限定：过滤不适用的编码（如新生儿特有疾病）
  → 科室限定：优先本科室常见编码

步骤4：排序并返回Top 3
  → 按置信度排序
  → 返回编码、名称、置信度、推理说明
```

#### 3.5.4 输出数据结构

```typescript
interface ICDRecommendation {
  diagnosis_text: string
  context: {
    gender?: "M" | "F"
    age?: number
    department?: string
  }
  recommendations: Array<{
    code: string  // ICD-10编码，如"I21.001"
    name: string  // 编码名称
    confidence: number  // 0.0-1.0
    match_method: "exact" | "prefix" | "fuzzy" | "semantic"
    reasoning: string  // 推理说明
  }>
}
```

#### 3.5.5 编码推荐示例

**输入**：
```json
{
  "diagnosis_text": "急性前壁ST段抬高型心肌梗死",
  "context": {
    "gender": "M",
    "age": 65,
    "department": "心内科"
  }
}
```

**输出**：
```json
{
  "recommendations": [
    {
      "code": "I21.001",
      "name": "急性前壁ST段抬高型心肌梗死",
      "confidence": 0.98,
      "match_method": "exact",
      "reasoning": "完全匹配，ICD-10标准编码"
    },
    {
      "code": "I21.901",
      "name": "急性心肌梗死，未特指",
      "confidence": 0.75,
      "match_method": "prefix",
      "reasoning": "上级编码，适用于部位不明确时"
    },
    {
      "code": "I25.201",
      "name": "陈旧性心肌梗死",
      "confidence": 0.30,
      "match_method": "semantic",
      "reasoning": "相关疾病，但时间状态不符（陈旧 vs 急性）"
    }
  ]
}
```

---

## 4. 技术方案

### 4.1 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端层 (Vue 3)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │病案首页编辑  │  │智能提取界面  │  │编码建议界面  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                           ↓ ↑
┌─────────────────────────────────────────────────────────┐
│                   API层 (FastAPI)                        │
│  POST /api/frontpage/extract          - 开始提取         │
│  GET  /api/frontpage/task/{id}        - 查询任务状态     │
│  POST /api/frontpage/coding/suggest   - 编码建议         │
│  POST /api/frontpage/export           - 导出             │
└─────────────────────────────────────────────────────────┘
                           ↓ ↑
┌─────────────────────────────────────────────────────────┐
│                  服务层 (Services)                       │
│  ┌─────────────────────────────────────────────────┐    │
│  │  FrontPageExtractionService                     │    │
│  │  ├─ extract_patient_info()                      │    │
│  │  ├─ extract_diagnosis_info()                    │    │
│  │  ├─ infer_admission_condition()                 │    │
│  │  ├─ extract_procedure_info()                    │    │
│  │  └─ extract_other_info()                        │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  CodingRecommendationService                    │    │
│  │  ├─ recommend_icd10(diagnosis_text)             │    │
│  │  └─ recommend_icd9cm3(procedure_text)           │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                           ↓ ↑
┌─────────────────────────────────────────────────────────┐
│                   AI能力层 (LLM)                         │
│  DeepSeek V3 / Qwen-Max   +   ICD编码库                  │
└─────────────────────────────────────────────────────────┘
                           ↓ ↑
┌─────────────────────────────────────────────────────────┐
│               数据存储层 (Supabase PostgreSQL)           │
│  - case_front_page (病案首页)                            │
│  - case_front_page_diagnoses (诊断)                      │
│  - case_front_page_procedures (手术)                     │
│  - front_page_extraction_tasks (提取任务)                │
│  - icd10_codes (ICD-10编码库)                            │
│  - icd9_procedures (ICD-9-CM-3编码库)                    │
└─────────────────────────────────────────────────────────┘
```

### 4.2 LLM提示词工程

#### 4.2.1 分步提取策略

```
步骤1：患者基本信息提取      (预计耗时: 3-5秒)
步骤2：诊断信息提取          (预计耗时: 5-8秒)
步骤3：入院病情推理          (预计耗时: 3-5秒)
步骤4：手术信息提取          (预计耗时: 3-5秒)
步骤5：其他医疗信息提取      (预计耗时: 2-4秒)
步骤6：人员信息提取          (预计耗时: 1-2秒)
步骤7：ICD编码推荐           (预计耗时: 5-8秒)

总耗时：约 22-37秒
优化后（并行）：约 15-25秒
```

#### 4.2.2 提示词优化策略

1. **结构化输出**：要求LLM严格输出JSON格式
2. **Few-Shot示例**：提供2-3个标准示例
3. **分步推理**：复杂任务分解为多个子任务
4. **上下文控制**：限制输入长度，提取关键段落
5. **温度参数调优**：提取任务使用temperature=0.1，保证稳定性

---

## 5. 数据模型设计

### 5.1 核心数据表

参考：`backend/app/data/frontpage_demo_case.json`

#### 5.1.1 病案首页表 (case_front_page)

基于现有DRG模块的表结构，扩展字段以支持完整病案首页。

**核心字段**：
- `basic_info` (JSONB): 患者基本信息
- `hospitalization` (JSONB): 住院信息
- `diagnosis_and_procedures` (JSONB): 诊断和手术
- `other_medical_info` (JSONB): 其他医疗信息
- `staff` (JSONB): 人员信息
- `costs` (JSONB): 费用信息
- `ai_extraction_result` (JSONB): AI完整提取结果
- `ai_extraction_confidence` (DECIMAL): 整体置信度
- `manual_corrections` (JSONB): 人工修正记录

#### 5.1.2 AI提取任务表 (front_page_extraction_tasks)

```sql
CREATE TABLE front_page_extraction_tasks (
  task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  admission_id VARCHAR(50),
  medical_record_id UUID,
  
  status VARCHAR(20) DEFAULT 'pending',  -- pending/processing/completed/failed
  progress INTEGER DEFAULT 0,  -- 0-100
  
  -- 各步骤提取结果
  extraction_steps JSONB DEFAULT '[]',
  -- 示例：[
  --   {"step": 1, "name": "患者基本信息", "status": "completed", "duration_ms": 3200, "confidence": 0.92},
  --   {"step": 2, "name": "诊断信息", "status": "completed", "duration_ms": 5800, "confidence": 0.88},
  --   ...
  -- ]
  
  total_tokens_used INTEGER,
  total_processing_time_ms INTEGER,
  
  error_message TEXT,
  error_stack TEXT,
  
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP
);

CREATE INDEX idx_extraction_tasks_admission ON front_page_extraction_tasks(admission_id);
CREATE INDEX idx_extraction_tasks_status ON front_page_extraction_tasks(status);
```

---

## 6. 用户界面设计

### 6.1 主界面（三栏布局）

```
┌────────────────────────────────────────────────────────────┐
│                       顶部操作栏                            │
│  [开始提取] [保存草稿] [提交审核] [导出医保] [导出卫健委]   │
│  进度：██████████░░░░  75%  |  用时：18秒                   │
└────────────────────────────────────────────────────────────┘
┌──────────┬───────────────────────┬──────────────────────┐
│ 左：原文  │ 中：提取结果           │ 右：AI建议            │
│ (30%)    │ (45%)                 │ (25%)                │
├──────────┼───────────────────────┼──────────────────────┤
│ [全病历] │ ┌─ 患者基本信息 ─┐    │ ┌─ 诊断编码建议 ─┐   │
│          │ │ ✓ 姓名: 张伟    │    │ │ 主要诊断:       │   │
│ 入院记录▼│ │ ✓ 性别: 男      │    │ │ 右肺腺癌        │   │
│ ├─基本信息│ │ ✓ 年龄: 44     │    │ │                 │   │
│ ├─主诉    │ │ ✓ 身份证: ***  │    │ │ C34.9 (95%) ✓   │   │
│ └─现病史  │ └────────────────┘    │ │ C34.8 (72%)     │   │
│          │                       │ │ [查看详情]      │   │
│ 病程记录▶│ ┌─ 诊断信息 ─────┐    │ └─────────────────┘   │
│          │ │ ⚠ 主要诊断:     │    │                      │
│ 手术记录▶│ │ 右肺腺癌(早期)  │    │ ┌─ 质量检查 ────┐   │
│          │ │ ICD-10: C34.9   │    │ │ ✓ 必填项完整   │   │
│ 出院记录▶│ │ 入院病情: 1(有) │    │ │ ⚠ 2项需确认    │   │
│          │ │ [编辑]          │    │ │ ✗ 1个编码异常  │   │
│          │ └────────────────┘    │ └─────────────────┘   │
│ [高亮定位]│                       │                      │
└──────────┴───────────────────────┴──────────────────────┘
```

**字段状态标识**：
- ✓ 绿色：高置信度（≥90%），自动采纳
- ⚠ 黄色：中置信度（60%-90%），需人工确认
- ✗ 红色：低置信度（<60%）或提取失败，需手工填写
- 🔒 灰色：HIS系统数据，不可编辑

---

## 7. 实施计划

### 7.1 开发阶段（总工期：11周）

| 周次 | 阶段 | 主要任务 | 交付物 |
|-----|------|---------|--------|
| W1 | 基础设施 | 数据库表设计、API框架、LLM集成 | 可运行的基础框架 |
| W2-W3 | 核心提取1 | 患者信息、诊断信息提取 | F1, F3完成 |
| W4 | 核心提取2 | 入院病情推理 | F4完成 |
| W5-W6 | 编码推荐 | ICD-10/ICD-9-CM-3编码库和推荐 | F5, F7完成 |
| W7 | 手术和其他 | 手术、人员、费用、其他信息提取 | F6, F8, F9, F10完成 |
| W8-W9 | 前端开发 | 病案首页编辑界面、提取进度界面 | F12完成 |
| W10 | 导出功能 | 医保清单、卫健委首页、医保首页导出 | F11完成 |
| W11 | 测试优化 | 集成测试、提示词优化、准确率提升 | 测试报告 |

### 7.2 上线计划

1. **内测**（1周）：5-10名医生试用
2. **灰度**（2周）：2-3个科室使用
3. **全量**（1周）：全院推广

---

### 3.8 F13：疾病诊断和手术操作画像

#### 3.8.1 功能描述

基于医院整体电子病历，自动构建患者的“疾病诊断和手术操作画像”，通过可视化时间轴和闭环验证机制，辅助医生在书写首页时进行查漏补缺。

#### 3.8.2 核心能力

**1. 诊断发生发展时间轴**
*   **目标**：清晰展示患者病情变化轨迹，防止漏填过程中的重要并发症。
*   **逻辑**：
    *   聚合全病历（入院记录、病程记录、检验检查、医嘱、出院记录）中的诊断实体。
    *   提取每个诊断的“首次出现时间”、“确诊时间”和“转归状态”。
    *   构建时间轴：`入院 -> 初步诊断 -> 检查确诊 -> 治疗/手术 -> 并发症 -> 出院诊断`。

**2. 手术操作闭环验证**
*   **目标**：解决“手术漏填”或“计划未做却误填”的问题。
*   **逻辑**：
    *   **计划源**：提取“术前小结”、“手术审批单”、“长期/临时医嘱”（如备皮、禁食）。
    *   **执行源**：提取“手术记录”、“麻醉记录”、“手术护理记录”。
    *   **验证状态**：
        *   `MATCH`（匹配）：计划且执行 -> 自动填入。
        *   `PLANNED_NOT_DONE`（计划未执行）：提示医生确认（可能是取消手术）。
        *   `DONE_NOT_PLANNED`（执行无计划）：提示医生补充审批文书（属于质控缺陷）。

**3. 首页书写差异分析**
*   **目标**：实时校验首页已填内容与病历画像的一致性。
*   **纠错类型**：
    *   **漏填提醒**：病历画像中有明确依据（如手术记录已存），但这首页未填写。
    *   **无据提醒**：首页填写了某诊断，但在病历文书中找不到支持依据。
    *   **不一致提醒**：首页填写的手术时间与麻醉记录时间不符。

#### 3.8.3 用户交互设计（画像面板）

在首页编辑界面的侧边栏或独立弹窗通过“画像视图”展示：

```
[ 时间轴视图 ]
2023-10-01 09:00 [入院] 初步诊断：急性阑尾炎？
       ↓
2023-10-01 10:30 [检查] B超提示：阑尾肿大
       ↓
2023-10-01 14:00 [手术] 腹腔镜下阑尾切除术 (验证通过: 手术记录+麻醉记录)
       ↓
2023-10-03 08:00 [查房] 发现切口红肿 (并发症线索) -> 首页建议补充: 切口感染
       ↓
2023-10-05 10:00 [出院] 出院诊断：急性阑尾炎
```

#### 3.8.4 输出数据结构

```typescript
interface MedicalProfile {
  // 诊断时间轴
  diagnosis_timeline: Array<{
    diagnosis_name: string
    first_mention_time: string
    first_mention_source: string // 文书名称
    status: "suspected" | "confirmed" | "ruled_out"
    timeline_events: Array<{ time: string, event: string, source: string }>
  }>

  // 手术验证
  surgery_verification: Array<{
    surgery_name: string
    plan_source?: string // 医嘱/通知单
    execution_source?: string // 手术记录
    verification_status: "verified" | "planned_only" | "executed_only"
    execution_time?: string
  }>
  
  // 差异分析
  discrepancies: Array<{
    type: "missing_in_frontpage" | "not_supported_by_record"
    item_category: "diagnosis" | "procedure"
    item_name: string
    suggestion: string
  }>
}
```

---

## 8. 成功指标

### 8.1 业务指标

| 指标 | 目标值 | 测量方式 |
|-----|-------|---------|
| 医生填写时长减少率 | ≥ 80% | 使用前后对比 |
| 字段自动填充率 | ≥ 90% | 自动填写数/总字段数 |
| 人工修改率 | ≤ 20% | 修改字段数/总字段数 |
| 用户满意度 | ≥ 4.0/5.0 | 问卷调查 |

### 8.2 技术指标

| 指标 | 目标值 | 测量方式 |
|-----|-------|---------|
| 患者信息准确率 | ≥ 95% | 人工抽检100例 |
| 诊断信息准确率 | ≥ 90% | 与医生编码对比 |
| ICD-10编码Top-1准确率 | ≥ 85% | 标准编码对比 |
| ICD-9-CM-3编码Top-1准确率 | ≥ 85% | 标准编码对比 |
| 入院病情推理准确率 | ≥ 80% | 专家评审 |
| 处理时间P50 | < 15秒 | 日志统计 |
| 处理时间P95 | < 30秒 | 日志统计 |

---

**文档版本历史**

| 版本 | 日期 | 修改内容 | 修改人 |
|-----|------|---------|--------|
| v1.0 | 2025-01-19 | 初始版本 | - |
| v1.1 | 2025-01-19 | 新增F13疾病诊断和手术操作画像 | Antigravity |

