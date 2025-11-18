# 科室级质控规则功能快速启动指南

## 📋 概述

本指南帮助您快速启动和测试科室级质控规则配置功能。

---

## 🚀 快速启动步骤

### 步骤 1: 执行数据库迁移

```bash
cd /home/ubuntu/coding/health-qc-monorepo/infra/supabase/medqc/migrations

# 执行迁移脚本
psql -h <your-supabase-host> \
     -U postgres \
     -d postgres \
     -f 009_department_qc_rules.sql

# 验证迁移
psql -h <your-supabase-host> \
     -U postgres \
     -d postgres \
     -f verify_009.sql
```

或者使用自动化测试脚本：

```bash
chmod +x test_009_migration.sh
./test_009_migration.sh
```

### 步骤 2: 启动后端 API 服务

```bash
cd /home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/backend

# 激活虚拟环境
source venv/bin/activate

# 启动 FastAPI 服务器
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**验证后端启动成功**:
- 访问 http://localhost:8001/docs
- 应该能看到新增的 8 个科室规则 API 接口

### 步骤 3: 启动前端开发服务器

```bash
cd /home/ubuntu/coding/health-qc-monorepo/apps/medqc-web

# 安装依赖（如果还没安装）
npm install

# 启动开发服务器
npm run dev
```

**验证前端启动成功**:
- 访问 http://localhost:5173
- 应该能看到登录页面

### 步骤 4: 登录系统

使用具有 ADMIN 或 QC_MANAGER 角色的账号登录：

```
用户名: admin@example.com
密码: admin123
```

或

```
用户名: qc_manager@example.com
密码: qcmanager123
```

### 步骤 5: 访问科室规则管理页面

登录后，导航到：

```
仪表板 → 科室规则管理
```

或直接访问：

```
http://localhost:5173/dashboard/department-rules
```

---

## 🧪 功能测试清单

### 1. 查看规则列表 ✅

- [ ] 页面正常加载
- [ ] 显示规则列表（如果有数据）
- [ ] 分页功能正常

### 2. 筛选功能 ✅

- [ ] 科室筛选下拉框正常工作
- [ ] 状态筛选（草稿/已发布/已归档）
- [ ] 覆盖行为筛选（覆盖配置/禁用规则）
- [ ] 关键词搜索

### 3. 创建科室规则 ✅

#### 模式 1: 基于全局规则创建

1. 点击 **[新增科室规则]** 按钮
2. 选择 **"基于全局规则创建"**
3. 从下拉框选择一个全局规则
4. 验证规则信息自动填充
5. 选择科室
6. 修改需要覆盖的字段（如优先级、严重程度）
7. 点击 **[确定]**
8. 验证规则创建成功

#### 模式 2: 全新创建

1. 点击 **[新增科室规则]** 按钮
2. 选择 **"全新创建"**
3. 填写所有必填字段：
   - 科室
   - 规则编号（如 `DEPT_001`）
   - 规则名称
   - 规则分类
   - 严重程度
4. 点击 **[确定]**
5. 验证规则创建成功

### 4. 编辑规则 ✅

1. 在规则列表中点击 **[编辑]** 按钮
2. 修改规则信息
3. 点击 **[确定]**
4. 验证规则更新成功

### 5. 发布规则 ✅

1. 找到一条状态为 **"草稿"** 的规则
2. 点击 **[发布]** 按钮
3. 验证规则状态变为 **"已发布"**

### 6. 查看变更历史 ✅

1. 点击任意规则的 **[历史]** 按钮
2. 验证显示变更历史时间线
3. 检查显示的信息：
   - 操作类型
   - 操作人
   - 操作时间
   - 操作原因

### 7. 删除规则 ✅

1. 点击 **[删除]** 按钮
2. 确认删除对话框
3. 点击 **[确定]**
4. 验证规则删除成功

---

## 🔍 API 测试

### 使用 Swagger UI 测试

访问 http://localhost:8001/docs，测试以下接口：

#### 1. 创建科室规则

```http
POST /api/v1/qc/rules/department
Authorization: Bearer <your-token>

