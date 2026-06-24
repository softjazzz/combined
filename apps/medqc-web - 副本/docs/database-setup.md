# 数据库Schema升级和规则初始化指南

## 概述

本文档描述了病历质控系统的数据库Schema升级和质控规则初始化过程。

## 🚀 快速开始

### 1. 环境准备

确保你有以下环境变量配置：

```bash
# .env.local
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
# 可选：如果有service key
SUPABASE_SERVICE_KEY=your-service-key
```

### 2. 一键设置

```bash
# 完整设置（推荐）
npm run setup

# 或者分步执行
npm run db:migrate      # 数据库Schema升级
npm run db:init-rules   # 初始化质控规则
npm run db:seed         # 创建测试数据（可选）
```

## 📊 Schema升级详情

### 新增表结构

#### 1. qc_rules 表增强
```sql
-- 新增字段
ALTER TABLE qc_rules 
ADD COLUMN rule_code TEXT UNIQUE,           -- 规则编码（如: 1.1.1）
ADD COLUMN rule_type TEXT,                  -- 规则类型: objective|subjective|hybrid
ADD COLUMN severity TEXT,                   -- 严重程度: critical|major|minor
ADD COLUMN max_score INTEGER,               -- 最大扣分
ADD COLUMN check_logic JSONB,               -- 检查逻辑配置
ADD COLUMN version TEXT;                    -- 规则版本
```

#### 2. qc_rules_embeddings 表（RAG支持）
```sql
CREATE TABLE qc_rules_embeddings (
  id UUID PRIMARY KEY REFERENCES qc_rules(id),
  rule_text TEXT NOT NULL,
  embedding VECTOR(1536),                   -- 向量embedding
  category TEXT NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE
);
```

#### 3. qc_analysis_cache 表（性能优化）
```sql
CREATE TABLE qc_analysis_cache (
  content_hash TEXT PRIMARY KEY,
  segment_type TEXT NOT NULL,
  analysis_result JSONB NOT NULL,
  rule_version TEXT NOT NULL,
  confidence_score DECIMAL,
  expires_at TIMESTAMP WITH TIME ZONE
);
```

#### 4. qc_analysis_history 表（追溯性）
```sql
CREATE TABLE qc_analysis_history (
  id UUID PRIMARY KEY,
  record_id UUID REFERENCES medical_records(id),
  version_number INTEGER NOT NULL,
  analysis_result JSONB NOT NULL,
  changes_from_previous JSONB,
  analyst_type TEXT,                        -- ai|human|hybrid
  analysis_time_ms INTEGER
);
```

### 增强功能

1. **向量检索 (RAG)**
   - 规则相似度匹配函数
   - 智能规则检索

2. **性能优化**
   - 分析结果缓存
   - 优化索引策略

3. **历史追踪**
   - 分析版本管理
   - 变更历史记录

4. **统计分析**
   - 质控分析统计视图
   - 规则使用统计视图

## 📝 质控规则详情

### Phase 1: 核心规则 (20条)

初始化脚本包含20条核心质控规则，覆盖：

#### 严重问题（单项否决丙级）
- `1.1.1` - 篡改、伪造病历 ⭐
- `1.1.2` - 病历内容与客观事实不一致 ⭐
- `3.1.1` - 无入院记录 ⭐
- `4.1.1` - 无首次病程记录 ⭐
- `5.5.1` - 无手术同意书 ⭐
- `4.15.1` - 抢救病人无抢救记录 ⭐
- `7.4.1` - 输血病人无输血知情同意书 ⭐
- `5.10.1` - 无手术记录 ⭐
- `5.9.1` - 无麻醉记录 ⭐
- `6.1.1` - 无出院记录 ⭐
- `9.1.1` - 无长期医嘱单 ⭐
- `2.1.1` - 病案首页空白 ⭐

#### 重要问题（乙级问题）
- `3.1.2` - 入院记录超时（24小时）
- `4.1.2` - 首次病程记录超时（8小时）

#### 一般问题（扣分问题）
- `3.3.2` - 入院记录无医师签名（2分）
- `6.1.11` - 出院记录无医师签名（5分）
- `2.6.1` - 出院主要诊断错误（5分）
- `1.4.1` - 字迹潦草难认（2分）

### 规则类型分类

1. **客观规则 (objective)**
   - 基于结构检查
   - 时间要求验证
   - 必填字段检查
   - 100% 可程序化判断

2. **主观规则 (subjective)**
   - 基于LLM分析
   - 语义理解判断
   - 医疗逻辑推理
   - 需要人工智能支持

3. **混合规则 (hybrid)**
   - 结合客观和主观判断
   - 多层次验证
   - 提高准确性

