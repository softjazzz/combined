# 医疗文书分类体系

## 📋 概述

本文档详细说明了医疗质控系统中的文书分类体系，严格按照医疗行业标准和实际业务需求设计，支持智能识别和分类。

## 🏗️ 分类架构

### **一级分类（DocumentCategory）**

```typescript
enum DocumentCategory {
  ADMISSION_RECORD = 'admission_record', // 入院记录
  PROGRESS_NOTE = 'progress_note', // 病程记录
  OPERATION_RECORD = 'operation_record', // 手术记录
  DISCHARGE_RECORD = 'discharge_record', // 出院记录
  AUXILIARY_EXAMINATION = 'auxiliary_examination', // 辅助检查
  INFORMED_CONSENT = 'informed_consent', // 知情同意书
}
```

### **二级分类（DocumentType）**

## 📁 **1. 入院记录**

### **特点：一级分类，部分有细分**

| 文书类型         | 代码                       | 说明                   |
| ---------------- | -------------------------- | ---------------------- |
| 入院记录         | `admission_record`         | 标准入院记录           |
| 24小时内入院记录 | `admission_record_24h_in`  | 24小时内入院患者记录   |
| 24小时出入院记录 | `admission_record_24h_out` | 24小时内出入院患者记录 |

**识别关键词：**

- 入院记录、入院诊断
- 24小时、出入院
- 主诉、现病史、既往史

## 📝 **2. 病程记录**

### **特点：二级分类丰富，是最常见的文书类型**

| 文书类型             | 代码                       | 说明                   |
| -------------------- | -------------------------- | ---------------------- |
| 首次病程记录         | `first_progress_note`      | 患者入院后首次病程记录 |
| 日常病程记录         | `daily_progress_note`      | 住院期间日常病程变化   |
| 主治医生首次查房记录 | `attending_first_progress` | 主治医生首次查房       |
| 主治医生查房记录     | `attending_progress`       | 主治医生日常查房       |
| 会诊记录             | `consultation_record`      | 多科室会诊讨论         |
| 接班记录             | `handover_record`          | 医生交接班记录         |
| 阶段小结             | `stage_summary`            | 治疗阶段总结           |

**识别关键词：**

- 首次病程、首次查房
- 主治医生、查房记录
- 会诊、多科会诊
- 接班、交班
- 阶段小结、小结

## 🔪 **3. 手术记录**

### **特点：二级分类，包含术前和术中记录**

| 文书类型 | 代码                   | 说明               |
| -------- | ---------------------- | ------------------ |
| 手术记录 | `operation_record`     | 手术过程详细记录   |
| 术前小结 | `preoperative_summary` | 术前病情总结和计划 |

**识别关键词：**

- 手术记录、手术过程
- 术前小结、术前讨论
- 手术方式、麻醉方式

## 🏥 **4. 出院记录**

### **特点：二级分类，包含特殊情况记录**

| 文书类型         | 代码                    | 说明             |
| ---------------- | ----------------------- | ---------------- |
| 出院记录         | `discharge_record`      | 标准出院记录     |
| 死亡记录         | `death_record`          | 患者死亡记录     |
| 死亡病例讨论记录 | `death_case_discussion` | 死亡病例讨论分析 |

**识别关键词：**

- 出院记录、出院诊断
- 死亡记录、死亡证明
- 死亡病例讨论、死亡讨论

## 🔬 **5. 辅助检查**

### **特点：二级分类，涵盖各类检查报告**

| 文书类型       | 代码                | 说明                   |
| -------------- | ------------------- | ---------------------- |
| 影像检查报告   | `imaging_report`    | X光、CT、MRI等影像报告 |
| 实验室检查报告 | `lab_report`        | 血液、尿液等化验报告   |
| 其他检查报告   | `other_examination` | 其他各种检查报告       |

**识别关键词：**

- 影像、CT、MRI、X光
- 化验、血常规、尿常规、实验室
- 检查报告、检验报告

## 📋 **6. 知情同意书**

### **特点：二级分类，法律文件性质**

| 文书类型           | 代码                        | 说明             |
| ------------------ | --------------------------- | ---------------- |
| 手术知情同意书     | `surgery_consent`           | 手术前知情同意   |
| 麻醉知情同意书     | `anesthesia_consent`        | 麻醉前知情同意   |
| 输血知情同意书     | `blood_transfusion_consent` | 输血前知情同意   |
| 特殊治疗知情同意书 | `special_treatment_consent` | 特殊治疗知情同意 |
| 病危(重)通知书     | `critical_illness_notice`   | 病危病重通知     |

**识别关键词：**

- 知情同意、同意书
- 手术同意、麻醉同意、输血同意
- 特殊治疗、病危、病重、通知书

## 🤖 **AI智能识别规则**

### **识别优先级**

1. **标题匹配**：优先根据文书标题进行识别
2. **关键词匹配**：分析文本内容中的关键词
3. **上下文分析**：结合文本结构和医疗术语
4. **默认分类**：无法确定时默认为"日常病程记录"

### **识别算法**

```typescript
function inferDocumentType(content: string, title?: string): DocumentType {
  const text = (title + ' ' + content).toLowerCase()

  // 按优先级进行匹配
  if (text.includes('入院记录')) {
    if (text.includes('24小时') && text.includes('出院')) {
      return DocumentType.ADMISSION_RECORD_24H_OUT
    } else if (text.includes('24小时')) {
      return DocumentType.ADMISSION_RECORD_24H_IN
    }
    return DocumentType.ADMISSION_RECORD
  }

  // ... 其他识别逻辑

  return DocumentType.DAILY_PROGRESS_NOTE // 默认
}
```

## 🎨 **UI显示规范**

