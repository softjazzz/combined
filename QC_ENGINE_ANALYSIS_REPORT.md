# 质控引擎实现分析报告 🔍

**分析时间**: 2025-10-11  
**分析范围**: health-qc-monorepo 项目  
**分析目的**: 确认项目中是否有真实的质控引擎实现

---

## 📊 执行摘要

### 核心发现

**结论**: 项目中**存在真实的 LLM 质控引擎实现**，但**默认未配置**，在未配置时会回退到模拟模式。

| 质控引擎类型 | 实现状态 | 配置状态 | 可用性 |
|------------|---------|---------|--------|
| **四川质控引擎** (Sichuan QC) | ✅ 已实现 | ❌ 未配置 | ⚠️ 需配置 API Key |
| **通用质控引擎** (QC Service) | ⚠️ 模拟实现 | N/A | ✅ 可用（演示模式） |
| **语义规则引擎** (Semantic Rules) | ✅ 已实现 | ✅ 已配置 | ✅ 可用 |
| **医保规则引擎** (Yibao) | ✅ 已实现 | ⚠️ 独立项目 | ✅ 可用 |

---

## 🔍 详细分析

### 1. 四川质控引擎（真实 LLM 实现）✅

#### 1.1 实现位置
- **服务类**: `apps/medqc-web/backend/app/services/sichuan_qc_service.py`
- **路由**: `apps/medqc-web/backend/app/routers/qc_sichuan.py`
- **HTTP 客户端**: `apps/medqc-web/backend/app/core/http.py`

#### 1.2 核心实现

**LLM 客户端类** (`SichuanQCLLMClient`):

```python
class SichuanQCLLMClient:
    def __init__(self) -> None:
        s = get_settings()
        self.api_endpoint: Optional[str] = str(s.SICHUAN_API_ENDPOINT) if s.SICHUAN_API_ENDPOINT else None
        self.api_key: Optional[str] = s.SICHUAN_API_KEY
        self.model: str = s.SICHUAN_MODEL  # 默认: "qwen2.5-14b-instruct"
        self.timeout_seconds: int = s.SICHUAN_TIMEOUT_SECONDS  # 默认: 120秒

    async def generate(self, prompt: str) -> Dict[str, Any]:
        # 如果未配置 API，返回 MOCK 结果
        if not (self.api_endpoint and self.api_key):
            return {
                "choices": [{"message": {"content": f"[MOCK RESULT] 分析完成: {prompt[:60]}..."}}],
                "usage": {"total_tokens": 0},
                "_mock": True,
            }
        
        # 真实的 LLM API 调用
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 4000,
            "stream": False,
        }
        
        result = await safe_post_json(
            url=f"{self.api_endpoint}/chat/completions",
            headers=headers,
            payload=payload,
            timeout_seconds=self.timeout_seconds,
        )
        return result
```

#### 1.3 配置要求

**环境变量** (在 `.env` 文件中配置):

```bash
# 四川质控 API 配置
SICHUAN_API_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1
SICHUAN_API_KEY=sk-your-api-key-here
SICHUAN_MODEL=qwen2.5-14b-instruct
SICHUAN_TIMEOUT_SECONDS=120
```

**当前配置状态**:
- ❌ `SICHUAN_API_ENDPOINT`: 未配置
- ❌ `SICHUAN_API_KEY`: 未配置
- ✅ `SICHUAN_MODEL`: 有默认值 (`qwen2.5-14b-instruct`)
- ✅ `SICHUAN_TIMEOUT_SECONDS`: 有默认值 (120)

#### 1.4 支持的 LLM 提供商

根据代码分析，支持以下 LLM 提供商：

| 提供商 | API 端点 | 模型示例 |
|--------|---------|---------|
| **阿里云通义千问** | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen2.5-14b-instruct` |
| **OpenAI** | `https://api.openai.com/v1` | `gpt-4`, `gpt-3.5-turbo` |
| **DeepSeek** | `https://api.deepseek.com/v1` | `deepseek-chat` |
| **其他 OpenAI 兼容 API** | 自定义端点 | 自定义模型 |

#### 1.5 质控功能

**单文档质控** (`/api/v1/qc/sichuan/evaluate`):
- 输入：文档内容、文档类型、规则 ID
- 处理：调用 LLM 进行语义分析
- 输出：合规率、问题列表、改进建议

**多文档质控** (`evaluate_multi_document`):
- 支持同时分析多个文档类型
- 自动从 Supabase 加载适用规则
- 按文档类型分组评估
- 生成综合质控报告

**批量质控** (`/api/v1/qc/sichuan/batch`):
- 支持批量处理多个病历
- 并发调用 LLM API
- 统计成功率和 Token 使用量

#### 1.6 统计功能