## 🔧 技术实现

### 规则配置结构

```typescript
interface QCRule {
  rule_code: string                    // "1.1.1"
  name: string                         // "篡改、伪造病历"
  description: string                  // 详细描述
  category: 'completeness' | 'consistency' | 'rationality' | 'timeliness'
  rule_type: 'objective' | 'subjective' | 'hybrid'
  severity: 'critical' | 'major' | 'minor'
  max_score: number                    // 最大扣分
  check_logic: {
    type: string                       // 检查类型
    patterns?: string[]                // 搜索模式
    criteria?: string[]                // 判断标准
    required_sections?: string[]       // 必需章节
    time_requirements?: {              // 时间要求
      deadline_hours: number
      from_admission: boolean
    }
  }
  prompt_template?: string             // LLM提示词模板
}
```

### RAG检索实现

```sql
-- 向量相似度检索函数
CREATE FUNCTION match_qc_rules(
  query_embedding VECTOR(1536),
  match_threshold FLOAT DEFAULT 0.7,
  match_count INT DEFAULT 5
) RETURNS TABLE (
  rule_id UUID,
  rule_code TEXT,
  similarity FLOAT
)
```

## 📊 监控和统计

### 分析统计视图

```sql
-- 质控分析统计
CREATE VIEW qc_analysis_stats AS
SELECT 
  DATE(analysis_time) as analysis_date,
  grade,
  COUNT(*) as count,
  AVG(score) as avg_score,
  AVG(confidence_score) as avg_confidence
FROM qc_results
WHERE analysis_time >= NOW() - INTERVAL '30 days'
GROUP BY DATE(analysis_time), grade;

-- 规则使用统计
CREATE VIEW qc_rule_usage_stats AS
SELECT 
  rule_code,
  name as rule_name,
  category,
  severity,
  COUNT(violations) as violation_count,
  ROUND(violation_rate, 2) as violation_rate
FROM qc_rules
-- ... 复杂统计逻辑
```

## 🚀 后续扩展计划

### Phase 2: 规则扩展 (50-70条)
- 增加主观判断规则
- 完善诊断依据检查
- 病程记录质量评估

### Phase 3: 全量规则 (100+条)
- 覆盖所有质控标准
- 专科特殊规则
- 个性化规则配置

### Phase 4: 智能优化
- 自动规则学习
- 个性化权重调整
- 持续模型优化

## 🔍 故障排除

### 常见问题

1. **迁移失败**
   ```bash
   # 检查Supabase连接
   npm run type-check
   
   # 手动验证表结构
   # 登录Supabase Dashboard查看表结构
   ```

2. **规则初始化失败**
   ```bash
   # 检查权限配置
   # 确保RLS策略正确设置
   
   # 重新初始化
   npm run db:init-rules
   ```

3. **向量检索不工作**
   ```bash
   # 确保pgvector扩展已启用
   # 检查embedding表数据
   ```

### 性能监控

```sql
-- 查看缓存命中率
SELECT 
  COUNT(*) as total_cache_entries,
  AVG(access_count) as avg_access_count,
  MAX(access_count) as max_access_count
FROM qc_analysis_cache;

-- 查看分析性能
SELECT 
  AVG(analysis_time_ms) as avg_analysis_time,
  COUNT(*) as total_analyses
FROM qc_analysis_history
WHERE created_at >= NOW() - INTERVAL '24 hours';
```

## 📊 系统当前状态 (2024年12月更新)

### ✅ 数据库完整性
- **所有表结构**: 已完成创建和优化
- **质控规则**: 18条核心规则已初始化
- **向量索引**: RAG检索功能就绪
- **缓存机制**: 性能优化完成

### ✅ AI质控引擎
- **DeepSeek API**: 已集成并测试通过
- **四维度评分**: 完整性、一致性、合理性、及时性
- **实际测试结果**: 89分A级评定，耗时13.8秒
- **改进建议**: 8条专业建议自动生成

### ✅ 完整工作流程
- **病案创建**: API完成 (medical-records.ts)
- **AI分析**: 引擎完成 (qc-analysis-api.ts)
- **结果保存**: 数据库存储完成
- **前端展示**: Vue组件集成完成

### 🎯 下一步重点
1. 前端界面优化和用户体验改进
2. 批量处理功能开发
3. 消息推送系统集成
4. 高级统计分析模块

## 📚 相关文档

- [AI分析服务模块](./ai-analysis-service.md) 🆕
- [质控规则配置指南](./qc-rules-guide.md)
- [RAG检索优化](./rag-optimization.md)
- [性能调优指南](./performance-tuning.md)
- [API使用文档](./api-reference.md) 