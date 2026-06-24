# 后端端口例外清单

最后更新：2026-03-10

## 目的

本项目当前约定：

- 主 `medqc-web` 后端开发端口统一为 `8001`
- 主后端健康检查路径统一为 `/api/v1/health`

本清单用于记录仓库内仍然保留非 `8001` 端口或旧健康检查路径的例外，避免后续排查时误判。

## 已统一范围

以下范围已按主后端口径统一：

- `backend/README_REFACTOR.md`
- `docs/STARTUP_GUIDE.md`
- `docs/启动指南.md`
- `docs/README.md`
- 大部分历史启动/验收/交接文档
- `backend` 下测试脚本与工具脚本的主后端默认地址
- `src/services`
- `src/views/medical-records`
- `src/components/debug`
- `src/views/test`

## 仍保留的例外

### 1. 独立 KAG 服务

这些文件中的端口不是主 `medqc` 后端，而是 KAG 或相关网关地址，暂不并入 `8001`：

- `src/services/kag-qc-service.ts`
- `docs/deployment/KAG_DEPLOYMENT_GUIDE.md`

### 2. 本地 LLM / OpenAI 兼容端点

这些地址用于本地模型服务或 OpenAI 兼容接口，不属于主后端端口：

- `src/services/llmApiConfig.ts`
- `docs/LLM_API_SETUP_GUIDE.md`
- `docs/Environment-Configuration.md`
- `supabase/setup-database.sql`

### 3. 另一套后端或归档入口

以下目录/文件属于另一套后端实现、迁移残留或归档代码，保留原端口信息用于历史追踪：

- `backend-fastapi/`
- `backend/_archived_entry_points/`
- `backend/simple_api.py`

### 4. 8002 文档体系

以下文档描述的是另一套 `8002` 服务，不属于本次 `8001` 统一范围：

- `docs/Medical_QC_API.postman_collection.json`
- `docs/QUICK_REFERENCE.md`
- `docs/DATABASE_AND_API_DOCUMENTATION.md`

### 5. 仍待后续清理的辅助脚本/文档

这些文件仍保留非 `8001` 端口，但不属于本轮核心运行链路；后续如果要完全统一口径，再逐个处理：

- `tools/deployment/quick_start.sh`
- `tools/deployment/start_frontend.sh`
- `src/components/QCLLMConfig.vue` 以外的其他 LLM 配置相关组件

## 仍保留的旧健康检查口径

以下文件仍出现 `/api/health` 或 `/health`，但属于例外系统或兼容逻辑：

- `backend/app/core/middleware_api_version.py`
- `backend-fastapi/`
- `backend/_archived_entry_points/`
- `backend/simple_api.py`
- `docs/Medical_QC_API.postman_collection.json`

## 使用建议

排查主工作台、主前端、主后端联调问题时，默认只认以下口径：

```text
Backend: http://localhost:8001
Health:  http://localhost:8001/api/v1/health
```

如果扫描到其它端口，先对照本清单判断它是否属于独立系统或历史残留，再决定是否需要修改。