{
  "department_id": "uuid",
  "rule_code": "DEPT_001",
  "name": "外科基本信息完整性",
  "description": "外科科室的基本信息完整性检查",
  "category": "completeness",
  "severity": "critical",
  "override_action": "override",
  "priority": 10,
  "status": "draft"
}
```

#### 2. 获取科室规则列表

```http
GET /api/v1/qc/rules/department?department_id=<uuid>&page=1&limit=20
Authorization: Bearer <your-token>
```

#### 3. 发布规则

```http
PATCH /api/v1/qc/rules/department/<rule-id>/publish
Authorization: Bearer <your-token>

{
  "approved_by": "current_user_id",
  "reason": "规则审核通过"
}
```

#### 4. 查看变更历史

```http
GET /api/v1/qc/rules/department/<rule-id>/history?page=1&limit=10
Authorization: Bearer <your-token>
```

#### 5. 获取适用规则

```http
GET /api/v1/qc/rules/department/applicable?department_id=<uuid>&document_type=入院记录
Authorization: Bearer <your-token>
```

---

## 🐛 常见问题排查

### 问题 1: 前端无法连接后端

**症状**: 前端显示网络错误

**解决方案**:
1. 检查后端是否正常运行：`curl http://localhost:8001/api/health`
2. 检查 Vite 代理配置：`apps/medqc-web/vite.config.ts`
3. 检查浏览器控制台的网络请求

### 问题 2: 401 未授权错误

**症状**: API 请求返回 401

**解决方案**:
1. 确认已登录系统
2. 检查 localStorage 中的 token：
   ```javascript
   localStorage.getItem('medqc_access_token')
   ```
3. 重新登录获取新 token

### 问题 3: 403 权限不足错误

**症状**: API 请求返回 403

**解决方案**:
1. 确认当前用户角色为 ADMIN 或 QC_MANAGER
2. 检查用户权限配置

### 问题 4: 科室列表为空

**症状**: 科室下拉框没有选项

**解决方案**:
1. 当前使用模拟数据，检查代码：
   ```typescript
   // apps/medqc-web/src/views/rules/DepartmentRulesView.vue
   const loadDepartments = async () => {
     departments.value = [
       { id: '1', name: '心内科' },
       { id: '2', name: '外科' },
       // ...
     ]
   }
   ```
2. 或集成真实的科室 API

### 问题 5: 数据库迁移失败

**症状**: 执行迁移脚本报错

**解决方案**:
1. 检查数据库连接
2. 查看错误日志
3. 使用回滚脚本恢复：
   ```bash
   psql -f 009_department_qc_rules_rollback.sql
   ```

---

## 📊 测试数据准备

### 创建测试科室

```sql
INSERT INTO departments (id, name, code, description)
VALUES 
  (gen_random_uuid(), '心内科', 'CARDIO', '心血管内科'),
  (gen_random_uuid(), '外科', 'SURGERY', '普通外科'),
  (gen_random_uuid(), '儿科', 'PEDIATRICS', '儿科'),
  (gen_random_uuid(), '妇产科', 'OBGYN', '妇产科');
```

### 创建测试全局规则

```sql
INSERT INTO qc_rules (
  id, rule_code, name, description, category, severity, 
  scope, is_active, created_at, updated_at
)
VALUES (
  gen_random_uuid(),
  'COMP_001',
  '基本信息完整性',
  '检查病历基本信息是否完整',
  'completeness',
  'critical',
  'global',
  true,
  NOW(),
  NOW()
);
```

---

## 📝 下一步

完成功能测试后，可以进行：

1. **集成测试** - 测试规则匹配逻辑
2. **性能测试** - 测试大量规则的加载和匹配性能
3. **用户验收测试** - 邀请实际用户测试
4. **部署到测试环境** - 部署到测试服务器

---

## 📚 相关文档

- [第三阶段完成报告](./PHASE_3_FRONTEND_UI_COMPLETION_REPORT.md)
- [PRD 文档](./PRD_DEPARTMENT_QC_RULES.md)
- [数据库迁移文档](../infra/supabase/medqc/migrations/README_009.md)
- [后端 API 文档](http://localhost:8001/docs)

---

**最后更新**: 2025-01-15  
**版本**: v1.0

