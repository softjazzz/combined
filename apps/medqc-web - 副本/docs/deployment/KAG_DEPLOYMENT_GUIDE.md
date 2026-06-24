# KAG质控系统部署指南

## 📋 概述

本指南详细说明如何将现有的传统质控系统完全迁移到基于KAG框架的新架构。

## 🏗️ 新架构概览

```
前端 (Vue 3 + TypeScript)
    ↓ HTTP API
KAG API Gateway (FastAPI)
    ↓
┌─────────────────┬─────────────────┐
│  KAG-Builder    │  KAG-Solver     │
│  (信息抽取)      │  (质控推理)      │
└─────────────────┴─────────────────┘
    ↓                    ↓
领域知识图谱 (OpenSPG)    PostgreSQL (结果存储)
```

## 🛠️ 环境准备

### 1. 系统要求

```bash
# 操作系统
Ubuntu 20.04+ / CentOS 7+ / macOS 10.15+

# Python环境
Python 3.9+
pip 21.0+

# Node.js环境
Node.js 18.0+
pnpm 8.0+

# 数据库
PostgreSQL 14+
Redis 6.0+ (可选，用于缓存)
```

### 2. 安装KAG框架

```bash
# 1. 克隆KAG仓库
git clone https://github.com/OpenSPG/KAG.git
cd KAG

# 2. 安装KAG
pip install -e .

# 3. 安装OpenSPG服务
docker-compose up -d

# 4. 验证安装
python -c "import kag; print('KAG安装成功')"
```

### 3. 项目结构调整

```bash
MedQC0817/
├── kag_services/                 # 新增：KAG服务层
│   ├── medical_record_builder.py # KAG-Builder实现
│   ├── medical_qc_solver.py      # KAG-Solver实现
│   ├── kag_api_gateway.py        # API网关
│   └── requirements.txt          # Python依赖
├── kag_schemas/                  # 新增：KAG Schema定义
│   └── MedicalQC.schema         # 医疗质控Schema
├── src/                         # 现有前端代码
│   ├── services/
│   │   └── kag-qc-service.ts    # 新增：KAG服务适配器
│   └── ...
├── supabase/                    # 现有数据库配置
└── docker-compose.yml           # 新增：容器化部署
```

## 📦 安装和配置

### 1. 安装Python依赖

```bash
# 进入KAG服务目录
cd kag_services/

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

创建 `requirements.txt`:
```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
asyncio==3.4.3
python-multipart==0.0.6
aiofiles==23.2.1
openspg-kag>=0.1.0
psycopg2-binary==2.9.9
redis==5.0.1
```

### 2. 配置环境变量

创建 `.env` 文件：
```bash
# KAG配置
KAG_PROJECT_HOST_ADDR=http://127.0.0.1:8887
KAG_PROJECT_PATH=./kag_project
OPENSPG_SERVER_URL=http://127.0.0.1:8887

# LLM配置
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/medqc
REDIS_URL=redis://localhost:6379

# API配置
KAG_API_HOST=0.0.0.0
KAG_API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=./logs/kag_service.log
```

### 3. 初始化KAG项目

```bash
# 创建KAG项目
cd kag_services/
python -c "
from kag.builder import KAGBuilder
from kag.solver import KAGSolver
import os

# 初始化KAG项目
os.makedirs('./kag_project', exist_ok=True)
print('KAG项目初始化完成')
"

# 提交Schema到OpenSPG
cd ../
knext project restore --host_addr http://127.0.0.1:8887 --proj_path ./kag_project
knext schema commit --schema_path ./kag_schemas/MedicalQC.schema
```

### 4. 数据库迁移

添加KAG相关表到现有Supabase数据库：

```sql
-- 添加KAG分析记录表
CREATE TABLE IF NOT EXISTS kag_analyses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_id VARCHAR(255) UNIQUE NOT NULL,
  record_id UUID REFERENCES medical_records(id) ON DELETE CASCADE,
  instance_kg_data JSONB,
  analysis_result JSONB,
  processing_time FLOAT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 添加KAG规则执行表
CREATE TABLE IF NOT EXISTS kag_rule_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_id VARCHAR(255) REFERENCES kag_analyses(analysis_id),
  rule_id VARCHAR(100) NOT NULL,
  rule_name VARCHAR(255) NOT NULL,
  rule_type VARCHAR(50) NOT NULL,
  execution_result JSONB,
  execution_time FLOAT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 为现有qc_results表添加KAG字段
