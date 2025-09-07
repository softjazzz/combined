---
title: "Supabase数据库操作规范"
description: "Supabase数据库操作的标准化规范和最佳实践"
version: "2.0"
category: "database"
priority: "high"
type: "manual"
---
# Supabase数据库操作规范

## 🗄️ 数据库架构原则

### 1. 表命名规范
- 使用snake_case命名
- 表名使用复数形式
- 关联表使用描述性名称

```sql
-- ✅ 正确示例
medical_records
qc_rules
qc_results
user_roles
patient_diagnoses

-- ❌ 错误示例
MedicalRecord
qcRule
result
```

### 2. 字段命名规范
```sql
-- ✅ 标准字段命名
CREATE TABLE medical_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_name VARCHAR(100) NOT NULL,
  patient_id VARCHAR(50) NOT NULL,
  admission_date DATE NOT NULL,
  discharge_date DATE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 3. 索引策略
```sql
-- 为常用查询字段创建索引
CREATE INDEX idx_medical_records_patient_id ON medical_records(patient_id);
CREATE INDEX idx_medical_records_department ON medical_records(department_id);
CREATE INDEX idx_qc_results_record_id ON qc_results(medical_record_id);
```

## 🔐 行级安全(RLS)策略

### 1. 基础RLS策略
```sql
-- 启用RLS
ALTER TABLE medical_records ENABLE ROW LEVEL SECURITY;

-- 医生只能访问自己科室的病历
CREATE POLICY "department_access" ON medical_records
FOR ALL USING (
  department_id IN (
    SELECT department_id FROM user_departments 
    WHERE user_id = auth.uid()
  )
);

-- 管理员可以访问所有数据
CREATE POLICY "admin_access" ON medical_records
FOR ALL USING (
  EXISTS (
    SELECT 1 FROM user_roles 
    WHERE user_id = auth.uid() AND role = 'admin'
  )
);
```

### 2. 质控规则访问策略
```sql
CREATE POLICY "qc_rules_read" ON qc_rules
FOR SELECT USING (
  is_active = true OR 
  EXISTS (
    SELECT 1 FROM user_roles 
    WHERE user_id = auth.uid() AND role IN ('admin', 'qc_manager')
  )
);
```

## 📝 TypeScript数据库类型

### 1. 数据库类型定义
```typescript
// types/database.ts
export interface Database {
  public: {
    Tables: {
      medical_records: {
        Row: {
          id: string
          patient_name: string
          patient_id: string
          department_id: string
          admission_date: string
          discharge_date: string | null
          diagnosis_codes: string[]
          status: 'draft' | 'submitted' | 'reviewed' | 'approved'
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          patient_name: string
          patient_id: string
          department_id: string
          admission_date: string
          discharge_date?: string | null
          diagnosis_codes?: string[]
          status?: 'draft' | 'submitted' | 'reviewed' | 'approved'
        }
        Update: {
          patient_name?: string
          patient_id?: string
          department_id?: string
          admission_date?: string
          discharge_date?: string | null
          diagnosis_codes?: string[]
          status?: 'draft' | 'submitted' | 'reviewed' | 'approved'
          updated_at?: string
        }
      }
      qc_rules: {
        Row: QCRuleRow
        Insert: QCRuleInsert
        Update: QCRuleUpdate
      }
    }
  }
}
```

### 2. 服务层封装
```typescript
// services/supabase-service.ts
class SupabaseService {
  private supabase = createClient<Database>(
    process.env.VITE_SUPABASE_URL!,
    process.env.VITE_SUPABASE_ANON_KEY!
  )

  // 医疗记录操作
  async getMedicalRecords(filters?: MedicalRecordFilters) {
    let query = this.supabase
      .from('medical_records')
      .select('*')

    if (filters?.departmentId) {
      query = query.eq('department_id', filters.departmentId)
    }

    if (filters?.status) {
      query = query.eq('status', filters.status)
    }

    const { data, error } = await query

    if (error) {
      throw new Error(`获取医疗记录失败: ${error.message}`)
    }

    return data
  }

  async createMedicalRecord(record: Database['public']['Tables']['medical_records']['Insert']) {
    const { data, error } = await this.supabase
      .from('medical_records')
      .insert(record)
      .select()
      .single()

    if (error) {
      throw new Error(`创建医疗记录失败: ${error.message}`)
    }

    return data
  }

  // 质控规则操作
  async getQCRules(category?: string) {
    let query = this.supabase
      .from('qc_rules')
      .select('*')
      .eq('is_active', true)

    if (category) {
      query = query.eq('category', category)
    }

    const { data, error } = await query

    if (error) {
      throw new Error(`获取质控规则失败: ${error.message}`)
    }

    return data
  }
}

export const supabaseService = new SupabaseService()
```

## 🔄 数据迁移规范

### 1. 迁移文件命名
```
supabase/migrations/
├── 001_init_base_schema.sql
├── 002_add_qc_rules_table.sql
├── 003_create_rls_policies.sql
└── 004_add_quality_standards.sql
```

### 2. 迁移脚本结构
```sql
-- 002_add_qc_rules_table.sql
-- 创建质控规则表
CREATE TABLE IF NOT EXISTS qc_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_code VARCHAR(20) UNIQUE NOT NULL,
  name VARCHAR(200) NOT NULL,
  description TEXT,
  category VARCHAR(50) NOT NULL,
  rule_type VARCHAR(20) NOT NULL DEFAULT 'objective',
  severity VARCHAR(20) NOT NULL DEFAULT 'minor',
  max_score INTEGER NOT NULL DEFAULT 0,
  weight DECIMAL(3,1) NOT NULL DEFAULT 1.0,
  check_logic JSONB,
  prompt_template TEXT,
  is_active BOOLEAN NOT NULL DEFAULT true,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_qc_rules_category ON qc_rules(category);
CREATE INDEX idx_qc_rules_active ON qc_rules(is_active);

-- 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_qc_rules_updated_at 
  BEFORE UPDATE ON qc_rules 
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

## 🚨 数据库操作禁忌
1. **禁止在生产环境直接执行DELETE操作**
2. **禁止绕过RLS策略访问数据**
3. **禁止在代码中硬编码SQL语句**
4. **禁止忽略数据库错误**
5. **禁止在事务中执行长时间操作**

## 📋 性能优化检查清单
- [ ] 为常用查询字段创建了索引
- [ ] 使用了适当的数据类型
- [ ] 实现了数据分页
- [ ] 避免了N+1查询问题
- [ ] 使用了连接查询而非多次查询