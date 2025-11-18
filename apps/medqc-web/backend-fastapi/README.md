# DRG Backend API

DRG/DIP 系统后端服务，基于 FastAPI 构建。

## 功能概述

### 3.2.1 编码智能辅助

- **ICD 编码推荐**：使用 LLM 根据诊断名称推荐 ICD-10/ICD-9-CM-3 编码
- **编码校验**：检查编码完整性和逻辑一致性
- **编码库搜索**：全文搜索 ICD 编码（支持中文分词）

### 3.2.2 自动入组预测

- **DRG 分组预测**：调用 OpenDRG 引擎进行分组
- **费用预测**：预估 DRG 基准支付金额
- **分组历史**：追踪分组版本变更

### 3.3 事中监控

- **实时预警**：费用超标、住院日过长等预警
- **编码优化建议**：LLM 分析病历后给出的建议

## 技术栈

- **框架**：FastAPI 0.109 + Uvicorn
- **数据库**：Supabase (PostgreSQL)
- **LLM**：DeepSeek-V3 (兼容 OpenAI API)
- **分组引擎**：OpenDRG（模拟模式/真实集成）
- **日志**：Loguru
- **数据验证**：Pydantic v2

## 快速开始

### 1. 环境准备

```bash
# Python 版本要求：3.10+
python --version

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，配置以下关键信息：
# - SUPABASE_URL
# - SUPABASE_KEY (service_role key)
# - DEEPSEEK_API_KEY
```

### 4. 启动服务

```bash
# 开发模式（自动重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# 或者直接运行
python -m app.main
```

### 5. 访问 API 文档

启动后访问：

- **Swagger UI**：http://localhost:8001/docs
- **ReDoc**：http://localhost:8001/redoc
- **OpenAPI JSON**：http://localhost:8001/openapi.json

## 项目结构

```
backend-fastapi/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 主应用
│   ├── config.py               # 配置管理
│   ├── api/                    # API 路由
│   │   ├── __init__.py
│   │   ├── coding.py           # 编码辅助 API
│   │   └── drg.py              # DRG 分组 API
│   ├── services/               # 业务服务
│   │   ├── __init__.py
│   │   ├── llm_service.py      # LLM 服务封装
│   │   ├── database.py         # Supabase 数据库服务
│   │   └── drg_grouper.py      # OpenDRG 分组引擎
│   └── models/                 # 数据模型
│       ├── __init__.py
│       └── schemas.py          # Pydantic 数据模型
├── logs/                       # 日志文件目录
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量模板
└── README.md                   # 本文档
```

## API 接口

### 编码辅助 API

#### 1. ICD 编码推荐

```http
POST /api/v1/coding/suggest
Content-Type: application/json

{
  "diagnosis_name": "急性心肌梗死",
  "context": "患者突发胸痛，心电图示前壁ST段抬高",
  "category": "diagnosis"
}
```

**响应**：

```json
{
  "candidates": [
    {
      "code": "I21.001",
      "name": "急性前壁ST段抬高型心肌梗死",
      "confidence": 0.92,
      "note": "根据'前壁'和'ST段抬高'特征推荐"
    }
  ],
  "total": 1
}
```

#### 2. 编码校验

```http
POST /api/v1/coding/validate
Content-Type: application/json

{
  "admission_id": "ADM20250104001",
  "primary_diagnosis": {
    "code": "I21.001",
    "name": "急性前壁ST段抬高型心肌梗死"
  },
  "secondary_diagnoses": [
    {"code": "I10.x01", "name": "高血压3级"}
  ],
  "procedures": [
    {"code": "36.0700", "name": "经皮冠状动脉介入术"}
  ]
}
```

#### 3. ICD 编码搜索

```http
GET /api/v1/coding/search?keyword=心肌梗死&category=diagnosis&limit=20
```

### DRG 分组 API

#### 1. DRG 入组预测

```http
POST /api/v1/drg/predict
Content-Type: application/json

{
  "admission_id": "ADM20250104001",
  "region": "sichuan"
}
```

**响应**：

```json
{
  "data": {
    "adrg_code": "FB1",
    "adrg_name": "急性心肌梗死",
    "drg_code": "FB19",
    "drg_name": "急性心肌梗死伴严重合并症",
    "weight": 2.8653,
    "baseline_payment": 42000.00,
    "expected_los": {"min": 10, "max": 15},
    "confidence": 0.89,
    "risk_level": "high",
    "grouping_logic": "主诊断：I21.001 → ADRG FB1；存在严重并发症 → 权重增加50%"
  },
  "message": "分组成功"
}
```

#### 2. DRG 分组历史

```http
GET /api/v1/drg/grouping/{admission_id}/history
```

#### 3. 获取编码建议

```http
GET /api/v1/drg/suggestions/{admission_id}?status=pending
```

#### 4. 获取 DRG 预警

```http
GET /api/v1/drg/alerts?admission_id=ADM20250104001&alert_level=critical
```

