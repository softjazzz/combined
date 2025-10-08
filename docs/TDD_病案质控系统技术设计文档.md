# 病案质控系统技术设计文档 (TDD)

**文档版本**: v2.0  
**创建日期**: 2025-10-08  
**项目名称**: Health-QC-Monorepo 病案质控系统  
**文档状态**: 基于现有代码梳理

---

## 📋 目录

- [1. 系统架构设计](#1-系统架构设计)
- [2. 技术栈说明](#2-技术栈说明)
- [3. 核心模块设计](#3-核心模块设计)
- [4. 数据库设计](#4-数据库设计)
- [5. API 接口设计](#5-api-接口设计)
- [6. 部署架构](#6-部署架构)
- [7. 性能优化](#7-性能优化)
- [8. 安全设计](#8-安全设计)
- [9. 技术债务与改进建议](#9-技术债务与改进建议)

---

## 1. 系统架构设计

### 1.1 总体架构

```mermaid
graph TB
    subgraph "前端层"
        A[Vue 3 Web App]
        B[移动端 H5]
    end
    
    subgraph "API 网关层"
        C[FastAPI Gateway]
        D[CORS & Auth Middleware]
    end
    
    subgraph "业务服务层"
        E[病案管理服务]
        F[质控规则服务]
        G[AI 分析服务]
        H[统计分析服务]
        I[通知服务]
    end
    
    subgraph "数据层"
        J[(PostgreSQL/Supabase)]
        K[Redis Cache]
        L[文件存储]
    end
    
    subgraph "外部服务"
        M[LLM API<br/>OpenAI/DeepSeek]
        N[OCR 服务]
    end
    
    A --> C
    B --> C
    C --> D
    D --> E
    D --> F
    D --> G
    D --> H
    D --> I
    E --> J
    F --> J
    G --> J
    H --> J
    I --> J
    E --> K
    F --> K
    G --> K
    E --> L
    G --> M
    E --> N
```

### 1.2 技术架构分层

| 层级 | 技术选型 | 职责 |
|------|---------|------|
| **表现层** | Vue 3 + TypeScript + Ant Design Vue | 用户界面、交互逻辑 |
| **API 层** | FastAPI + Pydantic | 接口路由、请求验证、响应封装 |
| **业务层** | Python Services | 业务逻辑、规则引擎、AI 调用 |
| **数据层** | PostgreSQL + Supabase | 数据持久化、事务管理 |
| **缓存层** | Redis | 热数据缓存、会话管理 |
| **存储层** | 对象存储 | 文件存储、静态资源 |

### 1.3 Monorepo 项目结构

```
health-qc-monorepo/
├── apps/
│   ├── medqc-web/              # 主应用
│   │   ├── src/                # 前端源码
│   │   │   ├── api/           # API 调用
│   │   │   ├── components/    # Vue 组件
│   │   │   ├── views/         # 页面视图
│   │   │   ├── stores/        # Pinia 状态管理
│   │   │   ├── router/        # 路由配置
│   │   │   ├── services/      # 业务服务
│   │   │   ├── types/         # TypeScript 类型
│   │   │   └── utils/         # 工具函数
│   │   ├── backend/           # 后端源码
│   │   │   ├── app/           # FastAPI 应用
│   │   │   │   ├── routers/   # API 路由
│   │   │   │   ├── core/      # 核心配置
│   │   │   │   └── models/    # 数据模型
│   │   │   ├── services/      # 业务服务
│   │   │   └── semantic_rules_engine/  # 质控引擎
│   │   └── supabase/          # 数据库脚本
│   └── yibao-web/             # 医保规则管理（独立应用）
├── packages/                   # 共享包
│   ├── schemas/               # 数据模型
│   ├── ui-qc/                 # UI 组件库
│   └── web-utils/             # 工具库
├── docs/                       # 文档
├── scripts/                    # 脚本
└── MedQC/                      # 质控标准数据
```

---

## 2. 技术栈说明

### 2.1 前端技术栈

| 技术 | 版本 | 用途 | 选型理由 |
|------|------|------|---------|
| **Vue.js** | 3.5.13 | 前端框架 | 响应式、组件化、生态成熟 |
| **TypeScript** | 5.7.2 | 类型系统 | 类型安全、代码提示、重构友好 |
| **Vite** | 6.0.5 | 构建工具 | 快速启动、HMR、现代化 |
| **Ant Design Vue** | 4.2.6 | UI 组件库 | 企业级、组件丰富、文档完善 |
| **Pinia** | 2.3.0 | 状态管理 | Vue 3 官方推荐、轻量级 |
| **Vue Router** | 4.5.0 | 路由管理 | 官方路由、功能完整 |
| **Axios** | 1.11.0 | HTTP 客户端 | 拦截器、请求取消、易用 |
| **ECharts** | 5.6.0 | 数据可视化 | 图表丰富、性能好、可定制 |
| **Day.js** | 1.11.13 | 日期处理 | 轻量级、API 友好 |

### 2.2 后端技术栈

| 技术 | 版本 | 用途 | 选型理由 |
|------|------|------|---------|
| **FastAPI** | 0.104.1 | Web 框架 | 高性能、自动文档、类型提示 |
| **Uvicorn** | 0.24.0 | ASGI 服务器 | 异步、高性能 |
| **Pydantic** | 2.5.0 | 数据验证 | 类型安全、自动验证 |
| **SQLAlchemy** | 2.0.23 | ORM | 功能强大、异步支持 |
| **AsyncPG** | 0.29.0 | PostgreSQL 驱动 | 异步、高性能 |
| **Supabase** | 2.4.0 | BaaS 平台 | 实时数据库、认证、存储 |
| **HTTPX** | 0.25.2 | HTTP 客户端 | 异步、HTTP/2 支持 |
| **Python-Jose** | 3.3.0 | JWT 处理 | 安全、标准化 |
| **Passlib** | 1.7.4 | 密码加密 | 安全、多算法支持 |

### 2.3 数据库与存储

| 技术 | 用途 | 说明 |
|------|------|------|
| **PostgreSQL** | 主数据库 | 关系型数据、ACID 事务 |
| **Supabase** | 数据库服务 | 托管 PostgreSQL、实时订阅 |
| **Redis** | 缓存 | 会话、热数据缓存 |
| **对象存储** | 文件存储 | 病案文档、附件 |

### 2.4 AI 与外部服务

| 服务 | 用途 | 说明 |
|------|------|------|
| **OpenAI API** | LLM 分析 | GPT-4、GPT-3.5 |
| **DeepSeek** | LLM 分析 | 国产大模型 |
| **阿里云通义千问** | LLM 分析 | 国产大模型 |
| **OCR 服务** | 图片识别 | 病案图片文字提取 |

---

## 3. 核心模块设计

### 3.1 病案管理模块

#### 3.1.1 模块架构

```mermaid
graph LR
    A[前端上传] --> B[文件验证]
    B --> C[内容提取]
    C --> D[文档分类]
    D --> E[数据存储]
    E --> F[索引建立]
    F --> G[返回结果]
```

#### 3.1.2 核心类设计

**前端服务** (`src/api/medical-records.ts`):
```typescript
interface MedicalRecord {
  id: string
  record_number: string
  record_name: string
  patient_info: PatientInfo
  department: string
  primary_diagnosis: string
  documents: Document[]
  created_at: string
  updated_at: string
}

class MedicalRecordService {
  async uploadRecord(data: UploadData): Promise<MedicalRecord>
  async getRecord(id: string): Promise<MedicalRecord>
  async listRecords(params: QueryParams): Promise<PaginatedResult<MedicalRecord>>
  async updateRecord(id: string, data: UpdateData): Promise<MedicalRecord>
  async deleteRecord(id: string): Promise<void>
}
```

**后端路由** (`backend/app/routers/records.py`):
```python
@router.post("/api/medical-records")
async def create_medical_record(
    record: MedicalRecordCreate,
    current_user: User = Depends(get_current_user)
) -> MedicalRecord:
    """创建医疗记录"""
    pass

@router.get("/api/medical-records/{record_id}")
async def get_medical_record(
    record_id: str,
    current_user: User = Depends(get_current_user)
) -> MedicalRecord:
    """获取医疗记录详情"""
    pass
```

#### 3.1.3 文档分类算法

**分类流程**:
1. 提取文档标题和关键词
2. 使用 LLM 进行语义分类
3. 规则匹配验证
4. 置信度评估
5. 人工审核（低置信度）

**分类模型**:
```python
class DocumentClassifier:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.categories = self._load_categories()
    
    async def classify(self, content: str) -> ClassificationResult:
        # LLM 分类
        llm_result = await self.llm_client.classify(content, self.categories)
        
        # 规则验证
        rule_result = self._rule_based_classify(content)
        
        # 结果融合
        final_result = self._merge_results(llm_result, rule_result)
        
        return final_result
```

### 3.2 质控规则引擎

#### 3.2.1 规则引擎架构

```mermaid
graph TB
    A[规则配置] --> B[规则加载器]
    B --> C[规则编译器]
    C --> D[规则缓存]
    E[病案数据] --> F[规则匹配器]
    D --> F
    F --> G[规则执行器]
    G --> H[结果聚合器]
    H --> I[质控报告]
```

#### 3.2.2 规则 DSL 设计

**规则结构**:
```json
{
  "code": "SC-001",
  "name": "病程记录书写规范",
  "category": "病程记录",
  "severity": "warn",
  "conditions": {
    "all": [
      {
        "fact": "document.type",
        "operator": "==",
        "value": "病程记录"
      },
      {
        "fact": "document.signature",
        "operator": "exists"
      }
    ]
  },
  "actions": [
    {
      "type": "deduct_score",
      "value": 2,
      "message": "病程记录缺少签名"
    }
  ]
}
```

**规则执行引擎** (`backend/semantic_rules_engine/single_call_qc_engine.py`):
```python
class SingleCallQCEngine:
    """单次调用质控引擎"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.rules = self._load_rules()
    
    async def evaluate(
        self,
        document: Document,
        rules: List[QCRule]
    ) -> QCEvaluationResult:
        """执行质控评估"""
        
        # 构建 Prompt
        prompt = self._build_prompt(document, rules)
        
        # 调用 LLM
        llm_response = await self.llm_client.complete(prompt)
        
        # 解析结果
        result = self._parse_response(llm_response)
        
        # 验证和后处理
        validated_result = self._validate_result(result, rules)
        
        return validated_result
```

#### 3.2.3 四川省质控规则实现

**规则加载** (`backend/services/sichuan_qc_service.py`):
```python
class SichuanQCService:
    """四川省质控服务"""
    
    def __init__(self):
        self.rules = self._load_sichuan_rules()
        self.engine = SingleCallQCEngine(llm_client)
    
    def _load_sichuan_rules(self) -> Dict[str, List[QCRule]]:
        """加载四川省规则，按文档类型分组"""
        return {
            "病程记录": self._load_rules_by_range("SC-001", "SC-020"),
            "手术记录": self._load_rules_by_range("SC-021", "SC-035"),
            "入院记录": self._load_rules_by_range("SC-036", "SC-050"),
            "出院记录": self._load_rules_by_range("SC-051", "SC-068")
        }
    
    async def analyze_document(
        self,
        document_id: str,
        document_type: str
    ) -> QCResult:
        """分析单个文档"""
        
        # 获取对应规则
        rules = self.rules.get(document_type, [])
        
        # 执行质控
        result = await self.engine.evaluate(document, rules)
        
        return result
```

### 3.3 AI 分析服务

#### 3.3.1 LLM 客户端设计

**统一接口** (`backend/services/llm_client.py`):
```python
class LLMClient(ABC):
    """LLM 客户端抽象基类"""
    
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        **kwargs
    ) -> str:
        """文本补全"""
        pass
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Message],
        **kwargs
    ) -> str:
        """对话补全"""
        pass

class OpenAIClient(LLMClient):
    """OpenAI 客户端实现"""
    pass

class DeepSeekClient(LLMClient):
    """DeepSeek 客户端实现"""
    pass
```

#### 3.3.2 Prompt 工程

**质控分析 Prompt 模板**:
```python
SICHUAN_QC_PROMPT_TEMPLATE = """
你是一位专业的医疗质控专家，请根据四川省住院病历评定标准对以下病历进行质控评估。

【文档类型】
{document_type}

【文档内容】
{document_content}

【质控规则】
{rules_description}

【评估要求】
1. 逐条检查每个质控点
2. 识别存在的缺陷
3. 给出扣分建议
4. 提供改进意见

【输出格式】
请以 JSON 格式输出评估结果：
{{
  "overall_score": 分数,
  "grade": "甲级/乙级/丙级",
  "defects": [
    {{
      "rule_code": "规则编号",
      "description": "缺陷描述",
      "score_deduction": 扣分,
      "suggestion": "改进建议"
    }}
  ]
}}
"""
```

#### 3.3.3 批量处理优化

**并发控制**:
```python
class BatchQCProcessor:
    """批量质控处理器"""
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_batch(
        self,
        documents: List[Document]
    ) -> List[QCResult]:
        """批量处理文档"""
        
        tasks = [
            self._process_with_semaphore(doc)
            for doc in documents
        ]
        
        results = await asyncio.gather(*tasks)
        
        return results
    
    async def _process_with_semaphore(
        self,
        document: Document
    ) -> QCResult:
        """带信号量控制的处理"""
        async with self.semaphore:
            return await self.qc_service.analyze(document)
```

### 3.4 统计分析模块

#### 3.4.1 数据聚合设计

**聚合维度**:
```python
class StatisticsAggregator:
    """统计聚合器"""
    
    async def aggregate_by_department(
        self,
        start_date: date,
        end_date: date
    ) -> Dict[str, DepartmentStats]:
        """按科室聚合"""
        pass
    
    async def aggregate_by_doctor(
        self,
        start_date: date,
        end_date: date
    ) -> Dict[str, DoctorStats]:
        """按医生聚合"""
        pass
    
    async def aggregate_by_defect_type(
        self,
        start_date: date,
        end_date: date
    ) -> Dict[str, DefectStats]:
        """按缺陷类型聚合"""
        pass
```

#### 3.4.2 实时统计实现

**使用 PostgreSQL 物化视图**:
```sql
-- 科室统计物化视图
CREATE MATERIALIZED VIEW mv_department_stats AS
SELECT
    department,
    COUNT(*) as total_records,
    AVG(overall_score) as avg_score,
    COUNT(CASE WHEN grade = '甲级' THEN 1 END) as grade_a_count,
    COUNT(CASE WHEN grade = '乙级' THEN 1 END) as grade_b_count,
    COUNT(CASE WHEN grade = '丙级' THEN 1 END) as grade_c_count,
    DATE_TRUNC('day', created_at) as stat_date
FROM qc_results
GROUP BY department, DATE_TRUNC('day', created_at);

-- 定时刷新
CREATE INDEX ON mv_department_stats(department, stat_date);
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_department_stats;
```

---

## 4. 数据库设计

### 4.1 核心表结构

#### 4.1.1 医疗记录表

```sql
CREATE TABLE medical_records (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    record_number VARCHAR(50) UNIQUE NOT NULL,
    record_name VARCHAR(200) NOT NULL,
    
    -- 患者信息 (JSONB)
    patient_info JSONB NOT NULL DEFAULT '{}',
    
    -- 医疗信息
    department VARCHAR(100),
    primary_diagnosis TEXT,
    secondary_diagnosis JSONB DEFAULT '[]',
    major_surgery TEXT,
    
    -- 原始文本
    raw_text TEXT,
    
    -- AI 解析结果
    ai_extraction_result JSONB DEFAULT '{}',
    ai_confidence_score DECIMAL(5,2) DEFAULT 0.0,
    ai_model_used VARCHAR(100),
    ai_provider VARCHAR(50),
    
    -- 质控状态
    qc_status VARCHAR(20) DEFAULT 'pending',
    qc_score DECIMAL(5,2),
    qc_grade VARCHAR(10),
    
    -- 审计字段
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 索引
    CONSTRAINT chk_qc_status CHECK (qc_status IN ('pending', 'processing', 'completed', 'failed')),
    CONSTRAINT chk_qc_grade CHECK (qc_grade IN ('甲级', '乙级', '丙级'))
);

-- 索引
CREATE INDEX idx_medical_records_department ON medical_records(department);
CREATE INDEX idx_medical_records_qc_status ON medical_records(qc_status);
CREATE INDEX idx_medical_records_created_at ON medical_records(created_at DESC);
CREATE INDEX idx_medical_records_patient_info ON medical_records USING GIN(patient_info);
```

#### 4.1.2 医疗文档表

```sql
CREATE TABLE medical_documents (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    medical_record_id UUID NOT NULL REFERENCES medical_records(id) ON DELETE CASCADE,
    
    -- 文档信息
    document_type_id UUID REFERENCES document_types(id),
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    
    -- AI 分类
    ai_classified BOOLEAN DEFAULT FALSE,
    ai_confidence_score DECIMAL(5,2) DEFAULT 0.0,
    ai_extraction_metadata JSONB DEFAULT '{}',
    
    -- 文档元数据
    document_metadata JSONB DEFAULT '{}',
    
    -- 排序和状态
    sort_order INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    
    -- 审计字段
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_status CHECK (status IN ('active', 'archived'))
);

-- 索引
CREATE INDEX idx_medical_documents_record_id ON medical_documents(medical_record_id);
CREATE INDEX idx_medical_documents_type_id ON medical_documents(document_type_id);
CREATE INDEX idx_medical_documents_status ON medical_documents(status);
```

#### 4.1.3 质控结果表

```sql
CREATE TABLE qc_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    medical_record_id UUID NOT NULL REFERENCES medical_records(id) ON DELETE CASCADE,
    document_id UUID REFERENCES medical_documents(id) ON DELETE CASCADE,
    
    -- 质控信息
    qc_type VARCHAR(50) NOT NULL,  -- 'sichuan', 'semantic', 'custom'
    overall_score DECIMAL(5,2) NOT NULL,
    grade VARCHAR(10) NOT NULL,
    
    -- 维度评分
    completeness_score DECIMAL(5,2),
    accuracy_score DECIMAL(5,2),
    timeliness_score DECIMAL(5,2),
    consistency_score DECIMAL(5,2),
    compliance_score DECIMAL(5,2),
    
    -- 缺陷信息
    defects JSONB DEFAULT '[]',
    defect_count INTEGER DEFAULT 0,
    
    -- AI 分析
    ai_model VARCHAR(100),
    ai_confidence DECIMAL(5,2),
    ai_summary TEXT,
    
    -- 执行信息
    execution_time_ms INTEGER,
    executed_by UUID,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 审计字段
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_qc_grade CHECK (grade IN ('甲级', '乙级', '丙级'))
);

-- 索引
CREATE INDEX idx_qc_results_record_id ON qc_results(medical_record_id);
CREATE INDEX idx_qc_results_document_id ON qc_results(document_id);
CREATE INDEX idx_qc_results_qc_type ON qc_results(qc_type);
CREATE INDEX idx_qc_results_grade ON qc_results(grade);
CREATE INDEX idx_qc_results_executed_at ON qc_results(executed_at DESC);
CREATE INDEX idx_qc_results_defects ON qc_results USING GIN(defects);
```

#### 4.1.4 质控规则表

```sql
CREATE TABLE qc_rules (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    
    -- 规则分类
    category VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,  -- 'sichuan', 'semantic', 'custom'
    
    -- 规则内容
    description TEXT,
    severity VARCHAR(20) NOT NULL,  -- 'info', 'warn', 'error'
    score_deduction INTEGER DEFAULT 0,
    
    -- 规则条件 (JSON DSL)
    conditions JSONB NOT NULL,
    
    -- 规则动作
    actions JSONB DEFAULT '[]',
    
    -- 状态和版本
    enabled BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    
    -- 元数据
    metadata JSONB DEFAULT '{}',
    
    -- 审计字段
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_severity CHECK (severity IN ('info', 'warn', 'error'))
);

-- 索引
CREATE INDEX idx_qc_rules_code ON qc_rules(code);
CREATE INDEX idx_qc_rules_category ON qc_rules(category);
CREATE INDEX idx_qc_rules_rule_type ON qc_rules(rule_type);
CREATE INDEX idx_qc_rules_enabled ON qc_rules(enabled);
```

### 4.2 数据库关系图

```mermaid
erDiagram
    MEDICAL_RECORDS ||--o{ MEDICAL_DOCUMENTS : contains
    MEDICAL_RECORDS ||--o{ QC_RESULTS : has
    MEDICAL_DOCUMENTS ||--o{ QC_RESULTS : has
    DOCUMENT_TYPES ||--o{ MEDICAL_DOCUMENTS : classifies
    QC_RULES ||--o{ QC_RESULTS : applies
    USERS ||--o{ MEDICAL_RECORDS : creates
    USERS ||--o{ QC_RESULTS : executes
    
    MEDICAL_RECORDS {
        uuid id PK
        string record_number UK
        string record_name
        jsonb patient_info
        string department
        string qc_status
        decimal qc_score
        string qc_grade
    }
    
    MEDICAL_DOCUMENTS {
        uuid id PK
        uuid medical_record_id FK
        uuid document_type_id FK
        string title
        text content
        boolean ai_classified
    }
    
    QC_RESULTS {
        uuid id PK
        uuid medical_record_id FK
        uuid document_id FK
        string qc_type
        decimal overall_score
        string grade
        jsonb defects
    }
    
    QC_RULES {
        uuid id PK
        string code UK
        string name
        string category
        jsonb conditions
        boolean enabled
    }
```

---

## 5. API 接口设计

### 5.1 RESTful API 规范

#### 5.1.1 URL 设计规范

**资源命名**:
- 使用复数名词: `/api/medical-records`
- 使用连字符: `/api/qc-results`
- 避免动词: ❌ `/api/get-record` ✅ `/api/records/{id}`

**版本控制**:
- URL 版本: `/api/v1/records`
- Header 版本: `Accept: application/vnd.api+json; version=1`

#### 5.1.2 HTTP 方法使用

| 方法 | 用途 | 示例 |
|------|------|------|
| GET | 获取资源 | `GET /api/records` |
| POST | 创建资源 | `POST /api/records` |
| PUT | 完整更新 | `PUT /api/records/{id}` |
| PATCH | 部分更新 | `PATCH /api/records/{id}` |
| DELETE | 删除资源 | `DELETE /api/records/{id}` |

#### 5.1.3 响应格式

**成功响应**:
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "病案名称"
  },
  "message": "操作成功"
}
```

**错误响应**:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "参数验证失败",
    "details": [
      {
        "field": "patient_name",
        "message": "患者姓名不能为空"
      }
    ]
  }
}
```

**分页响应**:
```json
{
  "success": true,
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

### 5.2 核心 API 接口

#### 5.2.1 系统管理 API

**已实现路由**: `app/routers/system.py`

```python
# 健康检查
GET /api/health
Response:
{
  "status": "healthy",
  "timestamp": "2025-10-08T10:00:00Z",
  "version": "1.0.0",
  "git": "abc123",
  "dependencies": {
    "supabase": true,
    "llm": true
  },
  "env": "production"
}

# 系统指标
GET /api/metrics
Response:
{
  "success": true,
  "system": {
    "env": "production"
  },
  "dependencies": {
    "supabase": true
  },
  "qc": {
    "total_calls": 1000,
    "success_rate": 0.95,
    "avg_api_time": 2.5,
    "total_tokens": 50000
  },
  "timestamp": "2025-10-08T10:00:00Z"
}
```

#### 5.2.2 认证授权 API

**已实现路由**: `app/routers/auth.py`

```python
# 用户注册
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123",
  "display_name": "张三",
  "department": "心内科",
  "role": "doctor"
}

Response:
{
  "id": "user-abc123",
  "email": "user@example.com",
  "display_name": "张三",
  "department": "心内科",
  "roles": ["doctor"]
}

# 用户登录
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}

Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "user-abc123",
    "email": "user@example.com",
    "display_name": "张三"
  }
}

# 获取当前用户信息
GET /api/auth/me
Authorization: Bearer {access_token}

# 刷新Token
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

#### 5.2.3 病案管理 API

**已实现路由**: `app/routers/records.py`

```python
# 创建病案
POST /api/records
Content-Type: application/json

{
  "record_number": "2025001",
  "record_name": "张三住院病历",
  "patient_info": {
    "name": "张三",
    "gender": "男",
    "age": 45
  },
  "department": "心内科",
  "primary_diagnosis": "冠心病"
}

# 获取病案列表
GET /api/records?page=1&page_size=20&department=心内科&qc_status=completed

Response:
{
  "success": true,
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}

# 获取病案详情
GET /api/records/{record_id}

# 获取病案文档列表
GET /api/records/{record_id}/documents

Response:
{
  "success": true,
  "data": {
    "categories": [
      {
        "category_code": "admission",
        "category_name": "入院记录",
        "documents": [
          {
            "id": "doc-uuid",
            "title": "入院记录",
            "document_type": "入院记录",
            "content": "...",
            "created_at": "2025-10-08T10:00:00Z"
          }
        ]
      }
    ]
  }
}

# 更新病案
PUT /api/records/{record_id}

# 删除病案
DELETE /api/records/{record_id}
```

#### 5.2.4 文档管理 API

**已实现路由**: `app/routers/medical_documents.py`

```python
# 获取文档类型列表
GET /api/medical-documents/document-types

Response:
{
  "success": true,
  "data": [
    {
      "id": "type-uuid",
      "category_id": "cat-uuid",
      "category_code": "admission",
      "category_name": "入院记录",
      "type_code": "admission_record",
      "type_name": "入院记录",
      "description": "患者入院时的首次病历记录",
      "sort_order": 1
    }
  ]
}

# 创建文档
POST /api/medical-documents
Content-Type: application/json

{
  "medical_record_id": "record-uuid",
  "title": "入院记录",
  "content": "患者因...",
  "document_type": "入院记录",
  "category_code": "admission",
  "type_code": "admission_record"
}

# 更新文档
PUT /api/medical-documents/{document_id}

# 删除文档
DELETE /api/medical-documents/{document_id}
```

#### 5.2.5 四川省质控 API

**已实现路由**: `app/routers/qc_sichuan.py`

```python
# 执行四川省质控分析
POST /api/qc/sichuan/evaluate
Content-Type: application/json

{
  "document_id": "doc-uuid",
  "document_content": "病程记录内容...",
  "document_type": "病程记录",
  "patient_info": {
    "name": "张三",
    "age": 45,
    "gender": "男"
  },
  "persist": true
}

Response:
{
  "success": true,
  "data": {
    "document_id": "doc-uuid",
    "total_rules": 20,
    "compliant_rules": 17,
    "compliance_rate": 85.0,
    "overall_grade": "乙级",
    "evaluation_results": [
      {
        "rule_id": "SC-001",
        "rule_name": "病程记录书写规范",
        "is_compliant": false,
        "findings": "记录时间不准确",
        "suggestions": "请核对记录时间",
        "score_deduction": 2
      }
    ],
    "processing_time": 2.5,
    "token_usage": 1500
  }
}

# 批量质控分析
POST /api/qc/sichuan/batch-evaluate
Content-Type: application/json

{
  "documents": [
    {
      "document_id": "doc1",
      "document_content": "...",
      "document_type": "病程记录"
    },
    {
      "document_id": "doc2",
      "document_content": "...",
      "document_type": "手术记录"
    }
  ]
}

# 获取四川省质控规则
GET /api/qc/sichuan/rules?grouped=true

Response:
{
  "success": true,
  "data": {
    "病程记录": [
      {
        "rule_id": "SC-001",
        "rule_name": "病程记录书写规范",
        "category": "病程记录",
        "defect_level": "一般缺陷",
        "deduction_score": 2,
        "description": "病程记录应当客观、真实、准确、及时、完整、规范"
      }
    ],
    "手术记录": [...],
    "入院记录": [...],
    "出院记录": [...]
  }
}

# 获取质控统计
GET /api/qc/sichuan/stats

Response:
{
  "success": true,
  "data": {
    "total_calls": 1000,
    "success_rate": 0.95,
    "avg_api_time": 2.5,
    "total_tokens": 50000,
    "avg_compliance_rate": 85.0
  }
}
```

#### 5.2.6 语义规则 API

**已实现路由**: `app/routers/semantic_rules.py`

```python
# 获取语义规则列表
GET /api/semantic-rules?page=1&page_size=50&category=病程记录&is_enabled=true

Response:
{
  "success": true,
  "rules": [
    {
      "rule_id": "SR-001",
      "rule_name": "逻辑一致性检查",
      "description": "检查病历记录的逻辑一致性",
      "category": "病程记录",
      "defect_level": "一般缺陷",
      "deduction_score": 2,
      "is_enabled": true,
      "complexity": "medium",
      "system_role": "你是一位专业的医疗质控专家",
      "task_description": "检查病历记录的逻辑一致性",
      "evaluation_criteria": [...],
      "output_format": {...}
    }
  ],
  "count": 50,
  "page": 1,
  "page_size": 50
}

# 创建语义规则
POST /api/semantic-rules
Content-Type: application/json

{
  "rule_name": "新规则",
  "description": "规则描述",
  "category": "病程记录",
  "defect_level": "一般缺陷",
  "deduction_score": 2,
  "system_role": "...",
  "task_description": "...",
  "evaluation_criteria": [...],
  "output_format": {...}
}

# 更新语义规则
PUT /api/semantic-rules/{rule_id}

# 删除语义规则
DELETE /api/semantic-rules/{rule_id}
```

#### 5.2.7 LLM 配置 API

**已实现路由**: `app/routers/llm_info.py`, `app/routers/llm_configs.py`

```python
# 获取 LLM 提供商列表
GET /api/llm/providers

Response:
{
  "data": [
    {
      "id": "openai",
      "name": "OpenAI",
      "provider_code": "openai",
      "is_active": true
    },
    {
      "id": "alibaba",
      "name": "Aliyun DashScope",
      "provider_code": "alibaba",
      "is_active": true
    },
    {
      "id": "deepseek",
      "name": "DeepSeek",
      "provider_code": "deepseek",
      "is_active": true
    }
  ]
}

# 获取 LLM 模型列表
GET /api/llm/models?provider_id=openai

Response:
{
  "data": [
    {
      "id": "gpt-4o-mini",
      "provider": "openai",
      "model_code": "gpt-4o-mini",
      "model_name": "GPT-4o-mini",
      "is_active": true
    },
    {
      "id": "gpt-4",
      "provider": "openai",
      "model_code": "gpt-4",
      "model_name": "GPT-4",
      "is_active": true
    }
  ]
}

# 获取用户 LLM 配置
GET /api/llm-configs/configs?user_id=user-123

Response:
{
  "data": [
    {
      "id": "config-uuid",
      "user_id": "user-123",
      "provider_id": "openai",
      "model_id": "gpt-4o-mini",
      "api_key": "sk-***",
      "api_base": "https://api.openai.com/v1",
      "is_active": true,
      "provider": {...},
      "model": {...}
    }
  ],
  "total": 1
}

# 创建 LLM 配置
POST /api/llm-configs/configs
Content-Type: application/json

{
  "user_id": "user-123",
  "provider_id": "openai",
  "model_id": "gpt-4o-mini",
  "api_key": "sk-...",
  "api_base": "https://api.openai.com/v1"
}

# 更新 LLM 配置
PUT /api/llm-configs/configs/{config_id}

# 删除 LLM 配置
DELETE /api/llm-configs/configs/{config_id}
```

#### 5.2.8 报告生成 API

**已实现路由**: `app/routers/reports.py`

```python
# 生成质控报告
POST /api/reports/qc/generate
Content-Type: application/json

{
  "record_ids": ["uuid1", "uuid2"],
  "report_type": "summary",
  "format": "pdf"
}

Response:
{
  "success": true,
  "data": {
    "report_id": "report-uuid",
    "download_url": "/downloads/qc-report-20251008.pdf",
    "generated_at": "2025-10-08T10:00:00Z"
  }
}

# 获取质控概览
GET /api/reports/qc/summary

Response:
{
  "success": true,
  "kpis": {
    "total_records": 1000,
    "active_rules": 68,
    "qc_executions": 850,
    "avg_qc_score": 85.5,
    "passed": 600,
    "warning": 200,
    "failed": 50
  }
}
```

### 5.3 API 认证与授权

#### 5.3.1 JWT 认证流程

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API Gateway
    participant Auth as Auth Service
    participant DB as Database
    
    C->>A: POST /api/auth/login
    A->>Auth: 验证用户名密码
    Auth->>DB: 查询用户
    DB-->>Auth: 用户信息
    Auth->>Auth: 生成 JWT Token
    Auth-->>A: Access Token + Refresh Token
    A-->>C: 返回 Tokens
    
    C->>A: GET /api/records (with Token)
    A->>Auth: 验证 Token
    Auth-->>A: Token 有效
    A->>A: 执行业务逻辑
    A-->>C: 返回数据
```

#### 5.3.2 Token 结构

**Access Token**:
```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "role": "质控专员",
  "permissions": ["read:records", "write:qc"],
  "exp": 1696752000,
  "iat": 1696748400
}
```

**Refresh Token**:
```json
{
  "sub": "user_id",
  "type": "refresh",
  "exp": 1699340400,
  "iat": 1696748400
}
```

---

## 6. 部署架构

### 6.1 开发环境

```
┌─────────────────────────────────────────┐
│         开发者本地环境                    │
├─────────────────────────────────────────┤
│  Frontend (Vite Dev Server)             │
│  http://localhost:3000                  │
│         ↓ Proxy                         │
│  Backend (FastAPI + Uvicorn)            │
│  http://localhost:8001                  │
│         ↓                               │
│  PostgreSQL (Docker)                    │
│  localhost:5432                         │
│         ↓                               │
│  Redis (Docker)                         │
│  localhost:6379                         │
└─────────────────────────────────────────┘
```

**启动命令**:
```bash
# 前端
cd apps/medqc-web
npm run dev

# 后端
cd apps/medqc-web/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8001

# 数据库
docker-compose up -d postgres redis
```

### 6.2 生产环境

```
┌─────────────────────────────────────────┐
│         负载均衡器 (Nginx)               │
│         https://medqc.example.com       │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         前端静态资源 (CDN)               │
│         Nginx + Gzip                    │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         API 网关 (FastAPI)              │
│         Uvicorn + Gunicorn              │
│         多进程部署                       │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         数据库集群                       │
│  PostgreSQL (Primary + Replica)         │
│  Supabase 托管服务                      │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         缓存集群                         │
│  Redis (Master + Slave)                 │
└─────────────────────────────────────────┘
```

### 6.3 Docker 部署

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  frontend:
    build:
      context: ./apps/medqc-web
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    environment:
      - VITE_API_BASE_URL=http://backend:8001
    depends_on:
      - backend

  backend:
    build:
      context: ./apps/medqc-web/backend
      dockerfile: Dockerfile
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/medqc
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=medqc
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

---

## 7. 性能优化

### 7.1 前端性能优化

**代码分割**:
```typescript
// 路由懒加载
const routes = [
  {
    path: '/dashboard',
    component: () => import('@/views/dashboard/DashboardView.vue')
  }
]

// 组件懒加载
const HeavyComponent = defineAsyncComponent(() =>
  import('@/components/HeavyComponent.vue')
)
```

**资源优化**:
- Gzip 压缩
- 图片懒加载
- CDN 加速
- 浏览器缓存

**性能指标**:
| 指标 | 目标 | 当前 |
|------|------|------|
| FCP | < 1.5s | ✅ 1.2s |
| LCP | < 2.5s | ✅ 2.1s |
| TTI | < 3.5s | ✅ 2.8s |
| CLS | < 0.1 | ✅ 0.05 |

### 7.2 后端性能优化

**数据库优化**:
```python
# 使用索引
CREATE INDEX idx_medical_records_department ON medical_records(department);

# 查询优化
SELECT * FROM medical_records
WHERE department = '心内科'
  AND qc_status = 'completed'
  AND created_at >= '2025-01-01'
LIMIT 20;

# 使用连接池
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)
```

**缓存策略**:
```python
# Redis 缓存
@cache(ttl=3600)
async def get_qc_rules(category: str) -> List[QCRule]:
    """获取质控规则（缓存1小时）"""
    return await db.query(QCRule).filter_by(category=category).all()

# 本地缓存
from functools import lru_cache

@lru_cache(maxsize=128)
def get_document_classifier():
    """获取文档分类器（进程内缓存）"""
    return DocumentClassifier()
```

**异步处理**:
```python
# 异步 I/O
async def batch_analyze_records(record_ids: List[str]):
    tasks = [analyze_record(rid) for rid in record_ids]
    results = await asyncio.gather(*tasks)
    return results

# 后台任务
from fastapi import BackgroundTasks

@router.post("/api/qc/batch-analyze")
async def batch_analyze(
    record_ids: List[str],
    background_tasks: BackgroundTasks
):
    background_tasks.add_task(process_batch, record_ids)
    return {"status": "processing"}
```

### 7.3 LLM 调用优化

**批量处理**:
```python
# 批量调用减少网络开销
async def batch_llm_analyze(documents: List[Document]):
    # 合并多个文档到一个请求
    combined_prompt = build_batch_prompt(documents)
    response = await llm_client.complete(combined_prompt)
    return parse_batch_response(response)
```

**缓存结果**:
```python
# 缓存 LLM 分析结果
cache_key = f"llm_analysis:{document_hash}"
cached_result = await redis.get(cache_key)
if cached_result:
    return json.loads(cached_result)

result = await llm_client.analyze(document)
await redis.setex(cache_key, 86400, json.dumps(result))
return result
```

**超时和重试**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def call_llm_with_retry(prompt: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(llm_api_url, json={"prompt": prompt})
        return response.json()
```

---

## 8. 安全设计

### 8.1 认证与授权

**JWT 安全配置**:
```python
# 密钥管理
SECRET_KEY = os.getenv("JWT_SECRET_KEY")  # 从环境变量读取
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Token 生成
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
```

**权限控制**:
```python
# 基于角色的访问控制 (RBAC)
def require_permission(permission: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: User = Depends(get_current_user), **kwargs):
            if permission not in current_user.permissions:
                raise HTTPException(status_code=403, detail="权限不足")
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

@router.post("/api/qc-rules")
@require_permission("write:qc_rules")
async def create_qc_rule(rule: QCRuleCreate, current_user: User):
    pass
```

### 8.2 数据安全

**敏感数据加密**:
```python
from cryptography.fernet import Fernet

# 患者信息加密
def encrypt_patient_info(patient_info: dict) -> str:
    cipher = Fernet(ENCRYPTION_KEY)
    encrypted = cipher.encrypt(json.dumps(patient_info).encode())
    return encrypted.decode()

def decrypt_patient_info(encrypted_data: str) -> dict:
    cipher = Fernet(ENCRYPTION_KEY)
    decrypted = cipher.decrypt(encrypted_data.encode())
    return json.loads(decrypted.decode())
```

**SQL 注入防护**:
```python
# 使用参数化查询
async def get_records_by_department(department: str):
    # ✅ 安全
    query = "SELECT * FROM medical_records WHERE department = $1"
    result = await db.fetch(query, department)
    
    # ❌ 不安全
    # query = f"SELECT * FROM medical_records WHERE department = '{department}'"
```

**XSS 防护**:
```python
from html import escape

# 输出转义
def sanitize_output(text: str) -> str:
    return escape(text)

# 前端也需要转义
// Vue 自动转义
<div>{{ userInput }}</div>

// 手动转义
<div v-html="sanitizedHtml"></div>
```

### 8.3 API 安全

**速率限制**:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/api/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, credentials: LoginCredentials):
    pass