```python
def stats(self) -> Dict[str, Any]:
    return {
        "total_calls": self.call_count,
        "success_calls": self.success_count,
        "error_calls": self.error_count,
        "success_rate": (self.success_count / self.call_count * 100),
        "total_tokens": self.total_tokens,
        "total_api_time": self.total_api_time,
        "avg_api_time": (self.total_api_time / self.call_count),
    }
```

---

### 2. 通用质控引擎（模拟实现）⚠️

#### 2.1 实现位置
- **服务类**: `apps/medqc-web/backend/app/services/qc_service.py`
- **路由**: `apps/medqc-web/backend/app/routers/qc.py`

#### 2.2 实现方式

**这是一个演示模式的实现**，使用确定性算法而非真实 LLM：

```python
async def evaluate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run a lightweight deterministic QC evaluation.
    
    The demo前端会传入病历内容、选中文书与规则，本方法根据这些信息
    生成一个稳定但富有语义的分析结果，以便在演示模式下模拟真实质控流程。
    """
    
    # 基于内容长度计算评分
    content_strength = min(30, max(0, len(content_lower) // 400 * 5))
    
    # 基于关键词匹配计算奖励
    keyword_bonus = min(12, keyword_hits * 6)
    
    # 基于文档类型计算奖励
    doc_bonus = 8 if doc_types.intersection(hint_targets) else 4
    
    # 最终评分
    score_components = 50 + content_strength + keyword_bonus + doc_bonus
```

#### 2.3 评分逻辑

| 评分组成 | 最大值 | 计算方式 |
|---------|-------|---------|
| 基础分 | 50 | 固定值 |
| 内容强度 | 30 | `len(content) // 400 * 5` |
| 关键词匹配 | 12 | `keyword_hits * 6` |
| 文档类型匹配 | 8 | 匹配则 8 分，否则 4 分 |
| **总分** | **100** | 四项相加，最高 98 分 |

#### 2.4 用途

- ✅ 测试前后端集成
- ✅ 验证 API 接口
- ✅ 展示质控流程
- ❌ **不适用于生产环境**

---

### 3. 语义规则引擎 ✅

#### 3.1 实现位置
- **路由**: `apps/medqc-web/backend/app/routers/semantic_rules.py`
- **数据源**: Supabase `qc_rules` 表

#### 3.2 功能特性

**规则管理**:
- ✅ 规则列表查询（支持筛选、排序、分页）
- ✅ 规则详情查询
- ✅ 规则执行（单个/批量）
- ✅ 自定义规则执行
- ✅ 规则统计
- ✅ 规则验证

**规则字段**:
- `rule_id`: 规则唯一标识
- `name`: 规则名称
- `description`: 规则描述
- `category`: 规则类别（completeness, consistency, rationality, timeliness, compliance）
- `severity`: 严重程度（critical, major, medium, minor, low）
- `applicable_documents`: 适用文档类型
- `check_logic`: 检查逻辑（JSON）
- `is_active`: 是否启用

**文档类型推断**:
```python
def _infer_docs_from_name(rule_name: str) -> list[str]:
    name = (rule_name or "").lower()
    if any(k in name for k in ["入院", "admission"]):
        return ["入院记录"]
    if any(k in name for k in ["首次病程", "first course"]):
        return ["首次病程记录"]
    if any(k in name for k in ["病程", "progress note"]):
        return ["病程记录"]
    # ... 更多类型
```

#### 3.3 数据源

**Supabase 表**: `qc_rules`

当前配置:
- ✅ Supabase URL: `https://dgsdkdbjpucyawnyfbdu.supabase.co`
- ✅ Supabase Anon Key: 已配置
- ✅ 表名: `qc_rules`

---

### 4. 医保规则引擎（Yibao 项目）✅

#### 4.1 项目位置
- **目录**: `Yibao/`
- **Edge Functions**: `Yibao/supabase/functions/`

#### 4.2 实现方式

**Edge Functions** (Supabase Serverless):

1. **evaluate-rule** - 规则引擎执行器
   - 输入：病例上下文 JSON + 规则 ID/事件类型
   - 流程：读取规则 → 加载 conditions/actions → 计算命中 → 生成结果
   - 输出：`{ severity, messages[], evidence }`

2. **violations** - 违规记录管理
   - 支持按 `severity`、`visit_id`、`rule_code` 过滤
   - 分页结果携带准确总数
   - CORS 支持

3. **statistics** - 统计数据聚合
   - 汇总规则命中趋势
   - TopN 维度（科室/医生/规则类型）
   - 导出 CSV/JSON

4. **rule-performance-monitor** - 性能监控
   - 质控引擎性能监控
   - 统计分析
   - 基准测试

#### 4.3 LLM 解析器

