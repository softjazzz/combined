# 👨‍💻 Agent A 前端开发任务指导文档

**角色**: 前端专家 (Frontend Developer)  
**技术栈**: Vue 3 + TypeScript + Vite + Ant Design Vue  
**开发周期**: 3 周  
**协作对象**: Agent B (后端专家)  

---

## 📋 **任务背景**

### 🎯 **项目概述**
医疗质控系统是一个基于 AI 的智能医疗质控平台，采用 Vue 3 + FastAPI + Supabase 架构。系统已完成基础架构搭建和集成验证，现在进入并行开发阶段。

### 🏗️ **当前状态**
- ✅ **项目架构**: 完整的前后端分离架构
- ✅ **数据库设计**: 完整的医疗质控数据模型
- ✅ **基础组件**: 部分 Vue 组件已实现
- ✅ **API 规范**: 后端接口规范已定义
- ⚠️ **待完善**: 用户界面需要重构和优化

### 🎯 **前端开发目标**
1. **用户体验优化**: 现代化、直观的用户界面
2. **功能完整性**: 覆盖所有核心业务功能
3. **响应式设计**: 支持桌面端和移动端
4. **性能优化**: 快速加载和流畅交互
5. **代码质量**: 可维护、可扩展的代码结构

---

## 🗓️ **Week 1 核心任务 (高优先级)**

### 🔐 **Task A1: 用户认证界面重构**
**优先级**: 🔥 高  
**预估工作量**: 3 天  
**依赖**: 无 (可立即开始)  

#### **任务描述**
重构用户登录、注册和个人资料管理界面，实现现代化的认证流程，支持多角色用户登录。

#### **具体工作内容**
1. **登录界面重构**
   - 设计现代化的登录表单
   - 实现表单验证和错误提示
   - 添加"记住我"和"忘记密码"功能
   - 支持多角色选择 (admin, doctor, qc_manager, viewer)

2. **注册界面开发**
   - 创建用户注册表单
   - 实现密码强度验证
   - 添加邮箱验证和手机号验证
   - 科室选择和角色申请

3. **个人资料管理**
   - 用户信息展示和编辑
   - 头像上传功能
   - 密码修改功能
   - 登录历史查看

#### **文件结构**
```
src/
├── views/auth/
│   ├── LoginView.vue          # 登录页面
│   ├── RegisterView.vue       # 注册页面
│   ├── ProfileView.vue        # 个人资料页面
│   └── ForgotPasswordView.vue # 忘记密码页面
├── components/auth/
│   ├── LoginForm.vue          # 登录表单组件
│   ├── RegisterForm.vue       # 注册表单组件
│   ├── ProfileForm.vue        # 资料编辑组件
│   ├── AvatarUpload.vue       # 头像上传组件
│   └── PasswordStrength.vue   # 密码强度组件
├── stores/
│   ├── auth.ts               # 认证状态管理
│   └── user.ts               # 用户信息状态管理
└── types/
    └── auth.ts               # 认证相关类型定义
```

#### **API 接口依赖**
```typescript
// 需要调用的后端接口 (Agent B 负责实现)
POST /api/auth/login          // 用户登录
POST /api/auth/register       // 用户注册
POST /api/auth/refresh        // 刷新令牌
POST /api/auth/logout         // 用户登出
GET  /api/auth/profile        // 获取用户资料
PUT  /api/auth/profile        // 更新用户资料
POST /api/auth/upload-avatar  // 上传头像
POST /api/auth/change-password // 修改密码
```