ALTER TABLE qc_results ADD COLUMN IF NOT EXISTS analysis_method VARCHAR(50) DEFAULT 'traditional';
ALTER TABLE qc_results ADD COLUMN IF NOT EXISTS kag_analysis_id VARCHAR(255);
ALTER TABLE qc_results ADD COLUMN IF NOT EXISTS processing_duration FLOAT;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_kag_analyses_record_id ON kag_analyses(record_id);
CREATE INDEX IF NOT EXISTS idx_kag_analyses_analysis_id ON kag_analyses(analysis_id);
CREATE INDEX IF NOT EXISTS idx_kag_rule_executions_analysis_id ON kag_rule_executions(analysis_id);
CREATE INDEX IF NOT EXISTS idx_qc_results_kag_analysis_id ON qc_results(kag_analysis_id);
```

## 🚀 部署步骤

### 1. 容器化部署

创建 `docker-compose.yml`:
```yaml
version: '3.8'

services:
  # KAG API Gateway
  kag-api:
    build:
      context: ./kag_services
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - KAG_PROJECT_HOST_ADDR=http://openspg:8887
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - DATABASE_URL=${DATABASE_URL}
    volumes:
      - ./kag_schemas:/app/kag_schemas
      - ./logs:/app/logs
    depends_on:
      - openspg
      - redis
    restart: unless-stopped

  # OpenSPG服务
  openspg:
    image: openspg/openspg:latest
    ports:
      - "8887:8887"
    environment:
      - SPRING_PROFILES_ACTIVE=docker
    volumes:
      - openspg_data:/data
    restart: unless-stopped

  # Redis缓存
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  # 前端应用
  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_KAG_API_URL=http://localhost:8000
      - VITE_SUPABASE_URL=${VITE_SUPABASE_URL}
      - VITE_SUPABASE_ANON_KEY=${VITE_SUPABASE_ANON_KEY}
    depends_on:
      - kag-api
    restart: unless-stopped

volumes:
  openspg_data:
  redis_data:
```

创建 `kag_services/Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建日志目录
RUN mkdir -p /app/logs

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "kag_api_gateway:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. 启动服务

```bash
# 1. 启动所有服务
docker-compose up -d

# 2. 检查服务状态
docker-compose ps

# 3. 查看日志
docker-compose logs -f kag-api

# 4. 健康检查
curl http://localhost:8000/health
```

### 3. 前端配置更新

修改 `src/main.ts`:
```typescript
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { pinia } from './stores'

// 导入KAG服务
import { kagQCService } from './services/kag-qc-service'

const app = createApp(App)

// 全局配置KAG服务
app.config.globalProperties.$kagQC = kagQCService

app.use(pinia)
app.use(router)
app.mount('#app')
```

更新质控分析组件：
```vue
<!-- src/views/QCAnalysis.vue -->
<template>
  <div class="qc-analysis">
    <h2>KAG智能质控分析</h2>
    
    <!-- 分析表单 -->
    <a-form @submit="handleAnalyze">
      <a-form-item label="病历内容">
        <a-textarea 
          v-model:value="recordContent" 
          :rows="10"
          placeholder="请输入病历内容..."
        />
      </a-form-item>
      
      <a-form-item label="分析模式">
        <a-select v-model:value="analysisMode">
          <a-select-option value="comprehensive">全面分析</a-select-option>
          <a-select-option value="focused">重点分析</a-select-option>
          <a-select-option value="quick">快速分析</a-select-option>
        </a-select>
      </a-form-item>
      
      <a-form-item>
        <a-button 
          type="primary" 
          html-type="submit"
          :loading="analyzing"
        >
          开始KAG分析
        </a-button>
      </a-form-item>
    </a-form>
    
    <!-- 分析结果 -->
    <div v-if="analysisResult" class="analysis-result">
      <a-card title="分析结果">
        <div class="summary">
          <p><strong>总分:</strong> {{ analysisResult.summary.totalScore }}</p>
          <p><strong>等级:</strong> {{ analysisResult.summary.grade }}</p>
          <p><strong>缺陷数量:</strong> {{ analysisResult.summary.defectsCount }}</p>
        </div>
        
        <a-divider />
        
        <div class="defects">
          <h4>发现的问题:</h4>
          <a-list 
            :data-source="analysisResult.defects"
            item-layout="vertical"
          >
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta
                  :title="item.ruleName"
                  :description="item.description"
                />
                <div>
                  <a-tag :color="getSeverityColor(item.severity)">
                    {{ item.severity }}
                  </a-tag>
                  <span>扣分: {{ item.deductionScore }}</span>
                </div>
                <p><strong>建议:</strong> {{ item.suggestion }}</p>
              </a-list-item>
            </template>
          </a-list>
        </div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { kagQCService } from '@/services/kag-qc-service'

const recordContent = ref('')
const analysisMode = ref('comprehensive')
const analyzing = ref(false)
const analysisResult = ref(null)

const handleAnalyze = async () => {
  if (!recordContent.value.trim()) {
    message.error('请输入病历内容')
    return
  }
  
  analyzing.value = true
  
  try {
    const result = await kagQCService.analyzeMedicalRecord({
      recordId: `record_${Date.now()}`,
      content: recordContent.value,
      analysisMode: analysisMode.value
    })
    
    analysisResult.value = result
    message.success('KAG分析完成')
  } catch (error) {
    message.error(`分析失败: ${error.message}`)
  } finally {
    analyzing.value = false
  }
}

const getSeverityColor = (severity: string) => {
  switch (severity) {
    case 'critical': return 'red'
    case 'major': return 'orange'
    case 'minor': return 'yellow'
    default: return 'blue'
  }
}
</script>
```

