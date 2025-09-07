# 🚀 病案质控系统部署指南

## 📋 部署前准备

### 🔧 系统要求

**服务器配置**
- **CPU**: 4核心以上
- **内存**: 8GB以上
- **存储**: 100GB以上 SSD
- **网络**: 100Mbps以上带宽

**软件环境**
- **Node.js**: 18.x 或更高版本
- **npm**: 9.x 或更高版本
- **Git**: 最新版本

### 🌐 第三方服务

**必需服务**
1. **Supabase账号** - 数据库和认证服务
2. **DeepSeek API Key** - AI分析服务
3. **域名和SSL证书** - 生产环境访问

## 📦 快速部署

### 1. 克隆项目

```bash
# 克隆项目代码
git clone <repository-url>
cd icd

# 安装依赖
npm install
```

### 2. 环境配置

创建 `.env` 文件：

```bash
# 复制环境变量模板
cp .env.example .env
```

编辑 `.env` 文件：

```env
# Supabase配置
VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key

# DeepSeek AI配置
VITE_DEEPSEEK_API_KEY=your_deepseek_api_key

# 应用配置
VITE_APP_TITLE=智能病案质控系统
VITE_APP_VERSION=1.0.0
VITE_APP_ENV=production

# 可选配置
VITE_ENABLE_MOCK=false
VITE_ENABLE_DEBUG=false
```

### 3. 数据库初始化

```bash
# 验证数据库连接
npm run verify:database

# 创建数据库表结构
npm run setup:database

# 优化数据库索引
npm run optimize:database
```

### 4. 构建和部署

```bash
# 运行系统验证
npm run verify:system

# 构建生产版本
npm run build

# 预览构建结果
npm run preview
```

## 🔧 详细配置

### Supabase配置