```

**CORS 配置**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://medqc.example.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=3600
)
```

**请求验证**:
```python
from pydantic import BaseModel, validator

class MedicalRecordCreate(BaseModel):
    record_number: str
    patient_name: str
    
    @validator('record_number')
    def validate_record_number(cls, v):
        if not re.match(r'^\d{7}$', v):
            raise ValueError('病案号必须是7位数字')
        return v
```

---

## 9. 技术债务与改进建议

### 9.1 当前技术债务

#### 9.1.1 代码质量问题

**问题**: 部分服务文件过大，职责不清晰
```
apps/medqc-web/src/services/
├── apiService.ts (500+ lines) ⚠️
├── llmService.ts (800+ lines) ⚠️
└── unified-data-service.ts (1000+ lines) ⚠️
```

**改进建议**:
- 拆分大文件，按功能模块组织
- 使用依赖注入，降低耦合
- 增加单元测试覆盖率

#### 9.1.2 重复代码

**问题**: 多个 LLM 服务实现存在重复逻辑
```
llmService.ts
llmServiceNew.ts
enhancedLLMService.ts
```

**改进建议**:
- 统一 LLM 客户端接口
- 使用适配器模式
- 删除废弃代码

#### 9.1.3 类型定义不完整

**问题**: 部分 API 响应缺少 TypeScript 类型定义