### **颜色标识**

| 分类       | 颜色 | 色值      | 用途     |
| ---------- | ---- | --------- | -------- |
| 入院记录   | 绿色 | `#52c41a` | 表示开始 |
| 病程记录   | 蓝色 | `#1890ff` | 表示过程 |
| 手术记录   | 橙色 | `#fa8c16` | 表示重要 |
| 出院记录   | 紫色 | `#722ed1` | 表示结束 |
| 辅助检查   | 青色 | `#13c2c2` | 表示检查 |
| 知情同意书 | 粉色 | `#eb2f96` | 表示法律 |

### **图标标识**

```typescript
const DOCUMENT_TYPE_ICONS = {
  admission_record: 'LoginOutlined',
  progress_note: 'FileTextOutlined',
  operation_record: 'ScissorOutlined',
  discharge_record: 'LogoutOutlined',
  auxiliary_examination: 'ExperimentOutlined',
  informed_consent: 'FileProtectOutlined',
}
```

## 📊 **统计分析**

### **文书分布统计**

```sql
-- 按分类统计文书数量
SELECT
    CASE
        WHEN document_type IN ('admission_record', 'admission_record_24h_in', 'admission_record_24h_out')
        THEN '入院记录'
        WHEN document_type IN ('first_progress_note', 'daily_progress_note', 'attending_first_progress', 'attending_progress', 'consultation_record', 'handover_record', 'stage_summary')
        THEN '病程记录'
        WHEN document_type IN ('operation_record', 'preoperative_summary')
        THEN '手术记录'
        WHEN document_type IN ('discharge_record', 'death_record', 'death_case_discussion')
        THEN '出院记录'
        WHEN document_type IN ('imaging_report', 'lab_report', 'other_examination')
        THEN '辅助检查'
        WHEN document_type IN ('surgery_consent', 'anesthesia_consent', 'blood_transfusion_consent', 'special_treatment_consent', 'critical_illness_notice')
        THEN '知情同意书'
    END as category,
    COUNT(*) as count
FROM medical_documents
GROUP BY category
ORDER BY count DESC;
```

### **AI识别准确率分析**

```sql
-- AI分类准确率统计
SELECT
    document_type,
    AVG(ai_confidence_score) as avg_confidence,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE ai_confidence_score > 90) as high_confidence_count
FROM medical_documents
WHERE ai_classified = true
GROUP BY document_type
ORDER BY avg_confidence DESC;
```

## 🔧 **配置和扩展**

### **添加新文书类型**

1. **更新枚举定义**

```typescript
// 在 DocumentType 中添加新类型
NEW_DOCUMENT_TYPE = 'new_document_type'
```

2. **更新映射关系**

```typescript
// 在各个映射对象中添加对应关系
DOCUMENT_TYPE_LABELS[DocumentType.NEW_DOCUMENT_TYPE] = '新文书类型'
```

3. **更新数据库约束**

```sql
-- 在数据库CHECK约束中添加新类型
ALTER TABLE medical_documents
DROP CONSTRAINT medical_documents_document_type_check;

ALTER TABLE medical_documents
ADD CONSTRAINT medical_documents_document_type_check
CHECK (document_type IN ('...', 'new_document_type'));
```

4. **更新识别规则**

```typescript
// 在 inferDocumentType 函数中添加识别逻辑
if (text.includes('新文书关键词')) {
  return DocumentType.NEW_DOCUMENT_TYPE
}
```

### **自定义识别规则**

```typescript
// 支持用户自定义识别规则
interface CustomRecognitionRule {
  keywords: string[]
  documentType: DocumentType
  priority: number
}

const customRules: CustomRecognitionRule[] = [
  {
    keywords: ['特殊关键词1', '特殊关键词2'],
    documentType: DocumentType.CUSTOM_TYPE,
    priority: 10,
  },
]
```

## 📈 **性能优化**

### **索引策略**

```sql
-- 为文书类型创建索引
CREATE INDEX idx_medical_documents_type ON medical_documents(document_type);

-- 为AI分类创建复合索引
CREATE INDEX idx_medical_documents_ai_classified ON medical_documents(ai_classified, ai_confidence_score);
```

### **缓存策略**

```typescript
// 缓存文书类型选项
const documentTypeOptionsCache = new Map()

export function getCachedDocumentTypeOptions() {
  if (!documentTypeOptionsCache.has('options')) {
    documentTypeOptionsCache.set('options', getGroupedDocumentTypeOptions())
  }
  return documentTypeOptionsCache.get('options')
}
```

## 🧪 **测试用例**

### **识别准确性测试**

```typescript
describe('文书类型识别', () => {
  test('应该正确识别入院记录', () => {
    const content = '患者张三，男，65岁，因头晕入院...'
    const result = inferDocumentType(content, '入院记录')
    expect(result).toBe(DocumentType.ADMISSION_RECORD)
  })

  test('应该正确识别首次病程记录', () => {
    const content = '患者入院后首次病程记录...'
    const result = inferDocumentType(content, '首次病程记录')
    expect(result).toBe(DocumentType.FIRST_PROGRESS_NOTE)
  })
})
```

## 📚 **最佳实践**

### **文书命名规范**

1. **标题规范**：使用标准的医疗文书名称
2. **内容结构**：保持文书内容的标准格式
3. **关键词使用**：在文书中使用标准的医疗术语

### **AI训练数据**

1. **数据质量**：确保训练数据的准确性和完整性
2. **样本平衡**：各类文书的样本数量要相对平衡
3. **持续优化**：根据用户反馈持续改进识别规则

这个文书分类体系严格按照医疗行业标准设计，支持智能识别和扩展，为医疗质控系统提供了完整的文书管理解决方案。