#### **技术实现要点**
```vue
<!-- 示例：LoginForm.vue -->
<template>
  <div class="login-form">
    <a-form
      :model="loginForm"
      :rules="loginRules"
      @finish="handleLogin"
      layout="vertical"
    >
      <a-form-item label="邮箱" name="email">
        <a-input
          v-model:value="loginForm.email"
          placeholder="请输入邮箱"
          size="large"
        />
      </a-form-item>
      
      <a-form-item label="密码" name="password">
        <a-input-password
          v-model:value="loginForm.password"
          placeholder="请输入密码"
          size="large"
        />
      </a-form-item>
      
      <a-form-item name="role">
        <a-select
          v-model:value="loginForm.role"
          placeholder="选择角色"
          size="large"
        >
          <a-select-option value="doctor">医生</a-select-option>
          <a-select-option value="qc_manager">质控管理员</a-select-option>
          <a-select-option value="admin">系统管理员</a-select-option>
          <a-select-option value="viewer">查看者</a-select-option>
        </a-select>
      </a-form-item>
      
      <a-form-item>
        <a-button
          type="primary"
          html-type="submit"
          size="large"
          block
          :loading="loading"
        >
          登录
        </a-button>
      </a-form-item>
    </a-form>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import type { LoginRequest } from '@/types/auth'

const authStore = useAuthStore()
const loading = ref(false)

const loginForm = reactive<LoginRequest>({
  email: '',
  password: '',
  role: undefined,
  remember_me: false
})

const loginRules = {
  email: [
    { required: true, message: '请输入邮箱' },
    { type: 'email', message: '邮箱格式不正确' }
  ],
  password: [
    { required: true, message: '请输入密码' },
    { min: 6, message: '密码至少6位' }
  ],
  role: [
    { required: true, message: '请选择角色' }
  ]
}

const handleLogin = async () => {
  loading.value = true
  try {
    await authStore.login(loginForm)
    // 登录成功后的处理
  } catch (error) {
    // 错误处理
  } finally {
    loading.value = false
  }
}
</script>
```

#### **验收标准**
- [ ] 支持 4 种用户角色登录
- [ ] 表单验证完整，错误提示友好
- [ ] 界面响应式设计，支持移动端
- [ ] 登录状态持久化，支持自动登录
- [ ] 密码强度验证，安全性良好
- [ ] 头像上传功能正常
- [ ] 所有表单操作流畅，无卡顿

---

### 📄 **Task A2: 医疗记录管理界面**
**优先级**: 🔥 高  
**预估工作量**: 4 天  
**依赖**: Agent B 的 Task B2 (医疗记录处理API)  

#### **任务描述**
开发完整的医疗记录管理界面，包括记录列表、详情查看、上传编辑、搜索筛选等功能。

#### **具体工作内容**
1. **记录列表页面**
   - 响应式数据表格展示
   - 高级搜索和筛选功能
   - 分页和排序功能
   - 批量操作 (导出、删除)

2. **记录详情页面**
   - 完整的记录信息展示
   - 附件文件预览和下载
   - 编辑和更新功能
   - 操作历史记录

3. **文件上传功能**
   - 拖拽上传界面
   - 多格式文件支持
   - 上传进度显示
   - 文件预处理和验证

4. **搜索筛选组件**
   - 关键词搜索
   - 高级筛选器
   - 搜索历史
   - 快速筛选标签

#### **文件结构**
```
src/
├── views/records/
│   ├── RecordsListView.vue    # 记录列表页面
│   ├── RecordDetailView.vue   # 记录详情页面
│   ├── RecordEditView.vue     # 记录编辑页面
│   └── RecordUploadView.vue   # 记录上传页面
├── components/records/
│   ├── RecordsTable.vue       # 记录表格组件
│   ├── RecordCard.vue         # 记录卡片组件
│   ├── RecordForm.vue         # 记录表单组件
│   ├── FileUpload.vue         # 文件上传组件
│   ├── FilePreview.vue        # 文件预览组件
│   ├── SearchFilter.vue       # 搜索筛选组件
│   └── BatchActions.vue       # 批量操作组件
├── stores/
│   └── records.ts             # 记录状态管理
└── types/
    └── records.ts             # 记录相关类型定义
```

