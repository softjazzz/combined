# 开发环境端口分配标准

## 🚀 端口分配规范

MedQC 本地开发使用以下端口。前端通过 Vite 将 API 请求代理到 FastAPI。部署端口以对应发布手册为准。详见[活文档索引](docs/INDEX.md)。

### 前端服务
| 服务名称 | 端口 | 用途 | 访问地址 |
|---------|------|------|----------|
| medqc-web | 3000 | 医疗质控系统前端 | http://localhost:3000 |
| yibao-web | 3008 | 医保质控系统前端 | http://localhost:3008 |

### 后端服务
| 服务名称 | 端口 | 用途 | 访问地址 |
|---------|------|------|----------|
| medqc-api | 8001 | 医疗质控API服务 | http://localhost:8001 |
| yibao-api | 8008 | 医保质控API服务 | http://localhost:8008 |

### 数据库服务
| 服务名称 | 端口 | 用途 | 访问地址 |
|---------|------|------|----------|
| PostgreSQL | 5432 | 主数据库 | localhost:5432 |
| Redis | 6379 | 缓存服务 | localhost:6379 |

### 开发工具
| 服务名称 | 端口 | 用途 | 访问地址 |
|---------|------|------|----------|
| Storybook (medqc) | 6006 | UI组件展示 | http://localhost:6006 |
| Storybook (yibao) | 6007 | UI组件展示 | http://localhost:6007 |

## 🔧 端口配置管理

### 1. Vite配置 (前端)
```javascript
// apps/medqc-web/vite.config.mjs
export default defineConfig({
  server: {
    port: 3000,
    host: true,
    strictPort: true // 端口被占用时不自动尝试其他端口
  }
})

// apps/yibao-web/vite.config.ts
export default defineConfig({
  server: {
    port: 3008,
    host: true,
    strictPort: true
  }
})
```

### 2. FastAPI 配置（后端）

按 [MedQC 本地启动](apps/medqc-web/README.md#本地启动) 配置开发库和 JWT 密钥。Vite 默认代理到 `http://localhost:8001`，可通过 `VITE_BACKEND_TARGET` 指定开发后端。

```bash
cd apps/medqc-web/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

# YiBao 后端（保持原端口 8008，如有需要可参见其 README）
```

## 🚨 端口冲突处理

### 检查端口占用
```bash
# 检查特定端口
lsof -ti:3000

# 检查所有项目相关端口
lsof -ti:3000,3008,8001,8008,5432,6379
```

### 清理占用的端口
```bash
# 清理特定端口
kill -9 $(lsof -ti:3000)

# 批量清理项目端口
kill -9 $(lsof -ti:3000,3008,8001,8008) 2>/dev/null || true
```

### 启动服务脚本
```bash
# 根目录添加启动脚本
pnpm dev:medqc       # 启动 MedQC 前端
pnpm dev:yibao       # 启动 YiBao 前端
pnpm dev:all         # 启动两个前端
```

## 📝 开发环境检查清单

- [ ] medqc-web 在 3000 端口正常访问
- [ ] yibao-web 在 3008 端口正常访问
- [ ] 后端API服务正常响应
- [ ] 数据库连接正常
- [ ] 无端口冲突警告

## 🔄 更新记录

| 日期 | 变更内容 | 修改人 |
|------|----------|--------|
| 2024-09-14 | 初始端口分配标准 | 开发团队 |

---
**注意**: 修改端口配置后，请更新相关的环境变量和API调用地址。
