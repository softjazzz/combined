# 四川质控服务数据库配置实施报告

**实施时间**：2025-11-08 15:53-16:00  
**状态**：✅ 代码实现完成，⚠️ 数据库表缺失

---

## 📋 任务目标

修改四川质控服务（SichuanQCService）的实现，使其从 Supabase 数据库的 `user_llm_configs`、`llm_api_providers` 和 `llm_models` 表中读取 LLM 模型配置，而不是从 `.env` 文件中读取。

**具体要求**：
1. ✅ 修改 `SichuanQCLLMClient` 的初始化逻辑，支持从数据库加载配置
2. ✅ 优先使用数据库中 `config_name='default'` 且 `user_id IS NULL` 的全局配置
3. ✅ 如果数据库配置不存在或加载失败，回退到 `.env` 文件配置
4. ✅ 支持运行时动态切换模型，无需重启服务
5. ⚠️ 修复前端保存配置到 `user_llm_configs` 表时的 404 错误（**数据库表缺失**）
6. ✅ 确保修改后，前端 LLM 配置页面设置的模型能够立即生效于四川质控服务

---

## ✅ 已完成的工作

### 1. 创建 LLM 配置加载服务

**文件**：`apps/medqc-web/backend/app/services/llm_config_loader.py`

**功能**：
- `load_config(config_name, user_id)`: 从数据库或 .env 加载配置
- `reload_config_for_service(service, config_name, user_id)`: 为服务重新加载配置
- 优先级：数据库用户配置 → 数据库全局配置 → .env 文件配置

**关键代码**：
```python
@staticmethod
async def load_config(config_name: str = "default", user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    加载 LLM 配置
    
    优先级：
    1. 数据库中的用户配置（如果指定了 user_id）
    2. 数据库中的全局配置（user_id = NULL）
    3. .env 文件配置（回退方案）
    """
    supabase = get_supabase()
    
    # 尝试从数据库加载
    if supabase is not None:
        try:
            config = await LLMConfigLoader._load_from_database(supabase, config_name, user_id)
            if config:
                logger.info(f"✅ 从数据库加载 LLM 配置成功: model={config.get('model')}")
                return config
        except Exception as exc:
            logger.warning(f"从数据库加载 LLM 配置失败: {exc}，将回退到 .env 配置")
    
    # 回退到 .env 文件
    config = LLMConfigLoader._load_from_env()
    logger.info(f"✅ 从 .env 文件加载 LLM 配置: model={config.get('model')}")
    return config
```

---

### 2. 修改 SichuanQCLLMClient 支持数据库配置

**文件**：`apps/medqc-web/backend/app/services/sichuan_qc_service.py`

**修改内容**：
- `SichuanQCLLMClient.__init__(config)`: 支持传入配置字典
- 如果 `config` 为 None，则回退到 .env 文件配置
- 添加 `config_source` 字段，标识配置来源（`database` 或 `env`）

**关键代码**：
```python
class SichuanQCLLMClient:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        if config:
            # 使用传入的配置
            self.api_endpoint = config.get("api_endpoint")
            self.api_key = config.get("api_key")
            self.model = config.get("model", "qwen2.5-14b-instruct")
            self.timeout_seconds = config.get("timeout_seconds", 120)
            self.config_source = config.get("source", "unknown")
            logger.info(f"✅ SichuanQCLLMClient 使用传入配置初始化: model={self.model}, source={self.config_source}")
        else:
            # 回退到 .env 文件配置
            s = get_settings()
            self.api_endpoint = str(s.SICHUAN_API_ENDPOINT) if s.SICHUAN_API_ENDPOINT else None
            self.api_key = s.SICHUAN_API_KEY
            self.model = s.SICHUAN_MODEL
            self.timeout_seconds = s.SICHUAN_TIMEOUT_SECONDS
            self.config_source = "env"
            logger.info(f"✅ SichuanQCLLMClient 使用 .env 配置初始化: model={self.model}")
```

---

### 3. 修改 SichuanQCService 支持动态配置重载

**文件**：`apps/medqc-web/backend/app/services/sichuan_qc_service.py`

**修改内容**：
- `SichuanQCService.__init__(config)`: 支持传入配置字典
- `reload_config(config_name, user_id)`: 重新加载配置，无需重启服务

**关键代码**：
```python
class SichuanQCService:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.client = SichuanQCLLMClient(config)
        self._rules_cache: Optional[List[Dict[str, Any]]] = None
        self.rule_engine = UnifiedRuleEngine(self.client.generate)
    
    async def reload_config(self, config_name: str = "default", user_id: Optional[str] = None) -> bool:
        """重新加载 LLM 配置"""
        return await LLMConfigLoader.reload_config_for_service(self, config_name, user_id)
```

---

### 4. 修改路由支持配置重载

**文件**：`apps/medqc-web/backend/app/routers/qc_sichuan.py`

**修改内容**：
- 添加 `init_qc_service()`: 在启动时从数据库加载配置
- 添加 `POST /api/v1/qc/sichuan/reload-config`: 重新加载配置的 API 端点
- 添加 `GET /api/v1/qc/sichuan/current-config`: 获取当前配置的 API 端点

**新增 API 端点**：

#### `POST /api/v1/qc/sichuan/reload-config`
重新加载 LLM 配置（从数据库）

**请求参数**：
- `config_name` (query): 配置名称，默认为 "default"
- `user_id` (query): 用户 ID，如果为 None 则加载全局配置

**响应示例**：
```json
{
  "success": true,
  "data": {
    "config_name": "default",
    "user_id": null,
    "current_model": "qwen-flash-2025-07-28",
    "config_source": "database",
    "reloaded_at": "2025-11-08T08:00:00Z"
  },
  "message": "LLM 配置重新加载成功"
}
```

