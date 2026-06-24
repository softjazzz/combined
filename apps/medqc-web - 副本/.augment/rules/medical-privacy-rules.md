---
title: "医疗数据隐私保护规则"
description: "医疗数据处理的隐私保护和合规要求"
version: "2.0"
category: "privacy"
priority: "critical"
compliance: "HIPAA, 个人信息保护法"
type: "manual"
---
# 医疗数据隐私保护规则

## 🔒 数据敏感性分级

### 1. 高敏感数据 (严格保护)
- **患者身份信息**: 姓名、身份证号、联系方式
- **医疗记录**: 诊断信息、治疗记录、检查结果
- **财务信息**: 费用明细、支付信息

### 2. 中敏感数据 (适度保护)
- **统计数据**: 去标识化的汇总信息
- **系统日志**: 不包含患者信息的操作日志

### 3. 低敏感数据 (基础保护)
- **配置信息**: 系统配置、规则配置
- **元数据**: 数据字典、代码表

## 🛡️ 数据处理规则

### 1. 代码中的隐私保护
```typescript
// ✅ 正确示例 - 包含隐私保护注释
interface PatientInfo {
  id: string
  name: string        // 敏感信息：患者姓名，需要访问权限控制
  idNumber: string    // 高敏感：身份证号，仅授权人员可访问
  age: number         // 低敏感：年龄信息
  diagnosis: string   // 敏感信息：诊断信息，需要医疗权限
}

// ❌ 错误示例 - 缺少隐私保护说明
interface Patient {
  name: string
  idNumber: string    // 未标注敏感性
}
```

### 2. 数据脱敏要求
- **开发环境**: 必须使用虚构数据，禁止使用真实患者信息
- **测试数据**: 使用标准化的测试数据集
- **演示数据**: 使用明显的虚构信息

```typescript
// ✅ 测试数据示例
const mockPatientData = {
  name: "张三(测试)",
  idNumber: "110000199001010001", // 明显的测试身份证号
  phone: "13800138000"
}
```

### 3. 数据访问控制
- 实现基于角色的访问控制(RBAC)
- 使用Supabase的行级安全(RLS)策略
- 记录所有敏感数据访问日志

```sql
-- RLS策略示例
CREATE POLICY "医生只能访问自己科室的病历" ON medical_records
FOR SELECT USING (
  department_id IN (
    SELECT department_id FROM user_departments 
    WHERE user_id = auth.uid()
  )
);
```

### 4. 数据传输安全
- 所有API调用必须使用HTTPS
- 敏感数据传输时进行加密
- 实现请求签名验证

### 5. 日志记录规范
```typescript
// ✅ 正确的日志记录
logger.info('用户访问病历列表', {
  userId: user.id,
  action: 'view_medical_records',
  timestamp: new Date(),
  // 不记录敏感的患者信息
})

// ❌ 错误的日志记录
logger.info('查看患者张三的病历') // 包含敏感信息
```

## 🚨 违规行为禁止清单
1. **禁止在代码注释中包含真实患者信息**
2. **禁止在控制台输出敏感数据**
3. **禁止将敏感数据存储在本地存储中**
4. **禁止在错误信息中暴露敏感数据**
5. **禁止在Git提交中包含真实医疗数据**

## 📋 合规检查清单
- [ ] 所有患者相关字段都有隐私保护注释
- [ ] 测试数据使用虚构信息
- [ ] 实现了适当的访问控制
- [ ] 敏感操作有审计日志
- [ ] 错误处理不暴露敏感信息