#### **API 接口依赖**
```typescript
// 等待 Agent B 实现的接口
GET    /api/records            // 获取记录列表
POST   /api/records            // 创建记录
GET    /api/records/{id}       // 获取记录详情
PUT    /api/records/{id}       // 更新记录
DELETE /api/records/{id}       // 删除记录
POST   /api/records/upload     // 上传文件
GET    /api/records/search     // 搜索记录
POST   /api/records/batch      // 批量操作
```

#### **验收标准**
- [ ] 支持多格式文件上传 (PDF, DOC, TXT, 图片)
- [ ] 表格支持排序、筛选、分页
- [ ] 搜索响应时间 < 1 秒
- [ ] 批量操作流畅，支持进度显示
- [ ] 文件预览功能正常
- [ ] 移动端适配良好
- [ ] 数据加载优化，支持虚拟滚动

---

### 🔍 **Task A3: 质控分析结果展示**
**优先级**: 🔥 高  
**预估工作量**: 3 天  
**依赖**: Agent B 的 Task B3 (AI质控分析引擎)  

#### **任务描述**
开发质控分析结果的可视化展示界面，包括问题高亮、建议展示、规则配置等功能。

#### **具体工作内容**
1. **分析结果展示**
   - 质控评分和等级显示
   - 问题分类和优先级展示
   - 改进建议和解决方案
   - 分析进度和状态跟踪

2. **问题高亮功能**
   - 文档内容问题标注
   - 问题类型颜色区分
   - 点击查看详细说明
   - 问题修复状态跟踪

3. **规则配置界面**
   - 质控规则列表管理
   - 规则启用/禁用控制
   - 规则参数配置
   - 自定义规则创建

#### **文件结构**
```
src/
├── views/qc/
│   ├── QCResultsView.vue      # 质控结果页面
│   ├── QCAnalysisView.vue     # 分析详情页面
│   ├── QCRulesView.vue        # 规则配置页面
│   └── QCDashboardView.vue    # 质控仪表板
├── components/qc/
│   ├── QCScoreCard.vue        # 评分卡片组件
│   ├── QCIssuesList.vue       # 问题列表组件
│   ├── QCHighlighter.vue      # 问题高亮组件
│   ├── QCSuggestions.vue      # 建议展示组件
│   ├── QCRuleConfig.vue       # 规则配置组件
│   └── QCProgress.vue         # 分析进度组件
├── stores/
│   └── qc.ts                  # 质控状态管理
└── types/
    └── qc.ts                  # 质控相关类型定义
```

#### **API 接口依赖**
```typescript
// 等待 Agent B 实现的接口
POST /api/qc/analyze           // 执行质控分析
GET  /api/qc/results/{id}      // 获取质控结果
GET  /api/qc/tasks/{id}        // 获取分析任务状态
POST /api/qc/batch-analyze     // 批量分析
GET  /api/qc-rules             // 获取质控规则
PUT  /api/qc-rules/{id}        // 更新规则配置
```

#### **验收标准**
- [ ] 质控问题清晰展示，分类明确
- [ ] 支持问题类型筛选和排序
- [ ] 改进建议易于理解和操作
- [ ] 规则配置界面直观易用
- [ ] 分析进度实时更新
- [ ] 支持批量分析操作
- [ ] 历史分析结果对比

---

## 🗓️ **Week 2 高级功能 (中优先级)**

### 📊 **Task A4: 统计分析仪表板**
**预估工作量**: 3-4 天

#### **任务描述**
开发数据可视化仪表板，展示质控统计、趋势分析、科室对比等信息。

#### **主要功能**
- 多种图表类型 (柱状图、饼图、折线图)
- 数据筛选和时间范围选择
- 实时数据更新
- 数据导出功能

### 🔍 **Task A5: 智能搜索界面**
**预估工作量**: 2-3 天

#### **任务描述**
实现智能搜索功能，包括语义搜索、搜索建议、结果高亮等。