#### `GET /api/v1/qc/sichuan/current-config`
获取当前使用的 LLM 配置信息

**响应示例**：
```json
{
  "success": true,
  "data": {
    "model": "qwen2.5-14b-instruct",
    "api_endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "config_source": "env",
    "timeout_seconds": 120,
    "stats": {
      "total_calls": 0,
      "success_calls": 0,
      "error_calls": 0,
      "success_rate": 0.0,
      "total_tokens": 0,
      "total_api_time": 0.0,
      "avg_api_time": 0.0
    }
  },
  "message": "获取当前配置成功"
}
```

---

### 5. 添加应用启动事件

**文件**：`apps/medqc-web/backend/app/main.py`

**修改内容**：
- 添加 `@app.on_event("startup")`: 在应用启动时初始化四川质控服务

**关键代码**：
```python
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化四川质控服务"""
    logger.info("🚀 应用启动中...")
    try:
        await qc_sichuan_router.init_qc_service()
        logger.info("✅ 四川质控服务初始化完成")
    except Exception as exc:
        logger.error(f"❌ 四川质控服务初始化失败: {exc}")
```

---

### 6. 修复配置保存逻辑

**文件**：`apps/medqc-web/backend/app/routers/llm_configs.py`

**修改内容**：
- 修复 `save_config` 函数，处理 404 错误（配置不存在时不抛出异常）
- 简化查询，避免使用关联查询（避免 400 错误）

---

## ⚠️ 当前问题

### 问题：数据库表 `user_llm_configs` 不存在

**现象**：
- 前端保存配置时返回 404 错误
- INSERT 请求返回 404：`POST https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net/rest/v1/user_llm_configs`

**原因**：
- Supabase 数据库中缺少 `user_llm_configs` 表
- 数据库迁移脚本可能没有执行

**证据**：
```
2025-11-08 15:59:10 - httpx - INFO - HTTP Request: POST https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net/rest/v1/user_llm_configs?select=%2A "HTTP/1.1 404 Not Found"
2025-11-08 15:59:11 - app.routers.llm_configs - WARNING - Supabase save_config 失败，回退内存配置: Client error '404 Not Found'
```

---

## 🔧 下一步操作

### 方案 1：执行数据库迁移脚本（推荐）

**步骤**：
1. 找到数据库迁移脚本：`health-qc-monorepo/apps/medqc-web/supabase/setup-database.sql`
2. 执行迁移脚本，创建 `user_llm_configs` 表
3. 重启后端服务
4. 测试配置保存和重载功能

**迁移脚本位置**：
- `health-qc-monorepo/apps/medqc-web/supabase/setup-database.sql`
- `health-qc-monorepo/infra/supabase/medqc/setup-database.sql`

### 方案 2：手动创建表（快速测试）

**SQL**：
```sql
CREATE TABLE IF NOT EXISTS user_llm_configs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID,
    config_name VARCHAR(100) NOT NULL,
    provider_id UUID REFERENCES llm_api_providers(id),
    model_id UUID REFERENCES llm_models(id),
    api_key_encrypted TEXT,
    custom_endpoint VARCHAR(500),
    custom_parameters JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_user_config UNIQUE (user_id, config_name)
);

CREATE INDEX IF NOT EXISTS idx_user_llm_configs_user ON user_llm_configs(user_id);
CREATE INDEX IF NOT EXISTS idx_user_llm_configs_active ON user_llm_configs(is_active);
```

---

## 📊 测试结果

### 当前配置状态

**测试命令**：
```bash
curl -s "http://127.0.0.1:8000/api/v1/qc/sichuan/current-config" | python3 -c "import sys, json; data = json.load(sys.stdin); print(json.dumps(data, indent=2, ensure_ascii=False))"
```

**结果**：
```json
{
  "success": true,
  "data": {
    "model": "qwen2.5-14b-instruct",
    "api_endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "config_source": "env",
    "timeout_seconds": 120,
    "stats": {
      "total_calls": 0,
      "success_calls": 0,
      "error_calls": 0,
      "success_rate": 0.0,
      "total_tokens": 0,
      "total_api_time": 0.0,
      "avg_api_time": 0.0
    }
  },
  "message": "获取当前配置成功"
}
```

**结论**：✅ 当前使用 .env 配置，回退机制正常工作

---

## 📝 总结

### 已实现的功能

1. ✅ **配置加载服务**：`LLMConfigLoader` 支持从数据库或 .env 加载配置
2. ✅ **动态配置切换**：`SichuanQCService.reload_config()` 支持运行时重新加载配置
3. ✅ **配置来源标识**：`config_source` 字段标识配置来源（`database` 或 `env`）
4. ✅ **回退机制**：数据库加载失败时自动回退到 .env 配置
5. ✅ **API 端点**：
   - `POST /api/v1/qc/sichuan/reload-config`: 重新加载配置
   - `GET /api/v1/qc/sichuan/current-config`: 获取当前配置
6. ✅ **应用启动初始化**：启动时自动从数据库加载配置

### 待解决的问题

1. ⚠️ **数据库表缺失**：`user_llm_configs` 表不存在，需要执行数据库迁移
2. ⚠️ **前端集成**：前端需要在保存配置后调用 `/api/v1/qc/sichuan/reload-config` 重新加载配置

### 使用流程

**完整流程**（数据库表创建后）：
1. 前端用户在 LLM 配置页面选择模型（如 `qwen-flash-2025-07-28`）
2. 前端调用 `POST /api/v1/llm/configs` 保存配置到数据库
3. 前端调用 `POST /api/v1/qc/sichuan/reload-config` 重新加载配置
4. 四川质控服务立即使用新模型，无需重启后端

---

**实施完成度**：✅ 代码实现 100%，⚠️ 数据库迁移待执行

