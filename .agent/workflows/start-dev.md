---
description: 启动本地开发服务器
---

# 启动本地开发环境

// turbo-all

## 步骤

1. 启动后端服务
```bash
cd apps/medqc-web/backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

2. 启动前端服务
```bash
cd apps/medqc-web && npm run dev
```

3. 确认服务状态
- 后端: http://localhost:8001
- 前端: http://localhost:3000

## 验证

使用浏览器工具导航到 http://localhost:3000 确认页面正常加载。