#### **主要功能**
- 智能搜索输入框
- 搜索建议和自动补全
- 搜索结果展示和高亮
- 搜索历史管理

---

## 🗓️ **Week 3 优化完善 (低优先级)**

### 📱 **Task A6: 响应式设计和移动端适配**
**预估工作量**: 2-3 天

#### **任务描述**
优化移动端体验，实现响应式设计，添加暗色主题等。

---

## 🛠️ **技术要求和规范**

### 📦 **技术栈**
- **框架**: Vue 3.5+ (Composition API)
- **语言**: TypeScript 5.7+
- **构建工具**: Vite 6.0+
- **UI 库**: Ant Design Vue 4.x
- **状态管理**: Pinia
- **路由**: Vue Router 4
- **HTTP 客户端**: Axios + Supabase Client
- **样式**: Tailwind CSS + SCSS

### 🎨 **设计规范**
- **色彩方案**: 医疗主题色彩 (蓝色、绿色为主)
- **字体**: 系统默认字体栈
- **间距**: 8px 基础间距系统
- **圆角**: 6px 统一圆角
- **阴影**: 统一阴影层级

### 📝 **代码规范**
```typescript
// 组件命名：PascalCase
// 文件命名：PascalCase.vue
// 变量命名：camelCase
// 常量命名：UPPER_SNAKE_CASE
// 类型命名：PascalCase

// 示例组件结构
<template>
  <!-- 模板内容 -->
</template>

<script setup lang="ts">
// 导入
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

// 类型定义
interface ComponentProps {
  title: string
  data: any[]
}

// Props 和 Emits
const props = defineProps<ComponentProps>()
const emit = defineEmits<{
  update: [value: any]
  change: [id: string]
}>()

// 响应式数据
const loading = ref(false)
const formData = reactive({
  name: '',
  email: ''
})

// 计算属性
const isValid = computed(() => {
  return formData.name && formData.email
})

// 方法
const handleSubmit = async () => {
  loading.value = true
  try {
    // 处理逻辑
  } finally {
    loading.value = false
  }
}

// 生命周期
onMounted(() => {
  // 初始化逻辑
})
</script>

<style scoped lang="scss">
// 样式定义
.component {
  @apply p-4 bg-white rounded-lg shadow;
  
  &__title {
    @apply text-lg font-semibold mb-4;
  }
}
</style>
```

---

## 🤝 **协作机制**

### 📋 **任务跟踪**
```bash
# 查看当前可开始的任务
python3 tools/coordination/task_tracker.py ready agent_a

# 开始任务
python3 tools/coordination/task_tracker.py status A1 in_progress "开始用户认证界面重构"

# 完成任务
python3 tools/coordination/task_tracker.py status A1 completed "认证界面重构完成"

# 遇到阻塞
python3 tools/coordination/task_tracker.py status A2 blocked "等待医疗记录API完成"

# 生成每日报告
python3 tools/coordination/task_tracker.py report
```

### 🔄 **与 Agent B 协作**
1. **API 接口协调**
   - 参考 `docs/api/API_INTERFACE_SPECIFICATION.md`
   - 如需接口修改，及时沟通
   - 使用 Mock 数据进行前端开发

2. **依赖管理**
   - Task A2 依赖 Task B2 (医疗记录API)
   - Task A3 依赖 Task B3 (质控分析API)
   - 可先使用 Mock 数据开发，后续对接真实API

3. **文件冲突避免**
   - 只修改 `src/` 目录下的前端文件
   - 不要修改 `production_system/` 后端文件
   - 共享文件 (如 `docs/`) 需要协调

### 🌿 **Git 工作流**
```bash
# 切换到前端开发分支
git checkout feature/agent-a-frontend-enhancement

# 每日提交代码
git add .
git commit -m "feat(auth): 完成登录界面重构"
git push origin feature/agent-a-frontend-enhancement

# 每日合并到 develop 分支
git checkout develop
git pull origin develop
git merge feature/agent-a-frontend-enhancement
git push origin develop
```

