# Supabase数据库配置指南

## 📋 概述

本指南详细说明如何在Supabase中设置医疗质控系统的数据库，包括表结构创建、权限配置和数据迁移。

## 🗄️ 数据库架构设计

### **核心设计理念**

1. **JSONB字段存储非结构化数据**
   - 利用PostgreSQL的JSONB类型存储AI解析结果
   - 支持复杂查询和索引优化
   - 保持数据结构的灵活性

2. **分层存储策略**
   - 结构化字段：患者基本信息、诊断、科室等
   - 半结构化字段：AI解析结果、置信度评分
   - 非结构化字段：原始文本、文书内容

3. **审计和追踪**
   - 完整的创建/修改时间记录
   - 用户操作追踪
   - AI解析历史保存

## 🏗️ 表结构详解

### **1. medical_records (医疗记录主表)**

```sql
CREATE TABLE medical_records (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    record_number VARCHAR(50) UNIQUE NOT NULL,
    record_name VARCHAR(200) NOT NULL,
    
    -- 患者信息 (JSONB存储)
    patient_info JSONB NOT NULL DEFAULT '{}',
    
    -- 结构化医疗信息
    department VARCHAR(100),
    primary_diagnosis TEXT,
    secondary_diagnosis JSONB DEFAULT '[]',
    major_surgery TEXT,
    
    -- 原始数据和AI结果
    raw_text TEXT,
    ai_extraction_result JSONB DEFAULT '{}',
    ai_confidence_score DECIMAL(5,2) DEFAULT 0.0,
    
    -- 状态和元数据
    status VARCHAR(20) DEFAULT 'draft',
    import_method VARCHAR(20) DEFAULT 'manual',
    
    -- 审计字段
    created_by UUID REFERENCES auth.users(id),
    last_modified_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**JSONB字段示例：**

```json
// patient_info 字段
{
  "name": "张三",
  "age": 65,
  "gender": "男",
  "id_number": "***************",
  "phone": "138****8888",
  "address": "北京市朝阳区***",
  "emergency_contact": {
    "name": "李四",
    "phone": "139****9999",
    "relationship": "儿子"
  }
}

