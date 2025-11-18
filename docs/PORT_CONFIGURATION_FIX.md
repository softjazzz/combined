# 端口配置修正记录

## 📋 问题描述

在项目中发现多个配置文件中的端口配置不一致，导致混淆和潜在的启动问题。

## 🎯 标准端口分配

根据 `DEVELOPMENT_PORTS.md` 文档，项目的标准端口分配如下：

### 前端服务
| 服务名称 | 端口 | 用途 | 访问地址 |
|---------|------|------|----------|
| medqc-web | 3000 | 医疗质控系统前端 | http://localhost:3000 |
| yibao-web | 3008 | 医保质控系统前端 | http://localhost:3008 |

### 后端服务
| 服务名称 | 端口 | 用途 | 访问地址 |
|---------|------|------|----------|
| **medqc-api** | **8000** | 医疗质控API服务（主后端） | http://localhost:8000 |
| **medqc-drg-api** | **8001** | DRG相关API服务（独立后端） | http://localhost:8001 |
| yibao-api | 8008 | 医保质控API服务 | http://localhost:8008 |

---

## 🔍 发现的配置冲突

### 冲突 1：主后端端口配置错误

**问题文件**：
1. `apps/medqc-web/backend/app/config.py` 第 27 行
2. `apps/medqc-web/backend/.env.example` 第 67 行
3. `apps/medqc-web/backend/README_REFACTOR.md` 第 19 行
4. `scripts/start_backend.sh` 第 11 行

**错误配置**：`api_port: int = 8001` 或 `API_PORT=8001`

**正确配置**：`api_port: int = 8000` 或 `API_PORT=8000`

**原因**：主后端（medqc-api）应该运行在 8000 端口，与前端 Vite 代理配置一致。

---

## ✅ 已修正的文件

### 1. `apps/medqc-web/backend/app/config.py`

**修改前**：
```python
# API配置
api_host: str = "0.0.0.0"
api_port: int = 8001
```

**修改后**：
```python
# API配置
api_host: str = "0.0.0.0"
api_port: int = 8000  # 修正：根据 DEVELOPMENT_PORTS.md，medqc-api 标准端口为 8000
```

---

### 2. `apps/medqc-web/backend/.env.example`

**修改前**：
```bash
# API 服务器端口（默认: 8001）
API_PORT=8001
```

**修改后**：
```bash
# API 服务器端口（默认: 8000，根据 DEVELOPMENT_PORTS.md 标准）
API_PORT=8000
```

---

### 3. `apps/medqc-web/backend/README_REFACTOR.md`

**修改前**：
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

**修改后**：
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### 4. `scripts/start_backend.sh`

**修改前**：
```bash
PORT="${BACKEND_PORT:-8001}"
```

**修改后**：
```bash
PORT="${BACKEND_PORT:-8000}"  # 修正：根据 DEVELOPMENT_PORTS.md，medqc-api 标准端口为 8000
```

---

## 🔄 前端代理配置（已正确）

`apps/medqc-web/vite.config.ts` 中的代理配置是正确的：

```typescript
proxy: {
  // DRG 相关接口需要转发到新的后端服务
  '/api/v1/drg': {
    target: 'http://127.0.0.1:8001',  // ✅ DRG 后端（独立服务）
    changeOrigin: true,
    secure: false
  },
  // 其余历史接口保持指向原有 medqc 后端
  '/api': {
    target: 'http://127.0.0.1:8000',  // ✅ 主后端
    changeOrigin: true,
    secure: false
  }
}
```

**说明**：
- `/api/v1/drg/*` → 8001 端口（DRG 独立后端）
- `/api/*` → 8000 端口（主后端）

---

## 📝 未修改的文件（正确配置）

以下文件中的 8001 端口配置是**正确的**，因为它们属于 DRG 独立后端：

1. `apps/medqc-web/backend-fastapi/start.sh` - DRG 后端启动脚本
2. `apps/medqc-web/backend-fastapi/app/config.py` - DRG 后端配置

---

## 🚀 启动命令

### 主后端（medqc-api）- 端口 8000
```bash
cd health-qc-monorepo/apps/medqc-web/backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### DRG 后端（medqc-drg-api）- 端口 8001
```bash
cd health-qc-monorepo/apps/medqc-web/backend-fastapi
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 前端（medqc-web）- 端口 3000
```bash
cd health-qc-monorepo/apps/medqc-web
pnpm dev
```

---

## ✅ 验证清单

- [x] 主后端配置文件统一为 8000 端口
- [x] DRG 后端保持 8001 端口
- [x] 前端代理配置正确
- [x] 启动脚本端口正确
- [x] 文档说明清晰

---

## 📊 端口使用总结

| 端口 | 服务 | 用途 |
|------|------|------|
| 3000 | medqc-web | 医疗质控前端 |
| 8000 | medqc-api | 医疗质控主后端（质控规则、病历管理等） |
| 8001 | medqc-drg-api | DRG 相关后端（独立服务） |

---

## 🔧 后续建议

1. **环境变量检查**：如果有 `.env` 文件，请确保 `API_PORT=8000`
2. **进程检查**：启动前检查端口占用：`lsof -ti:8000`
3. **文档更新**：所有新文档都应引用 `DEVELOPMENT_PORTS.md` 作为端口标准

---

**修正日期**：2024-11-08  
**修正人**：Claude (Augment Agent)  
**相关文档**：`DEVELOPMENT_PORTS.md`