### 📞 **沟通机制**
- **每日同步**: 上午 9:00，15分钟进度汇报
- **问题反馈**: 遇到 API 接口问题及时反馈给 Agent B
- **设计确认**: 重要界面设计变更需要确认
- **集成测试**: 每周五下午进行前后端集成测试

---

## 📚 **重要参考文档**

1. **[并行开发计划](PARALLEL_DEVELOPMENT_PLAN.md)** - 整体开发计划
2. **[API 接口规范](docs/api/API_INTERFACE_SPECIFICATION.md)** - 后端接口文档
3. **[项目结构说明](PROJECT_STRUCTURE.md)** - 项目组织结构
4. **[集成验证报告](INTEGRATION_VERIFICATION_REPORT.md)** - 系统现状
5. **[Vue 3 官方文档](https://vuejs.org/)** - Vue 3 开发指南
6. **[Ant Design Vue](https://antdv.com/)** - UI 组件库文档

---

## 🎯 **成功标准**

### 📊 **质量指标**
- **代码质量**: TypeScript 类型覆盖率 > 90%
- **组件复用**: 公共组件复用率 > 80%
- **性能指标**: 页面加载时间 < 2 秒
- **用户体验**: 界面响应时间 < 100ms
- **兼容性**: 支持主流浏览器和移动端

### ✅ **验收清单**
- [ ] 所有 Week 1 任务按时完成
- [ ] 前后端 API 对接成功
- [ ] 界面设计符合医疗系统规范
- [ ] 响应式设计适配良好
- [ ] 代码通过 ESLint 和 TypeScript 检查
- [ ] 组件文档和注释完整
- [ ] 用户体验测试通过

---

**开始时间**: 立即开始  
**负责人**: Agent A (前端专家)  
**协作对象**: Agent B (后端专家)  
**预期完成**: 3 周内完成所有任务  

---

## 🚀 **快速启动指南**

### **第一步：环境准备**
```bash
# 1. 切换到项目目录
cd examples/002medqc/MedQC0817

# 2. 切换到前端开发分支
git checkout feature/agent-a-frontend-enhancement

# 3. 进入前端工作区
cd workspace/agent-a

# 4. 查看当前可开始的任务
python3 ../../tools/coordination/task_tracker.py ready agent_a
```

### **第二步：开始第一个任务**
```bash
# 1. 更新任务状态为进行中
python3 ../../tools/coordination/task_tracker.py status A1 in_progress "开始用户认证界面重构"

# 2. 创建认证相关文件
mkdir -p ../../src/views/auth
mkdir -p ../../src/components/auth
mkdir -p ../../src/stores
mkdir -p ../../src/types

# 3. 开始开发 LoginView.vue
# 参考上面的技术实现要点和代码示例
```

### **第三步：每日工作流程**
```bash
# 早上：查看进度和任务
python3 ../../tools/coordination/task_tracker.py report

# 开发过程中：提交代码
git add .
git commit -m "feat(auth): 实现登录表单组件"

# 晚上：更新任务状态
python3 ../../tools/coordination/task_tracker.py status A1 completed "登录界面开发完成"

# 推送代码
git push origin feature/agent-a-frontend-enhancement
```

### **第四步：API 对接准备**
```bash
# 1. 查看 API 接口规范
cat ../../docs/api/API_INTERFACE_SPECIFICATION.md

# 2. 创建 API 服务文件
mkdir -p ../../src/services
# 实现 authService.ts, recordsService.ts 等

# 3. 使用 Mock 数据进行开发
# 等待 Agent B 完成对应的后端 API
```

🚀 **现在可以开始前端开发工作了！**

记住：
- 📋 **每日更新任务状态**
- 🤝 **及时与 Agent B 沟通 API 需求**
- 📝 **遵循代码规范和设计标准**
- 🧪 **完成后进行自测和验收**