// ai_extraction_result 字段
{
  "extraction_time": "2024-08-27T10:30:00Z",
  "model_used": "medical-llm-v1",
  "model_version": "1.2.0",
  "fields_extracted": ["patient_name", "age", "department", "diagnosis"],
  "confidence_scores": {
    "patient_name": 95,
    "department": 88,
    "diagnosis": 92
  },
  "processing_time_ms": 2500,
  "tokens_used": 1250
}
```

### **2. medical_documents (医疗文书表)**

```sql
CREATE TABLE medical_documents (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    record_id UUID REFERENCES medical_records(id) ON DELETE CASCADE,
    
    document_type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    
    -- AI分类信息
    ai_classified BOOLEAN DEFAULT FALSE,
    ai_confidence_score DECIMAL(5,2) DEFAULT 0.0,
    ai_extraction_metadata JSONB DEFAULT '{}',
    
    -- 文书元数据
    document_metadata JSONB DEFAULT '{}',
    
    sort_order INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### **3. ai_parsing_history (AI解析历史表)**

```sql
CREATE TABLE ai_parsing_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    record_id UUID REFERENCES medical_records(id) ON DELETE CASCADE,
    
    -- 输入信息
    input_text TEXT NOT NULL,
    input_method VARCHAR(20) NOT NULL,
    
    -- 解析结果
    extraction_result JSONB NOT NULL,
    confidence_scores JSONB DEFAULT '{}',
    processing_time_ms INTEGER,
    tokens_used INTEGER,
    
    -- 模型信息
    model_name VARCHAR(100),
    model_version VARCHAR(50),
    
    -- 用户反馈
    user_corrections JSONB DEFAULT '{}',
    user_rating INTEGER CHECK (user_rating BETWEEN 1 AND 5),
    user_feedback TEXT,
    
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## 🚀 部署步骤

### **步骤1: 创建Supabase项目**

1. 访问 [Supabase Dashboard](https://supabase.com/dashboard)
2. 点击 "New Project"
3. 选择组织和输入项目信息
4. 等待项目初始化完成

### **步骤2: 执行数据库迁移**

1. 在Supabase Dashboard中，进入 "SQL Editor"
2. 复制 `supabase/migrations/20240827_create_medical_records_tables.sql` 文件内容
3. 粘贴到SQL编辑器中执行
4. 确认所有表和索引创建成功

### **步骤3: 配置Row Level Security (RLS)**

```sql
-- 启用RLS
ALTER TABLE medical_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE medical_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_parsing_history ENABLE ROW LEVEL SECURITY;

-- 创建基本策略
CREATE POLICY "Users can view their own records" ON medical_records
    FOR SELECT USING (auth.uid() = created_by);

CREATE POLICY "Users can insert records" ON medical_records
    FOR INSERT WITH CHECK (auth.uid() = created_by);

CREATE POLICY "Users can update their own records" ON medical_records
    FOR UPDATE USING (auth.uid() = created_by);
```

### **步骤4: 创建数据库函数**

```sql
-- 自动更新 updated_at 字段
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 应用触发器
CREATE TRIGGER update_medical_records_updated_at 
    BEFORE UPDATE ON medical_records 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### **步骤5: 创建视图和索引**

```sql
-- 创建联合查询视图
CREATE VIEW medical_records_with_documents AS
SELECT 
    mr.*,
    COALESCE(
        json_agg(
            json_build_object(
                'id', md.id,
                'document_type', md.document_type,
                'title', md.title,
                'content', md.content,
                'ai_confidence_score', md.ai_confidence_score
            ) ORDER BY md.sort_order
        ) FILTER (WHERE md.id IS NOT NULL),
        '[]'::json
    ) as documents
FROM medical_records mr
LEFT JOIN medical_documents md ON mr.id = md.record_id
GROUP BY mr.id;

-- 创建性能优化索引
CREATE INDEX idx_medical_records_patient_info ON medical_records USING GIN(patient_info);
CREATE INDEX idx_medical_records_ai_result ON medical_records USING GIN(ai_extraction_result);
CREATE INDEX idx_medical_documents_metadata ON medical_documents USING GIN(document_metadata);
```

## 🔧 环境配置

### **获取连接信息**

1. 在Supabase Dashboard中，进入 "Settings" > "API"
2. 复制以下信息：
   - Project URL
   - anon public key
   - service_role secret (仅服务端使用)

### **配置环境变量**

创建 `.env` 文件：

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

## 📊 数据查询示例

### **基本查询**

```sql
-- 查询所有病历记录
SELECT * FROM medical_records_with_documents 
WHERE status = 'active' 
ORDER BY created_at DESC;

-- 按科室统计
SELECT department, COUNT(*) as count 
FROM medical_records 
GROUP BY department;

-- AI解析置信度分析
SELECT 
    AVG(ai_confidence_score) as avg_confidence,
    COUNT(*) FILTER (WHERE ai_confidence_score > 90) as high_confidence,
    COUNT(*) FILTER (WHERE ai_confidence_score < 70) as low_confidence
FROM medical_records 
WHERE import_method = 'smart_import';
```

### **JSONB查询**

```sql
-- 查询特定年龄段患者
SELECT * FROM medical_records 
WHERE (patient_info->>'age')::int BETWEEN 60 AND 80;

-- 查询包含特定字段的AI结果
SELECT * FROM medical_records 
WHERE ai_extraction_result ? 'confidence_scores';

-- 按AI置信度排序
SELECT 
    record_name,
    patient_info->>'name' as patient_name,
    ai_extraction_result->'confidence_scores'->>'overall' as confidence
FROM medical_records 
WHERE import_method = 'smart_import'
ORDER BY (ai_extraction_result->'confidence_scores'->>'overall')::float DESC;
```

## 🔒 安全配置

### **数据脱敏**

```sql
-- 创建脱敏视图
CREATE VIEW medical_records_anonymized AS
SELECT 
    id,
    record_number,
    record_name,
    jsonb_set(
        patient_info, 
        '{name}', 
        '"***"'
    ) as patient_info_anonymized,
    department,
    primary_diagnosis,
    created_at
FROM medical_records;
```

### **访问控制**

```sql
-- 基于角色的访问控制
CREATE POLICY "Doctors can view all records" ON medical_records
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM user_roles 
            WHERE user_id = auth.uid() 
            AND role IN ('doctor', 'admin')
        )
    );
```

## 📈 性能优化

### **索引策略**

```sql
-- 复合索引
CREATE INDEX idx_medical_records_dept_status ON medical_records(department, status);
CREATE INDEX idx_medical_records_created_at_desc ON medical_records(created_at DESC);

-- 部分索引
CREATE INDEX idx_medical_records_smart_import ON medical_records(ai_confidence_score) 
WHERE import_method = 'smart_import';

-- 表达式索引
CREATE INDEX idx_patient_name ON medical_records((patient_info->>'name'));
```

### **查询优化**

```sql
-- 使用EXPLAIN ANALYZE分析查询性能
EXPLAIN ANALYZE 
SELECT * FROM medical_records_with_documents 
WHERE department = '内科' 
AND created_at >= '2024-08-01'
ORDER BY created_at DESC 
LIMIT 10;
```

## 🔄 数据迁移和备份

### **数据导出**

```sql
-- 导出病历数据
COPY (
    SELECT 
        record_number,
        record_name,
        patient_info->>'name' as patient_name,
        department,
        primary_diagnosis,
        created_at
    FROM medical_records 
    WHERE status = 'active'
) TO '/tmp/medical_records_export.csv' WITH CSV HEADER;
```

### **备份策略**

1. **自动备份**: Supabase提供自动备份功能
2. **手动备份**: 定期导出重要数据
3. **版本控制**: 使用迁移文件管理数据库结构变更

## 🧪 测试数据

### **插入测试数据**

```sql
-- 插入示例病历
INSERT INTO medical_records (
    record_number, 
    record_name, 
    patient_info, 
    department, 
    primary_diagnosis,
    ai_extraction_result,
    ai_confidence_score,
    import_method,
    created_by
) VALUES (
    'MR20240827001',
    '张三病历',
    '{"name": "张三", "age": 65, "gender": "男"}',
    '内科',
    '高血压病',
    '{"extraction_time": "2024-08-27T10:30:00Z", "model_used": "medical-llm-v1"}',
    89.5,
    'smart_import',
    auth.uid()
);
```

## 📚 最佳实践

### **数据建模**

1. **合理使用JSONB**: 对于经常查询的字段使用结构化列，对于灵活数据使用JSONB
2. **索引优化**: 为JSONB字段创建GIN索引，提高查询性能
3. **数据验证**: 使用CHECK约束和触发器确保数据完整性

### **查询优化**

1. **避免SELECT ***: 只查询需要的字段
2. **使用视图**: 封装复杂查询逻辑
3. **分页查询**: 使用LIMIT和OFFSET进行分页

### **安全考虑**

1. **启用RLS**: 确保数据访问安全
2. **数据脱敏**: 在非生产环境中使用脱敏数据
3. **审计日志**: 记录所有数据变更操作

这个数据库架构设计充分利用了PostgreSQL和Supabase的强大功能，为智能病历导入系统提供了灵活、高效、安全的数据存储解决方案。