## 配置说明

### Supabase 配置

后端需要使用 **service_role key**，具有完整数据库权限：

```bash
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # service_role key
```

⚠️ **安全提示**：
- service_role key 具有绕过 RLS 的完整权限
- 不要在前端代码中使用此密钥
- 不要提交到 Git 仓库

### LLM 配置

使用 DeepSeek-V3（兼容 OpenAI API）：

```bash
DEEPSEEK_API_KEY=sk-your-api-key
DEEPSEEK_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DEEPSEEK_MODEL=deepseek-v3
```

如需使用其他 LLM（如 OpenAI、Claude），修改 `app/services/llm_service.py` 中的客户端配置。

### OpenDRG 配置

当前使用**模拟模式**进行开发。

集成真实 OpenDRG 引擎：

1. 安装 OpenDRG：
   ```bash
   pip install opendrg
   # 或从 Git 安装
   pip install git+https://github.com/xxx/opendrg.git
   ```

2. 修改 `app/services/drg_grouper.py`：
   ```python
   from opendrg import DRGGrouper
   self.grouper = DRGGrouper(region=self.region)
   ```

3. 更新分组逻辑调用真实引擎。

## 开发指南

### 添加新 API 端点

1. 在 `app/api/` 目录创建新的路由文件
2. 定义 Pydantic 模型（`app/models/schemas.py`）
3. 在 `app/main.py` 中注册路由

示例：

```python
# app/api/analysis.py
from fastapi import APIRouter

router = APIRouter(prefix="/analysis", tags=["事后分析"])

@router.get("/statistics")
async def get_statistics():
    return {"message": "统计数据"}

# app/main.py
from app.api import analysis
app.include_router(analysis.router, prefix=settings.API_V1_PREFIX)
```

### 数据库操作

所有数据库操作通过 `app/services/database.py` 统一管理：

```python
from app.services.database import db_service

# 获取病案首页
case = await db_service.get_case_front_page(admission_id)

# 保存 DRG 分组
grouping_id = await db_service.save_drg_grouping(...)
```

### LLM 调用

通过 `app/services/llm_service.py` 调用 LLM：

```python
from app.services.llm_service import llm_service

# ICD 编码推荐
suggestions = await llm_service.suggest_icd_codes(
    diagnosis_name="急性心肌梗死",
    category="diagnosis"
)
```

## 测试

### 运行测试（待实现）

```bash
# 安装测试依赖
pip install pytest pytest-asyncio httpx

# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_coding_api.py

# 查看覆盖率
pytest --cov=app tests/
```

### 手动测试

使用 Swagger UI（http://localhost:8001/docs）或 curl：

```bash
# 健康检查
curl http://localhost:8001/health

# ICD 编码推荐
curl -X POST http://localhost:8001/api/v1/coding/suggest \
  -H "Content-Type: application/json" \
  -d '{
    "diagnosis_name": "急性心肌梗死",
    "category": "diagnosis"
  }'

# DRG 分组预测
curl -X POST http://localhost:8001/api/v1/drg/predict \
  -H "Content-Type: application/json" \
  -d '{
    "admission_id": "ADM20250104001",
    "region": "sichuan"
  }'
```

## 部署

### Docker 部署（待实现）

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

```bash
# 构建镜像
docker build -t drg-backend .

# 运行容器
docker run -p 8001:8001 --env-file .env drg-backend
```

### 生产部署

使用 Gunicorn + Uvicorn workers：

```bash
pip install gunicorn

gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001 \
  --access-logfile - \
  --error-logfile -
```

## 常见问题

### Q1: 启动时报错 "Module not found"？

检查 Python 路径和虚拟环境：

```bash
# 确认在虚拟环境中
which python

# 重新安装依赖
pip install -r requirements.txt
```

### Q2: Supabase 连接失败？

检查：
1. `.env` 文件中的 `SUPABASE_URL` 和 `SUPABASE_KEY` 是否正确
2. 使用的是 **service_role key**（不是 anon key）
3. 网络连接是否正常

### Q3: LLM 调用失败？

检查：
1. `DEEPSEEK_API_KEY` 是否有效
2. API 配额是否充足
3. 网络是否能访问 API 端点

### Q4: OpenDRG 如何集成？

当前使用模拟模式。真实集成步骤：

1. 获取 OpenDRG Python 包
2. 修改 `app/services/drg_grouper.py` 中的 `__init__` 方法
3. 更新 `group()` 方法调用真实引擎

## 相关文档

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Supabase Python 文档](https://supabase.com/docs/reference/python/introduction)
- [OpenAI API 文档](https://platform.openai.com/docs/api-reference)
- [DRG 前端开发文档](../docs/DRG-SETUP.md)

## 许可证

MIT

## 联系方式

- 项目主页：医疗质控系统
- 问题反馈：GitHub Issues

---

**最后更新**：2025-01-04
**版本**：v1.0.0