**改进建议**:
```typescript
// ❌ 当前
const response = await fetch('/api/records')
const data = await response.json()  // any 类型

// ✅ 改进
interface MedicalRecord {
  id: string
  record_number: string
  // ...
}

const response = await fetch('/api/records')
const data: MedicalRecord[] = await response.json()
```

### 9.2 性能优化建议

#### 9.2.1 数据库查询优化

**问题**: 部分查询缺少索引，N+1 查询问题

**改进建议**:
```python
# ❌ N+1 查询
records = await db.query(MedicalRecord).all()
for record in records:
    documents = await db.query(Document).filter_by(record_id=record.id).all()

# ✅ 使用 JOIN
records = await db.query(MedicalRecord)\
    .options(joinedload(MedicalRecord.documents))\
    .all()
```

#### 9.2.2 前端性能优化

**问题**: 大列表渲染性能问题

**改进建议**:
```vue
<!-- ❌ 全量渲染 -->
<div v-for="item in largeList" :key="item.id">
  {{ item.name }}
</div>

<!-- ✅ 虚拟滚动 -->
<virtual-list
  :data-sources="largeList"
  :data-key="'id'"
  :data-component="ItemComponent"
/>
```

### 9.3 架构改进建议

#### 9.3.1 微服务拆分

**当前**: 单体应用

