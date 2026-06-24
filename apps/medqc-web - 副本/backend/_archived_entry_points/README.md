# 归档的入口文件

## 归档原因

这些文件是旧的后端入口文件，已被归档以解决 **P0-2: 后端路由重复定义** 问题。

### 问题描述

在代码审查中发现，后端存在多个入口文件，导致：
1. 路由定义重复
2. 维护困难
3. 容易引入 bug
4. 不清楚哪个是当前使用的入口

### 归档文件列表

| 文件名 | 大小 | 说明 | 归档日期 |
|--------|------|------|----------|
| `main_api.py` | 154KB | 原始的单体入口文件，包含所有路由 | 2025-10-08 |
| `main_api_simplified.py` | 9.8KB | 简化版入口文件 | 2025-10-08 |
| `main_api_with_supabase.py` | 35KB | 集成 Supabase 的版本 | 2025-10-08 |
| `main_enhanced.py` | 4.6KB | 增强版入口文件 | 2025-10-08 |
| `main_api_complete.py` | 19KB | 完整版入口文件 | 2025-10-08 |
| `main_simple.py` | 8KB | 简单版入口文件 | 2025-10-08 |

**总计**: 6 个文件，约 231KB 代码

## 当前使用的入口文件

**唯一的入口文件**: `app/main.py`

启动命令:
```bash
uvicorn app.main:app --reload --port 8001
```

### 架构说明

新的模块化架构：
```
backend/
├── app/
│   ├── main.py              # 唯一入口文件
│   ├── core/                # 核心配置
│   │   ├── settings.py
│   │   ├── logging.py
│   │   └── middleware_errors.py
│   ├── routers/             # 路由模块（18个）
│   │   ├── system.py
│   │   ├── auth.py
│   │   ├── records.py
│   │   ├── qc.py
│   │   ├── qc_sichuan.py
│   │   ├── tools.py
│   │   ├── ingest.py
│   │   ├── medical_documents.py
│   │   ├── debug.py
│   │   ├── llm_info.py
│   │   ├── qc_llm_configs.py
│   │   ├── semantic_rules.py
│   │   ├── tasks.py
│   │   ├── classification.py
│   │   ├── llm_configs.py
│   │   ├── medical_records_alias.py
│   │   ├── reports.py
│   │   └── proxy.py
│   ├── schemas/             # 数据模型
│   └── services/            # 业务逻辑
└── _archived_entry_points/  # 归档的旧入口文件
```

## 迁移说明

### 如果需要恢复某个功能

1. **检查功能是否已在新架构中实现**
   - 查看 `app/routers/` 目录下的路由模块
   - 查看 `app/services/` 目录下的服务模块

2. **如果功能缺失，从归档文件中提取**
   ```bash
   # 查看归档文件中的路由定义
   grep -n "@app\|@router" _archived_entry_points/main_api.py
   
   # 提取特定功能到新的路由模块
   # 例如：提取某个路由到 app/routers/new_feature.py
   ```

3. **在新架构中实现**
   - 在 `app/routers/` 中创建新的路由模块
   - 在 `app/main.py` 中注册路由
   - 添加单元测试

### 回滚方案

如果新架构出现严重问题，可以临时回滚：

```bash
# 1. 恢复旧的入口文件
cp _archived_entry_points/main_api.py ../main_api.py

# 2. 修改启动命令
uvicorn main_api:app --reload --port 8001

# 3. 报告问题并尽快修复新架构
```

## 删除计划

这些归档文件将在以下时间点删除：

- **第一阶段** (当前): 归档文件，保留备份
- **第二阶段** (2周后): 确认新架构稳定，所有功能正常
- **第三阶段** (1个月后): 完全删除归档文件

## 相关文档

- [代码审查报告](../../../../docs/代码审查报告_2025Q1.md) - P0-2 问题详情
- [开发计划](../../../../docs/开发计划_2025Q1.md) - 第一阶段任务
- [TDD 技术设计文档](../../../../docs/TDD_病案质控系统技术设计文档.md) - 系统架构设计

## 验证清单

归档后请确认：

- [x] 后端启动正常 (`uvicorn app.main:app --reload --port 8001`)
- [x] API 文档可访问 (http://localhost:8001/docs)
- [x] 所有路由正常工作
- [x] 前端可以正常调用后端 API
- [x] 没有路由冲突
- [x] 没有导入错误

## 联系方式

如有问题，请联系开发团队或查看相关文档。

