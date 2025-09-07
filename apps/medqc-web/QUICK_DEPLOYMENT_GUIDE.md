# 🚀 医疗质控系统快速部署指南

**GitHub 仓库**: https://github.com/softjazzz/MedQC0825.git  
**部署时间**: 预计 15-30 分钟  
**适用环境**: 开发环境 + 生产环境  

---

## 📋 **部署前准备**

### 🔧 **系统要求**
- **Node.js**: >= 18.0.0
- **Python**: >= 3.10
- **Git**: 最新版本
- **包管理器**: npm/pnpm/yarn

### 🌐 **外部服务**
- **Supabase 账户**: 用于数据库和认证
- **OpenAI API Key**: 用于 AI 质控分析（可选）

---

## 🚀 **一键部署脚本**

### **Step 1: 克隆项目**
```bash
# 克隆项目
git clone https://github.com/softjazzz/MedQC0825.git
cd MedQC0825

# 查看项目结构
ls -la
```

### **Step 2: 运行自动部署脚本**
```bash
# 运行一键部署脚本
./tools/deployment/quick_deploy.sh

# 如果权限不足，先添加执行权限
chmod +x tools/deployment/quick_deploy.sh
./tools/deployment/quick_deploy.sh
```

### **Step 3: 配置环境变量**
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量
nano .env  # 或使用其他编辑器
```

**环境变量配置**:
```env
# Supabase 配置
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key

# OpenAI 配置 (可选)
OPENAI_API_KEY=your-openai-key

# JWT 配置
JWT_SECRET_KEY=your-jwt-secret-key

# 开发环境配置
NODE_ENV=development
```

---

## 🗄️ **数据库初始化**

### **Step 1: 创建 Supabase 项目**
1. 访问 [Supabase](https://supabase.com/)
2. 创建新项目
3. 获取项目 URL 和 API Key
4. 更新 `.env` 文件

### **Step 2: 执行数据库脚本**
在 Supabase SQL Editor 中按顺序执行：

```sql
-- 1. 主要表结构初始化
-- 执行 database/setup/database_init_complete.sql

-- 2. 统计分析视图
-- 执行 database/setup/database_init_part2.sql

-- 3. 安全策略和权限
-- 执行 database/setup/database_init_part3.sql

-- 4. 向量搜索设置
-- 执行 database/setup/database_vector_search_setup.sql

-- 5. 验证数据库
-- 执行 database/setup/verify_database.sql
```

### **Step 3: 创建测试数据**
```sql
-- 插入测试科室
INSERT INTO departments (id, name, code, category) VALUES
('dept-001', '内科', 'INTERNAL', '临床科室'),
('dept-002', '外科', 'SURGERY', '临床科室'),
('dept-003', '质控科', 'QC', '管理科室');

-- 插入测试用户
INSERT INTO user_profiles (id, email, password_hash, full_name, role, department_id) VALUES
('user-001', 'admin@medqc.com', '$2b$12$hash...', '系统管理员', 'admin', 'dept-003'),
('user-002', 'doctor@medqc.com', '$2b$12$hash...', '张医生', 'doctor', 'dept-001'),
('user-003', 'qc@medqc.com', '$2b$12$hash...', '李质控', 'qc_manager', 'dept-003');
```

---

## 🎨 **前端部署**

### **开发环境启动**
```bash
# 安装依赖
npm install
# 或使用 pnpm (推荐)
pnpm install

# 启动开发服务器
npm run dev
# 或
pnpm dev

# 访问地址: http://localhost:5173
```

### **生产环境构建**
```bash
# 构建生产版本
npm run build
# 或
pnpm build

# 预览生产版本
npm run preview
# 或
pnpm preview
```

### **前端配置检查**
```bash
# 检查前端配置
node tools/testing/frontend_config_check.js

# 检查依赖
npm audit
```

---

## 🔧 **后端部署**

### **开发环境启动**
```bash
# 进入后端目录
cd production_system

# 创建虚拟环境 (推荐)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
python main.py

# 访问地址: http://localhost:8001
# API 文档: http://localhost:8001/docs
```

### **后端配置检查**
```bash
# 检查后端环境
python ../tools/testing/backend_environment_check.py

# 测试数据库连接
python -c "
from core.database import get_supabase_client
client = get_supabase_client()
result = client.table('departments').select('*').execute()
print(f'数据库连接成功，找到 {len(result.data)} 个科室')
"
```

---

## 🧪 **系统测试**

### **集成测试**
```bash
# 运行集成验证
python tools/testing/simple_integration_check.py