**文件**: `Yibao/llm_parser.py`

```python
from openai import OpenAI

def get_api_client():
    """Initializes and returns the OpenAI client."""
    global API_CLIENT
    if API_CLIENT is None:
        try:
            API_CLIENT = OpenAI()
        except Exception as e:
            print(f"Error initializing OpenAI client: {e}")
            return None
    return API_CLIENT

def parse_chunk(text_chunk):
    """Sends a chunk of text to the LLM and returns the parsed JSON."""
    # 调用 OpenAI API 解析医保规则文本
```

#### 4.4 技术栈

- **后端**: Supabase Edge Functions (TypeScript/Deno)
- **规则引擎**: 自研轻量执行器 或 `json-rules-engine`
- **LLM**: OpenAI API（用于规则文本解析）
- **数据库**: Supabase PostgreSQL

---

## 📋 对比分析

### 我之前的首次病程记录质控使用的是哪个引擎？

**答案**: 使用的是**通用质控引擎（模拟实现）**

**证据**:

1. **测试文件调用的路由**:
   ```python
   # test_first_course_record_qc.py
   response = client.post(f"/api/v1/qc/analyze/{record_id}", json=first_course_record)
   ```

2. **路由对应的服务**:
   ```python
   # app/routers/qc.py
   @router.post("/analyze/{record_id}")
   async def analyze_record(request: Request, record_id: str, payload: Optional[Dict[str, Any]] = None):
       result = await service.evaluate(request_payload)  # 调用 QCService.evaluate()
   ```

3. **服务实现**:
   ```python
   # app/services/qc_service.py
   class QCService:
       async def evaluate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
           """Run a lightweight deterministic QC evaluation."""
           # 模拟算法，非真实 LLM
   ```

### 如何使用真实的 LLM 质控引擎？

**方法 1**: 使用四川质控引擎

```python
# 修改测试文件
response = client.post(
    "/api/v1/qc/sichuan/evaluate",  # 使用四川质控端点
    json={
        "document_id": record_id,
        "document_content": first_course_record["content"],
        "document_type": "首次病程记录",
        "persist": True
    }
)
```

**方法 2**: 配置环境变量后使用

```bash
# 在 .env 文件中添加
SICHUAN_API_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1
SICHUAN_API_KEY=sk-your-api-key-here
```

---

## 🎯 结论

### 1. 项目中**确实有真实的质控引擎实现**

| 引擎类型 | 实现状态 | LLM 调用 | 生产可用 |
|---------|---------|---------|---------|
| **四川质控引擎** | ✅ 完整实现 | ✅ 真实 LLM | ✅ 是（需配置） |
| **通用质控引擎** | ⚠️ 模拟实现 | ❌ 无 | ❌ 否（仅演示） |
| **语义规则引擎** | ✅ 完整实现 | ⚠️ 规则匹配 | ✅ 是 |
| **医保规则引擎** | ✅ 完整实现 | ✅ OpenAI | ✅ 是 |

### 2. 我之前的测试使用的是**模拟实现**

- ❌ 没有调用真实的 LLM API
- ❌ 没有使用真实的质控规则引擎
- ✅ 使用的是基于关键词和内容长度的简单算法
- ✅ 适用于测试和演示，不适用于生产

### 3. 要使用真实的质控引擎，需要：

**选项 A**: 配置四川质控引擎
```bash
# 1. 配置环境变量
SICHUAN_API_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1
SICHUAN_API_KEY=sk-your-api-key-here

# 2. 修改 API 调用
POST /api/v1/qc/sichuan/evaluate
```

**选项 B**: 使用医保规则引擎（Yibao 项目）
```bash
# 1. 部署 Edge Functions
cd Yibao
supabase functions deploy evaluate-rule

# 2. 调用 Edge Function
POST https://your-project.supabase.co/functions/v1/evaluate-rule
```

---

## 📝 建议

### 短期（1-2 天）
1. ✅ 配置 `SICHUAN_API_ENDPOINT` 和 `SICHUAN_API_KEY`
2. ✅ 修改测试使用四川质控引擎端点
3. ✅ 验证真实 LLM 质控结果

### 中期（1-2 周）
1. ⚠️ 集成语义规则引擎到四川质控流程
2. ⚠️ 实现规则与 LLM 的混合质控模式
3. ⚠️ 添加质控结果缓存机制

### 长期（1-2 个月）
1. 💡 统一四川质控引擎和医保规则引擎
2. 💡 实现多 LLM 提供商支持（OpenAI、Claude、通义千问）
3. 💡 建立质控引擎性能监控和优化机制

---

**分析完成时间**: 2025-10-11  
**分析人**: Augment Agent  
**分析方法**: 代码审查 + 配置检查 + 架构分析

