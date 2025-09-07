# 医疗质控系统 - 快速参考手册

## 🚀 快速开始

### 启动服务
```bash
# 后端服务
cd backend
python main_api_with_supabase.py
# 服务地址: http://localhost:8002

# 前端服务
npm run dev
# 服务地址: http://localhost:5173
```

### 测试连接
```bash
curl http://localhost:8002/api/health
```

---

## 📊 核心数据表

### medical_records (医疗记录)
```sql
-- 主要字段
id (uuid)                    -- 主键
record_number (varchar)      -- 病历编号 ✅ 必填
patient_name (varchar)       -- 患者姓名 ✅ 必填
patient_age (int)           -- 患者年龄
patient_gender (varchar)    -- 患者性别
department_id (uuid)        -- 科室ID ✅ 必填
content (text)              -- 病历内容 ✅ 必填
status (varchar)            -- 状态: pending/completed/failed
created_by (uuid)           -- 创建者ID ✅ 必填
```

### departments (科室)
```sql
id (uuid)           -- 主键
name (varchar)      -- 科室名称 ✅ 必填
code (varchar)      -- 科室代码 ✅ 必填
category (varchar)  -- 类别，默认 'clinical'
```

### user_profiles (用户)
```sql
id (uuid)           -- 主键
username (varchar)  -- 用户名 ✅ 必填
full_name (varchar) -- 真实姓名 ✅ 必填
email (varchar)     -- 邮箱 ✅ 必填
role_type (varchar) -- 角色，默认 'doctor'
```

---

## 🔌 核心 API

### 1. 文件解析
```http
POST /api/parse-medical-file-public
Content-Type: multipart/form-data

# 参数
file: PDF/TXT/DOC 文件
options: "{}" (JSON字符串)
```

### 2. 智能导入 ⭐
```http
POST /api/smart-import
Content-Type: application/json

{
  "patient_name": "患者姓名",
  "content": "病历内容",
  "file_info": { "filename": "test.pdf", "size": 1024 },
  "parse_result": { "method": "PDF解析", "medical_info": {} }
}
```

### 3. 查询记录
```http
GET /api/medical-records?page=1&page_size=10&status=pending
```

### 4. 创建测试数据
```http
POST /api/debug/create-test-data
```

---

## 💡 前端集成示例

### Vue 3 智能导入
```vue
<script setup>
const uploadFile = async (file) => {
  // 1. 解析文件
  const formData = new FormData()
  formData.append('file', file)
  
  const parseRes = await fetch('http://localhost:8002/api/parse-medical-file-public', {
    method: 'POST',
    body: formData
  })
  const parseData = await parseRes.json()
  
  // 2. 智能导入
  const importRes = await fetch('http://localhost:8002/api/smart-import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      patient_name: '提取的患者姓名',
      content: parseData.data.content,
      file_info: parseData.data.file_info,
      parse_result: parseData.data
    })
  })
  
  const record = await importRes.json()
  console.log('创建成功:', record.id)
}
</script>
```

### Supabase 实时监听
```javascript
import { supabase } from '@/lib/supabase'

// 监听医疗记录变化
const subscription = supabase
  .channel('medical_records_changes')
  .on('postgres_changes', 
    { event: 'INSERT', schema: 'public', table: 'medical_records' },
    (payload) => {
      console.log('新记录:', payload.new)
      // 更新前端列表
    }
  )
  .subscribe()
```

---

## 🔧 测试数据

### 默认测试ID
```javascript
const TEST_DEPARTMENT_ID = "11111111-1111-1111-1111-111111111111"
const TEST_USER_ID = "22222222-2222-2222-2222-222222222222"
```

### 创建测试部门和用户
```sql
-- 部门
INSERT INTO departments (id, name, code, category) VALUES 
('11111111-1111-1111-1111-111111111111', '测试部门', 'TEST_DEPT', 'clinical');

-- 用户
INSERT INTO user_profiles (id, username, full_name, email, role_type, department_id) VALUES 
('22222222-2222-2222-2222-222222222222', 'testuser', '测试用户', 'test@example.com', 'doctor', '11111111-1111-1111-1111-111111111111');
```

---

## ⚡ 常用命令

### 数据库查询
```sql
-- 查看所有医疗记录
SELECT id, record_number, patient_name, status, created_at 
FROM medical_records 
ORDER BY created_at DESC LIMIT 10;

-- 查看科室列表
SELECT id, name, code FROM departments;

-- 查看用户列表
SELECT id, username, full_name, email FROM user_profiles;
```

### API 测试
```bash
# 健康检查
curl http://localhost:8002/api/health

# 创建测试数据
curl -X POST http://localhost:8002/api/debug/create-test-data

# 查询记录
curl http://localhost:8002/api/medical-records?page=1&page_size=5

# 智能导入测试
curl -X POST http://localhost:8002/api/smart-import \
  -H "Content-Type: application/json" \
  -d '{"patient_name":"测试患者","content":"测试内容"}'
```

---

## 🐛 故障排除

### 常见问题

**1. 外键约束错误**
```
ERROR: insert or update on table "medical_records" violates foreign key constraint
```
**解决**: 先创建测试数据 `POST /api/debug/create-test-data`

**2. 连接被拒绝**
```
curl: (7) Failed to connect to localhost port 8002
```
**解决**: 检查后端服务是否启动 `python main_api_with_supabase.py`

**3. Supabase 连接失败**
```
supabase_status: "error: ..."
```
**解决**: 检查 `.env` 文件中的 Supabase 配置

### 日志查看
```bash
# 后端日志
tail -f backend/logs/app.log

# 前端开发服务器日志
npm run dev
```

---

## 📋 检查清单

### 部署前检查
- [ ] Supabase 连接正常
- [ ] 测试数据已创建
- [ ] API 健康检查通过
- [ ] 文件解析功能正常
- [ ] 智能导入功能正常
- [ ] 前端页面加载正常

### 开发环境
- [ ] Python 3.8+
- [ ] Node.js 16+
- [ ] 依赖包已安装
- [ ] 环境变量已配置
- [ ] 端口 8002, 5173 可用

---

## 🔗 相关链接

- **API 文档**: http://localhost:8002/docs
- **Supabase 控制台**: https://supabase.com/dashboard
- **完整文档**: [DATABASE_AND_API_DOCUMENTATION.md](./DATABASE_AND_API_DOCUMENTATION.md)

---

**快速参考版本**: v1.0  
**更新时间**: 2025-08-29