## 📊 监控和维护

### 1. 系统监控

```bash
# 查看KAG服务状态
curl http://localhost:8000/health

# 查看OpenSPG状态
curl http://localhost:8887/health

# 监控资源使用
docker stats
```

### 2. 日志管理

```bash
# 查看KAG API日志
docker-compose logs -f kag-api

# 查看特定时间段日志
docker-compose logs --since="2024-01-01T00:00:00" kag-api

# 日志轮转配置
echo "
/app/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    notifempty
    create 0644 root root
}
" > /etc/logrotate.d/kag-service
```

### 3. 性能优化

```python
# kag_services/performance_config.py
PERFORMANCE_CONFIG = {
    # 并发处理配置
    "max_concurrent_analyses": 10,
    "max_batch_size": 100,
    
    # 缓存配置
    "enable_result_cache": True,
    "cache_ttl_seconds": 3600,
    
    # 超时配置
    "analysis_timeout_seconds": 300,
    "llm_timeout_seconds": 60,
    
    # 资源限制
    "max_memory_per_analysis_mb": 512,
    "max_instance_kg_entities": 10000
}
```

## 🔄 迁移清单

### 迁移前检查

- [ ] 备份现有数据库
- [ ] 确认KAG服务正常运行
- [ ] 验证Schema正确提交
- [ ] 测试API接口连通性

### 迁移步骤

1. [ ] 部署KAG服务 (`docker-compose up -d`)
2. [ ] 运行数据库迁移脚本
3. [ ] 更新前端配置
4. [ ] 替换质控服务调用
5. [ ] 测试核心功能
6. [ ] 监控系统运行状态

### 迁移后验证

- [ ] 单个病历分析功能正常
- [ ] 批量处理功能正常
- [ ] 结果保存到数据库正常
- [ ] 前端显示格式正确
- [ ] 性能指标符合预期

## 🆘 故障排除

### 常见问题

1. **KAG服务启动失败**
   ```bash
   # 检查端口占用
   netstat -tulpn | grep 8000
   
   # 检查依赖安装
   pip list | grep kag
   ```

2. **OpenSPG连接失败**
   ```bash
   # 检查OpenSPG服务
   curl http://localhost:8887/health
   
   # 重启OpenSPG
   docker-compose restart openspg
   ```

3. **Schema提交失败**
   ```bash
   # 验证Schema语法
   knext schema validate --schema_path ./kag_schemas/MedicalQC.schema
   
   # 重新提交
   knext schema commit --force
   ```

4. **前端API调用失败**
   ```bash
   # 检查CORS配置
   # 检查API网关日志
   docker-compose logs kag-api
   ```

## 📞 技术支持

- **KAG框架文档**: https://github.com/OpenSPG/KAG
- **OpenSPG文档**: https://openspg.github.io
- **项目Issues**: https://github.com/your-repo/medqc/issues

---

**🎉 恭喜！您已成功将质控系统完全迁移到KAG架构！**
