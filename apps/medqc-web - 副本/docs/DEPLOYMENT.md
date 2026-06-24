# 🚀 部署指南

本文档详细介绍了医疗质控系统的部署方法和配置。

## 📋 部署前准备

### 系统要求
- **操作系统**: Ubuntu 20.04+ / CentOS 8+ / macOS 10.15+
- **CPU**: 4核心以上
- **内存**: 8GB以上
- **存储**: 100GB SSD
- **网络**: 100Mbps带宽

### 软件依赖
- Docker 20.10+
- Docker Compose 2.0+
- Node.js 18+
- Python 3.12+
- PostgreSQL 15+ (可选)
- Redis 7+ (可选)

## 🐳 Docker 部署（推荐）

### 1. 创建 Docker 配置

创建 `docker-compose.prod.yml`：

```yaml
version: '3.8'

services:
  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "80:80"
      - "443:443"
    environment:
      - NODE_ENV=production
      - VITE_API_BASE_URL=https://api.yourdomain.com
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - backend

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://medqc:${DB_PASSWORD}@db:5432/medqc
      - REDIS_URL=redis://redis:6379
      - JWT_SECRET=${JWT_SECRET}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - db
      - redis
    volumes:
      - ./uploads:/app/uploads

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=medqc
      - POSTGRES_USER=medqc
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - frontend
      - backend

volumes:
  postgres_data:
  redis_data:
```

### 2. 创建 Dockerfile

前端 Dockerfile：
```dockerfile
# Dockerfile.frontend
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

后端 Dockerfile：
```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3. 环境变量配置

创建 `.env.prod`：
```env
# 数据库配置
DB_PASSWORD=your_secure_password_here

# JWT配置
JWT_SECRET=your_jwt_secret_key_here

# OpenAI配置
OPENAI_API_KEY=your_openai_api_key_here

# 域名配置
DOMAIN=yourdomain.com
API_DOMAIN=api.yourdomain.com

# SSL配置
SSL_CERT_PATH=/etc/nginx/ssl/cert.pem
SSL_KEY_PATH=/etc/nginx/ssl/key.pem
```

### 4. 启动服务

```bash
# 构建并启动所有服务
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 查看服务状态
docker-compose -f docker-compose.prod.yml ps

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f
```

## 🔧 手动部署

### 1. 后端部署

```bash
# 创建虚拟环境
cd backend
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
export DATABASE_URL="postgresql://user:pass@localhost/medqc"
export JWT_SECRET="your-secret-key"
export OPENAI_API_KEY="your-openai-key"

# 启动服务
uvicorn main_api:app --host 0.0.0.0 --port 8001 --workers 4
```

### 2. 前端部署

```bash
# 安装依赖
npm install

# 构建生产版本
npm run build

# 使用 nginx 或其他 web 服务器托管 dist 目录
sudo cp -r dist/* /var/www/html/
```

### 3. 数据库设置

```sql
-- 创建数据库
CREATE DATABASE medqc;
CREATE USER medqc WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE medqc TO medqc;

-- 创建表结构（示例）
\c medqc;

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    department VARCHAR(255),
    roles TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE medical_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_name VARCHAR(255) NOT NULL,
    patient_age INTEGER,
    patient_gender VARCHAR(10),
    department VARCHAR(255),
    admission_date DATE,
    record_type VARCHAR(50),
    content TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE qc_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID REFERENCES medical_records(id),
    overall_score INTEGER,
    overall_grade VARCHAR(5),
    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    issues JSONB,
    suggestions JSONB,
    rule_results JSONB
);
```

## 🔒 SSL/HTTPS 配置

### 1. 获取 SSL 证书

使用 Let's Encrypt：
```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d yourdomain.com -d api.yourdomain.com

# 自动续期
sudo crontab -e
# 添加：0 12 * * * /usr/bin/certbot renew --quiet
```

### 2. Nginx 配置

```nginx
# nginx.conf
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 📊 监控和日志

### 1. 健康检查

```bash
# 检查服务状态
curl -f http://localhost:8001/api/v1/health || exit 1

# 检查数据库连接
docker-compose exec db pg_isready -U medqc
```

### 2. 日志管理

```bash
# 查看应用日志
docker-compose logs -f backend

# 设置日志轮转
sudo logrotate -d /etc/logrotate.d/medqc
```

### 3. 监控配置

使用 Prometheus + Grafana：
```yaml
# monitoring/docker-compose.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

## 🔄 备份和恢复

### 1. 数据库备份

```bash
# 创建备份
docker-compose exec db pg_dump -U medqc medqc > backup_$(date +%Y%m%d_%H%M%S).sql

# 恢复备份
docker-compose exec -T db psql -U medqc medqc < backup_20240825_120000.sql
```

### 2. 文件备份

```bash
# 备份上传文件
tar -czf uploads_backup_$(date +%Y%m%d).tar.gz uploads/

# 备份配置文件
tar -czf config_backup_$(date +%Y%m%d).tar.gz .env* docker-compose*.yml nginx.conf
```

## 🚨 故障排除

### 常见问题

1. **服务无法启动**
   ```bash
   # 检查端口占用
   sudo netstat -tlnp | grep :8001
   
   # 检查日志
   docker-compose logs backend
   ```

2. **数据库连接失败**
   ```bash
   # 检查数据库状态
   docker-compose exec db pg_isready
   
   # 检查连接字符串
   echo $DATABASE_URL
   ```

3. **前端无法访问后端**
   ```bash
   # 检查 CORS 配置
   curl -H "Origin: https://yourdomain.com" \
        -H "Access-Control-Request-Method: GET" \
        -H "Access-Control-Request-Headers: X-Requested-With" \
        -X OPTIONS \
        http://localhost:8001/api/v1/health
   ```

## 📈 性能优化

### 1. 数据库优化
- 创建适当的索引
- 配置连接池
- 定期执行 VACUUM

### 2. 缓存配置
- Redis 缓存热点数据
- CDN 加速静态资源
- 浏览器缓存策略

### 3. 负载均衡
```nginx
upstream backend {
    server backend1:8000;
    server backend2:8000;
    server backend3:8000;
}
```

---

如需更多帮助，请查看 [故障排除指南](./TROUBLESHOOTING.md) 或联系技术支持。