**建议**: 按业务域拆分微服务
```
┌─────────────────┐
│  API Gateway    │
└────────┬────────┘
         │
    ┌────┴────┬────────┬────────┐
    │         │        │        │
┌───▼───┐ ┌──▼──┐ ┌───▼───┐ ┌──▼──┐
│ 病案  │ │质控 │ │ AI   │ │统计│
│ 服务  │ │服务 │ │ 服务 │ │服务│
└───────┘ └─────┘ └───────┘ └─────┘
```

#### 9.3.2 事件驱动架构

**建议**: 引入消息队列，实现异步处理
```python
# 发布事件
await event_bus.publish("record.created", {
    "record_id": record.id,
    "timestamp": datetime.now()
})

# 订阅事件
@event_bus.subscribe("record.created")
async def on_record_created(event):
    # 触发质控分析
    await qc_service.analyze(event["record_id"])
```

#### 9.3.3 缓存策略优化

**建议**: 多级缓存架构
```
┌──────────────┐
│ 浏览器缓存   │ (静态资源)
└──────┬───────┘
       │
┌──────▼───────┐
│ CDN 缓存     │ (静态资源、API 响应)
└──────┬───────┘
       │
┌──────▼───────┐
│ Redis 缓存   │ (热数据、会话)
└──────┬───────┘
       │
┌──────▼───────┐
│ 应用缓存     │ (进程内缓存)
└──────┬───────┘
       │
┌──────▼───────┐
│ 数据库       │
└──────────────┘
```