# 测试前后端连接
python tools/testing/test_frontend_backend_integration.py
```

### **API 测试**
```bash
# 测试认证 API
curl -X POST "http://localhost:8001/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@medqc.com",
    "password": "admin123",
    "role": "admin"
  }'

# 测试健康检查
curl http://localhost:8001/health
```

### **前端功能测试**
1. 访问 http://localhost:5173
2. 测试用户登录功能
3. 验证页面路由和组件加载
4. 检查 API 调用和数据展示

---

## 🐳 **Docker 部署**

### **使用 Docker Compose**
```bash
# 构建和启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### **单独构建镜像**
```bash
# 构建前端镜像
docker build -t medqc-frontend .

# 构建后端镜像
cd production_system
docker build -t medqc-backend .

# 运行容器
docker run -p 5173:5173 medqc-frontend
docker run -p 8001:8001 medqc-backend
```

---

## 🔍 **故障排除**

### **常见问题**

#### **1. 前端启动失败**
```bash
# 清除缓存
rm -rf node_modules package-lock.json
npm install

# 检查 Node.js 版本
node --version  # 应该 >= 18.0.0

# 检查端口占用
lsof -i :5173
```

#### **2. 后端启动失败**
```bash
# 检查 Python 版本
python --version  # 应该 >= 3.10

# 重新安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 检查环境变量
python -c "import os; print(os.getenv('VITE_SUPABASE_URL'))"
```

#### **3. 数据库连接失败**
```bash
# 检查 Supabase 配置
echo $VITE_SUPABASE_URL
echo $VITE_SUPABASE_ANON_KEY

# 测试网络连接
curl -I https://your-project.supabase.co

# 检查数据库表
python tools/testing/test_database_connection.py
```

#### **4. API 调用失败**
```bash
# 检查 CORS 配置
# 在 production_system/main.py 中确认 CORS 设置

# 检查防火墙
sudo ufw status

# 检查服务器日志
tail -f production_system/app.log
```

---

## 📊 **性能优化**

### **前端优化**
```bash
# 分析打包大小
npm run build -- --analyze

# 启用 gzip 压缩
# 在 vite.config.ts 中配置

# 启用缓存
# 配置 PWA 和 Service Worker
```

### **后端优化**
```python
# 启用数据库连接池
# 在 core/database.py 中配置

# 启用 Redis 缓存
# pip install redis
# 配置缓存中间件

# 启用异步处理
# 使用 asyncio 和 asyncpg
```

---

## 🔒 **安全配置**

### **生产环境安全**
```bash
# 1. 更新所有密钥
JWT_SECRET_KEY=$(openssl rand -hex 32)

# 2. 启用 HTTPS
# 配置 SSL 证书

# 3. 设置防火墙
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

# 4. 配置反向代理
# 使用 Nginx 或 Apache
```

### **数据库安全**
```sql
-- 启用行级安全
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- 创建安全策略
CREATE POLICY user_policy ON user_profiles
  FOR ALL USING (auth.uid() = id);
```

---

## 📈 **监控和日志**

### **应用监控**
```bash
# 安装监控工具
pip install prometheus-client
npm install @sentry/vue

# 配置健康检查端点
# GET /health
# GET /metrics
```

### **日志配置**
```python
# 配置结构化日志
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

---

## 🎯 **部署检查清单**

### **部署前检查**
- [ ] 环境变量配置完整
- [ ] 数据库连接正常
- [ ] 依赖包安装完成
- [ ] 端口配置正确
- [ ] 防火墙规则设置

### **部署后验证**
- [ ] 前端页面正常访问
- [ ] 后端 API 响应正常
- [ ] 用户登录功能正常
- [ ] 数据库操作正常
- [ ] 文件上传功能正常

### **生产环境检查**
- [ ] HTTPS 证书配置
- [ ] 数据库备份策略
- [ ] 监控和告警设置
- [ ] 日志收集配置
- [ ] 性能基准测试

---

## 🎉 **部署完成**

恭喜！医疗质控系统已成功部署。

**访问地址**:
- 前端应用: http://localhost:5173
- 后端 API: http://localhost:8001
- API 文档: http://localhost:8001/docs

**测试账户**:
- 管理员: admin@medqc.com / admin123
- 医生: doctor@medqc.com / doctor123
- 质控: qc@medqc.com / qc123

**下一步**:
1. 开始使用系统功能
2. 上传医疗记录进行测试
3. 配置质控规则
4. 邀请用户注册使用

**技术支持**: 查看项目文档或提交 GitHub Issue
