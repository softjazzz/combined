# 🚀 医疗质控系统项目启动指南

**更新时间**: 2024-12-24  
**项目版本**: v2.0.0 (Python增强版)  
**适用环境**: 开发环境 & 生产环境

---

## 📋 **前置条件检查**

### **系统要求**
- **Node.js**: >= 18.0.0
- **Python**: >= 3.8
- **pnpm**: >= 8.0.0
- **PostgreSQL**: >= 13 (Supabase)
- **Redis**: >= 6.0 (可选，用于缓存)

### **环境变量配置**
在项目根目录创建 `.env` 文件：

```bash
# 数据库配置 (Supabase)
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# API配置
VITE_API_BASE_URL=http://localhost:8000
VITE_ENABLE_ENHANCED_API=true

# LLM服务配置
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_API_URL=https://api.deepseek.com

# Redis配置 (可选)
REDIS_URL=redis://localhost:6379

# 开发环境配置
NODE_ENV=development
DEBUG=true
```

---

## 🗄️ **数据库初始化**

### **1. Supabase设置**
```bash
# 如果使用本地Supabase
npx supabase start

# 或者使用云端Supabase
# 在 https://supabase.com 创建项目并获取连接信息
```

### **2. 数据库结构初始化**
```bash
# 初始化基础数据库结构
npm run db:init-base

# 验证数据库结构
npm run verify-schema

# 运行数据库迁移
npm run db:migrate

# 初始化质控规则
npm run db:init-rules

# 初始化综合规则系统
npm run init-comprehensive-rules

# 一键完整设置 (推荐)
npm run setup
```

---

## 🐍 **Python后端启动**

### **1. 安装Python依赖**
```bash
# 进入后端目录
cd backend

# 创建虚拟环境 (推荐)
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### **2. 创建requirements.txt** (如果不存在)
```bash
# 在backend目录创建requirements.txt
cat > requirements.txt << EOF
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
asyncpg==0.29.0
pydantic==2.5.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
aioredis==2.0.1
httpx==0.25.2
psutil==5.9.6
numpy==1.24.3
python-dotenv==1.0.0
EOF
```

### **3. 启动Python后端服务**
```bash
# 方式1: 直接运行
python main.py

# 方式2: 使用uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 方式3: 生产环境
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### **4. 验证后端服务**
```bash
# 检查健康状态
curl http://localhost:8000/health

# 查看API文档
# 浏览器访问: http://localhost:8000/docs
```

---

## 🌐 **前端启动**

### **1. 安装前端依赖**
```bash
# 返回项目根目录
cd ..

# 安装依赖 (使用pnpm)
pnpm install

# 或使用npm
npm install
```

### **2. 启动前端开发服务器**
```bash
# 使用pnpm (推荐)
pnpm dev

# 或使用npm
npm run dev

# 或使用现有脚本
./start_frontend.sh
```

### **3. 验证前端服务**
```bash
# 前端服务通常运行在: http://localhost:5173
# 浏览器访问查看界面
```

---

## 🔧 **完整启动流程**

### **开发环境一键启动**
```bash
# 1. 克隆项目并进入目录
cd examples/002medqc/MedQC0817

# 2. 安装前端依赖
pnpm install

# 3. 数据库初始化
npm run setup

# 4. 启动后端 (新终端)
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py

# 5. 启动前端 (新终端)
cd ..
pnpm dev
```

### **使用Docker启动** (推荐生产环境)
```bash
# 使用现有的docker-compose配置
docker-compose -f docker-compose.production.yml up -d

# 或者构建并启动
docker-compose up --build
```

---

## 📊 **服务验证**

### **后端服务检查**
```bash
# 1. 健康检查
curl http://localhost:8000/health

# 2. 系统信息
curl http://localhost:8000/api/system/info

# 3. 增强版AI服务状态
curl http://localhost:8000/api/v2/enhanced-ai-assistance/service-status

# 4. 增强版审核任务服务状态
curl http://localhost:8000/api/v2/enhanced-audit-tasks/health

# 5. 系统性能监控
curl http://localhost:8000/api/system/metrics
```

