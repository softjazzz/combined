# 质控引擎使用说明

## 概述

质控引擎是一个基于规则的决策系统，用于医保质控场景。它能够根据预定义的规则对业务数据进行实时评估，并给出相应的决策（通过/警告/拦截）。

## 核心特性

- ✅ **高性能**：毫秒级响应，支持 1000+ 规则并发执行
- ✅ **可扩展**：插件化操作符设计，易于添加新功能
- ✅ **可追溯**：完整的审计日志和性能指标
- ✅ **双重保障**：支持数据库和 JSON 文件双重存储
- ✅ **灵活配置**：支持复杂的条件组合（AND/OR 嵌套）

## 快速开始

### 1. 启动服务

```bash
cd apps/yibao-web/backend
source venv/bin/activate
python main.py
```

服务将在 http://localhost:8002 启动

### 2. API 接口

#### 单次评估

```bash
curl -X POST http://localhost:8002/api/engine/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "prescription_create",
    "context": {
      "patient": {"name": "张三", "age": 10},
      "drug": {"category": "adult_only"}
    }
  }'
```

#### 批量评估

```bash
curl -X POST http://localhost:8002/api/engine/batch-evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "prescription_create",
    "contexts": [
      {"patient": {"age": 10}, "drug": {"category": "adult_only"}},
      {"patient": {"age": 30}, "drug": {"category": "normal"}}
    ]
  }'
```

#### 健康检查

```bash
curl http://localhost:8002/api/engine/health
```

#### 统计信息

```bash
curl http://localhost:8002/api/engine/stats
```

## 规则结构

### 基本规则示例

```json
{
  "code": "DRUG_AGE_001",
  "name": "儿童用药限制",
  "severity": "block",
  "conditions": {
    "all": [
      {"fact": "patient.age", "operator": "<", "value": 18},
      {"fact": "drug.category", "operator": "==", "value": "adult_only"}
    ]
  },
  "actions": [
    {
      "action_type": "intercept",
      "message_template": "患者 {patient.name} 不能使用成人药品"
    }
  ],
  "triggers": ["prescription_create"]
}
```

### 支持的操作符

- `==` - 等于
- `!=` - 不等于
- `>` - 大于
- `>=` - 大于等于
- `<` - 小于
- `<=` - 小于等于
- `in` - 包含于
- `not_in` - 不包含于
- `contains` - 字符串包含
- `not_contains` - 字符串不包含
- `regex` - 正则匹配
- `between` - 区间（值需为 [min, max]）
- `exists` - 存在性检查

### 条件组合

```json
{
  "conditions": {
    "all": [
      {"fact": "patient.age", "operator": "<", "value": 18},
      {
        "any": [
          {"fact": "drug.category", "operator": "==", "value": "adult_only"},
          {"fact": "drug.restricted", "operator": "==", "value": true}
        ]
      }
    ]
  }
}
```

## 模块说明

### 核心模块

- **dsl.py** - 规则数据模型定义
- **operators.py** - 操作符实现和注册
- **templating.py** - 消息模板渲染
- **evaluator.py** - 规则执行引擎
- **repository.py** - 规则加载和管理
- **audit.py** - 审计日志
- **metrics.py** - 性能指标收集
- **api.py** - RESTful API 接口

### 扩展操作符

```python
from engine.operators import register_operator

def my_custom_op(left, right):
    """自定义操作符"""
    return str(left).startswith(str(right))

# 注册操作符
register_operator("starts_with", my_custom_op)

# 在规则中使用
{
  "fact": "patient.name",
  "operator": "starts_with",
  "value": "张"
}
```

## 性能优化

1. **规则预编译**：规则在加载时编译为可执行函数
2. **短路求值**：AND/OR 条件遇到确定结果立即返回
3. **内存索引**：按触发器、药品代码等建立索引
4. **批量处理**：支持批量评估多个上下文

## 测试

### 运行单元测试

```bash
cd apps/yibao-web/backend
source venv/bin/activate
python -m pytest engine/test_engine.py -v
```

### 运行集成测试

```bash
python test_qc_engine.py
```

## 决策级别

- **PASS** - 通过，无违规
- **WARN** - 警告，有轻微违规
- **BLOCK** - 拦截，有严重违规

决策遵循"最严重原则"：如果有任何 BLOCK 级别的规则命中，最终决策为 BLOCK；如果有 WARN 但无 BLOCK，决策为 WARN；否则为 PASS。

## 部署建议

### 生产环境配置

1. 使用 Supabase 数据库存储规则
2. 启用审计日志数据库写入
3. 配置适当的缓存大小
4. 设置性能监控告警

### 环境变量

```bash
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_key
YIBAO_API_PORT=8002
```

## 常见问题

### Q: 如何添加新规则？

A: 可以通过以下方式：
1. 编辑 `medical_rules.json` 文件
2. 使用 API 接口动态加载
3. 通过数据库管理界面添加

### Q: 规则执行顺序是怎样的？

A: 规则并行执行，没有固定顺序。所有符合条件的规则都会被评估。

### Q: 如何处理大量规则？

A: 引擎已优化处理大量规则：
- 使用索引快速过滤
- 预编译减少解析开销
- 短路求值提升性能

## 联系支持

如有问题，请查看文档或提交 Issue。