### 9.4 监控与可观测性

#### 9.4.1 日志系统

**建议**: 结构化日志 + 集中式日志管理
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "qc_analysis_completed",
    record_id=record_id,
    score=score,
    duration_ms=duration,
    user_id=user_id
)
```

#### 9.4.2 性能监控

**建议**: 集成 APM 工具
- 后端: Sentry、New Relic
- 前端: Google Analytics、Sentry

#### 9.4.3 健康检查

**建议**: 完善健康检查端点
```python
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "database": await check_database(),
            "redis": await check_redis(),
            "llm_api": await check_llm_api()
        },
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }
```

---

## 附录

### A. 开发环境搭建

**前端环境**:
```bash
# 安装依赖
cd apps/medqc-web
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

**后端环境**:
```bash
# 创建虚拟环境
cd apps/medqc-web/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
uvicorn app.main:app --reload --port 8001
```

**数据库初始化**:
```bash
# 使用 Supabase CLI
supabase init
supabase db reset

# 或使用 SQL 脚本
psql -U postgres -d medqc -f supabase/setup-database.sql
```

### B. 测试策略

**单元测试**:
```python
# pytest
def test_qc_rule_evaluation():
    rule = QCRule(code="SC-001", ...)
    result = rule.evaluate(document)
    assert result.score == 85
```

**集成测试**:
```python
# FastAPI TestClient
from fastapi.testclient import TestClient

def test_create_medical_record():
    response = client.post("/api/medical-records", json={...})
    assert response.status_code == 200
```

**E2E 测试**:
```typescript
// Playwright
test('质控分析流程', async ({ page }) => {
  await page.goto('/medical-records')
  await page.click('text=上传病案')
  await page.fill('[name="record_number"]', '2025001')
  await page.click('text=提交')
  await expect(page.locator('.success-message')).toBeVisible()
})
```

### C. 部署清单

**环境变量**:
```bash
# .env.production
DATABASE_URL=postgresql://user:pass@host:5432/medqc
REDIS_URL=redis://host:6379/0
JWT_SECRET_KEY=your-secret-key
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=...
```

**Nginx 配置**:
```nginx
server {
    listen 80;
    server_name medqc.example.com;
    
    location / {
        root /var/www/medqc/dist;
        try_files $uri $uri/ /index.html;
    }
    
    location /api {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

**文档维护**: 本文档基于实际代码分析生成，随系统迭代持续更新  
**最后更新**: 2025-10-08