### **前端服务检查**
```bash
# 访问前端界面
# http://localhost:5173

# 检查API连接状态
# 在浏览器开发者工具中查看网络请求
```

### **数据库连接检查**
```bash
# 检查数据库表结构
npm run verify-schema

# 测试质控规则
npm run check-work-rules

# 运行AI分析测试
npm run test:ai
```

---

## 🚨 **常见问题解决**

### **端口冲突**
```bash
# 如果8000端口被占用，修改后端端口
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# 同时修改前端.env文件中的API地址
VITE_API_BASE_URL=http://localhost:8001
```

### **数据库连接失败**
```bash
# 检查Supabase连接
npm run verify-schema

# 重新初始化数据库
npm run db:init-base
```

### **Python依赖问题**
```bash
# 升级pip
python -m pip install --upgrade pip

# 清理并重新安装
pip cache purge
pip install -r requirements.txt --force-reinstall
```

### **前端构建问题**
```bash
# 清理node_modules
rm -rf node_modules pnpm-lock.yaml
pnpm install

# 或使用npm
rm -rf node_modules package-lock.json
npm install
```

---

## 🔄 **API版本切换**

### **使用增强版API (推荐)**
```bash
# 在.env文件中设置
VITE_ENABLE_ENHANCED_API=true

# 前端会自动使用v2增强版API
# /api/v2/enhanced-ai-assistance/*
# /api/v2/enhanced-audit-tasks/*
```

### **降级到原始API**
```bash
# 在.env文件中设置
VITE_ENABLE_ENHANCED_API=false

# 前端会使用v1兼容API
# /api/v1/ai-assistance/*
# /api/v1/audit-tasks/*
```

---

## 📈 **性能监控**

### **实时监控**
```bash
# 系统性能指标
curl http://localhost:8000/api/system/metrics

# AI服务性能统计
curl http://localhost:8000/api/v2/enhanced-ai-assistance/performance-stats

# 审核任务服务统计
curl http://localhost:8000/api/v2/enhanced-audit-tasks/service/statistics
```

### **日志查看**
```bash
# 后端日志
tail -f backend/logs/app.log

# 前端开发日志
# 在浏览器开发者工具的Console中查看
```

---

## 🎯 **开发建议**

### **开发环境配置**
- 使用 **pnpm** 作为包管理器 (更快的安装速度)
- 启用 **热重载** 进行实时开发
- 使用 **增强版API** 获得最佳性能
- 开启 **调试模式** 查看详细日志

### **生产环境部署**
- 使用 **Docker** 容器化部署
- 配置 **Redis** 缓存提升性能
- 启用 **HTTPS** 和安全配置
- 设置 **监控和告警** 系统

### **测试验证**
```bash
# 运行单元测试
npm run test:unit

# 运行端到端测试
npm run test:e2e

# 运行AI功能测试
npm run test:ai

# 运行完整工作流测试
npm run test:workflow
```

---

## 🎉 **启动成功标志**

当看到以下信息时，说明系统启动成功：

### **后端启动成功**
```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     医疗质控系统启动完成
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### **前端启动成功**
```
  VITE v6.0.5  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://192.168.x.x:5173/
  ➜  press h to show help
```

### **服务验证成功**
- ✅ 后端健康检查返回 `"status": "healthy"`
- ✅ 前端界面正常加载
- ✅ API调用正常响应
- ✅ 数据库连接正常

---

**🚀 恭喜！医疗质控系统已成功启动！**

现在您可以：
- 访问前端界面进行操作
- 使用增强版AI缺陷识别功能
- 创建和管理审核任务
- 查看系统性能监控
- 体验智能抽样和负载均衡

如有问题，请参考常见问题解决方案或查看详细日志。