1. **创建Supabase项目**
   - 访问 [supabase.com](https://supabase.com)
   - 创建新项目
   - 获取项目URL和API密钥

2. **数据库设置**
   ```sql
   -- 启用必要的扩展
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   CREATE EXTENSION IF NOT EXISTS "pg_trgm";
   
   -- 创建数据库表
   -- (表结构已在 database/schema.sql 中定义)
   ```

3. **RLS策略配置**
   ```sql
   -- 启用行级安全
   ALTER TABLE medical_records ENABLE ROW LEVEL SECURITY;
   ALTER TABLE qc_results ENABLE ROW LEVEL SECURITY;
   
   -- 创建安全策略
   -- (策略已在 database/policies.sql 中定义)
   ```

### DeepSeek API配置

1. **获取API密钥**
   - 访问 [DeepSeek官网](https://platform.deepseek.com)
   - 注册账号并获取API密钥
   - 配置API调用限制和计费

2. **API测试**
   ```bash
   # 测试API连接
   npm run test:deepseek-api
   ```

## 🌐 生产部署

### 方式一：Vercel部署 (推荐)

1. **连接GitHub**
   ```bash
   # 推送代码到GitHub
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   ```

2. **Vercel配置**
   - 访问 [vercel.com](https://vercel.com)
   - 导入GitHub项目
   - 配置环境变量
   - 部署项目

3. **环境变量设置**
   ```
   VITE_SUPABASE_URL=your_supabase_url
   VITE_SUPABASE_ANON_KEY=your_supabase_key
   VITE_DEEPSEEK_API_KEY=your_deepseek_key
   VITE_APP_ENV=production
   ```

### 方式二：Nginx + PM2部署

1. **构建项目**
   ```bash
   npm run build
   ```

2. **Nginx配置**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       # 重定向到HTTPS
       return 301 https://$server_name$request_uri;
   }
   
   server {
       listen 443 ssl http2;
       server_name your-domain.com;
       
       # SSL证书配置
       ssl_certificate /path/to/certificate.crt;
       ssl_certificate_key /path/to/private.key;
       
       # 静态文件服务
       location / {
           root /path/to/dist;
           try_files $uri $uri/ /index.html;
           
           # 缓存配置
           location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
               expires 1y;
               add_header Cache-Control "public, immutable";
           }
       }
       
       # API代理 (如果需要)
       location /api/ {
           proxy_pass http://localhost:3000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

3. **PM2进程管理** (如果有后端服务)
   ```bash
   # 安装PM2
   npm install -g pm2
   
   # 启动应用
   pm2 start ecosystem.config.js
   
   # 设置开机自启
   pm2 startup
   pm2 save
   ```

### 方式三：Docker部署

1. **Dockerfile**
   ```dockerfile
   FROM node:18-alpine AS builder
   
   WORKDIR /app
   COPY package*.json ./
   RUN npm ci --only=production
   
   COPY . .
   RUN npm run build
   
   FROM nginx:alpine
   COPY --from=builder /app/dist /usr/share/nginx/html
   COPY nginx.conf /etc/nginx/nginx.conf
   
   EXPOSE 80
   CMD ["nginx", "-g", "daemon off;"]
   ```

2. **构建和运行**
   ```bash
   # 构建镜像
   docker build -t icd-system .
   
   # 运行容器
   docker run -d -p 80:80 --name icd-app icd-system
   ```

3. **Docker Compose**
   ```yaml
   version: '3.8'
   services:
     app:
       build: .
       ports:
         - "80:80"
       environment:
         - VITE_SUPABASE_URL=${SUPABASE_URL}
         - VITE_SUPABASE_ANON_KEY=${SUPABASE_KEY}
         - VITE_DEEPSEEK_API_KEY=${DEEPSEEK_KEY}
       restart: unless-stopped
   ```

## 📊 监控和维护

### 性能监控

1. **系统监控面板**
   - 访问 `/admin/monitor` 查看系统状态
   - 监控API响应时间和错误率
   - 查看缓存命中率和性能指标

2. **日志监控**
   ```bash
   # 查看应用日志
   tail -f /var/log/nginx/access.log
   tail -f /var/log/nginx/error.log
   
   # PM2日志 (如果使用)
   pm2 logs
   ```

3. **性能测试**
   ```bash
   # 运行性能测试
   npm run test:performance
   
   # 生成性能报告
   npm run report:performance
   ```

### 定期维护

1. **数据库维护**
   ```bash
   # 数据库性能分析
   npm run analyze:database
   
   # 清理过期数据
   npm run cleanup:database
   
   # 备份数据库
   npm run backup:database
   ```

2. **系统更新**
   ```bash
   # 检查依赖更新
   npm audit
   npm update
   
   # 运行系统验证
   npm run verify:system
   
   # 重新部署
   npm run deploy
   ```

## 🔧 故障排除

### 常见问题

1. **API连接失败**
   ```bash
   # 检查环境变量
   echo $VITE_SUPABASE_URL
   echo $VITE_DEEPSEEK_API_KEY
   
   # 测试API连接
   npm run test:api-connection
   ```

2. **数据库连接问题**
   ```bash
   # 验证数据库连接
   npm run verify:database
   
   # 检查数据库状态
   npm run status:database
   ```

3. **构建失败**
   ```bash
   # 清理缓存
   npm run clean
   rm -rf node_modules
   npm install
   
   # 重新构建
   npm run build
   ```

4. **性能问题**
   ```bash
   # 运行性能诊断
   npm run diagnose:performance
   
   # 查看性能报告
   npm run report:performance
   ```

### 日志分析

1. **应用日志**
   - 错误日志: `/logs/error.log`
   - 访问日志: `/logs/access.log`
   - 性能日志: `/logs/performance.log`

2. **监控告警**
   - 响应时间超过5秒
   - 错误率超过5%
   - 缓存命中率低于50%
   - 磁盘使用率超过80%

## 🔒 安全配置

### HTTPS配置

1. **SSL证书**
   ```bash
   # 使用Let's Encrypt
   sudo certbot --nginx -d your-domain.com
   ```

2. **安全头配置**
   ```nginx
   add_header X-Frame-Options "SAMEORIGIN" always;
   add_header X-Content-Type-Options "nosniff" always;
   add_header X-XSS-Protection "1; mode=block" always;
   add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
   ```

### 访问控制

1. **IP白名单** (可选)
   ```nginx
   location /admin {
       allow 192.168.1.0/24;
       deny all;
   }
   ```

2. **基础认证** (可选)
   ```nginx
   location /admin {
       auth_basic "Admin Area";
       auth_basic_user_file /etc/nginx/.htpasswd;
   }
   ```

## 📞 技术支持

### 联系方式

- **技术支持邮箱**: support@example.com
- **紧急联系电话**: 400-123-4567
- **在线文档**: https://docs.example.com

### 支持服务

- **7x24小时技术支持**
- **远程协助和故障排除**
- **定期系统健康检查**
- **性能优化建议**

---

**部署完成后，请访问系统监控面板确认所有服务正常运行！** 🎉
