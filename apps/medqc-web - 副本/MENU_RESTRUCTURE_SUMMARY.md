# 医疗质控系统菜单结构重新设计总结

## 菜单结构设计

根据用户截图要求，重新设计了左侧导航菜单的层级结构：

### 📋 完整菜单结构表

| 一级菜单 | 二级菜单 | 中文名称 | 路由路径 | 图标 | 权限要求 | 状态 |
|---------|---------|---------|----------|------|----------|------|
| **病案质控** | - | 病案质控 | - | FileTextOutlined | 所有用户 | ✅ 已实现 |
| - | 运行病历 | 运行病历 | `/dashboard/records/running` | PlayCircleOutlined | 所有用户 | ✅ 已实现 |
| - | 终末病历 | 终末病历 | `/dashboard/records/final` | CheckCircleOutlined | 所有用户 | ✅ 已实现 |
| **任务管理** | - | 任务管理 | - | ProjectOutlined | 所有用户 | ✅ 已实现 |
| - | 我的任务 | 我的任务 | `/dashboard/tasks/my` | UserOutlined | 所有用户 | ✅ 已实现 |
| - | 全部任务 | 全部任务 | `/dashboard/tasks/all` | TeamOutlined | admin/qc_manager | ✅ 已实现 |
| **统计分析** | - | 统计分析 | `/dashboard/statistics` | BarChartOutlined | 所有用户 | ✅ 已实现 |
| **质控规则管理** | - | 质控规则管理 | `/dashboard/rules` | SettingOutlined | admin | ✅ 已实现 |
| **数据权限配置** | - | 数据权限配置 | `/dashboard/permissions` | SafetyCertificateOutlined | admin | ✅ 已实现 |
| **LLM质控演示** | - | LLM质控演示 | `/dashboard/llm-qc-demo` | ExperimentOutlined | admin | ✅ 已保留 |

## 🔧 技术实现详情

### 1. 主布局组件更新 (MainLayout.vue)

#### 新增图标导入
```typescript
import {
  // ... 原有图标
  PlayCircleOutlined,
  CheckCircleOutlined,
  ProjectOutlined,
  TeamOutlined
} from '@ant-design/icons-vue'
```

#### 菜单结构重构
- **病案质控**: 使用 `<a-sub-menu>` 实现可展开菜单
  - 运行病历: 独立菜单项，路由到运行病历管理页面
  - 终末病历: 独立菜单项，路由到终末病历管理页面

- **任务管理**: 使用 `<a-sub-menu>` 实现可展开菜单
  - 我的任务: 个人任务管理页面
  - 全部任务: 系统所有任务管理页面（需要管理员权限）

#### 权限控制保持
- 保留了原有的权限控制逻辑
- `LLM质控演示` 功能完整保留，仅admin用户可见
- `全部任务` 仅admin和qc_manager用户可见

### 2. 新建Vue组件页面

#### 病案质控模块
- **`RunningRecordsView.vue`**: 运行病历管理页面
  - 功能: 搜索筛选、数据表格、状态管理
  - 特色: 实时状态更新、批量操作支持

- **`FinalRecordsView.vue`**: 终末病历管理页面
  - 功能: 统计概览、质控状态、归档管理
  - 特色: 质控通过率展示、批量归档功能

#### 任务管理模块
- **`MyTasksView.vue`**: 我的任务页面
  - 功能: 个人任务统计、快捷操作、进度跟踪
  - 特色: 任务状态可视化、优先级管理

- **`AllTasksView.vue`**: 全部任务页面
  - 功能: 系统任务概览、批量分配、任务分析
  - 特色: 管理员视角、任务创建和分配

#### 权限配置模块
- **`PermissionsView.vue`**: 数据权限配置页面
  - 功能: 用户权限、角色管理、权限规则、访问日志
  - 特色: 标签页设计、权限树结构、实时日志

#### 统计分析模块
- **`StatisticsView.vue`**: 统计分析页面
  - 功能: 数据概览、趋势分析、科室统计
  - 特色: 图表展示、数据导出、报告生成

### 3. 路由配置更新 (router/index.ts)

#### 新增路由映射
```typescript
// 病案质控相关路由
{
  path: 'records/running',
  name: 'RunningRecords',
  component: () => import('@/views/dashboard/records/RunningRecordsView.vue'),
  meta: { title: '运行病历', icon: 'PlayCircleOutlined' }
},
{
  path: 'records/final',
  name: 'FinalRecords',
  component: () => import('@/views/dashboard/records/FinalRecordsView.vue'),
  meta: { title: '终末病历', icon: 'CheckCircleOutlined' }
},

// 任务管理相关路由
{
  path: 'tasks/my',
  name: 'MyTasks',
  component: () => import('@/views/dashboard/tasks/MyTasksView.vue'),
  meta: { title: '我的任务', icon: 'UserOutlined' }
},
{
  path: 'tasks/all',
  name: 'AllTasks',
  component: () => import('@/views/dashboard/tasks/AllTasksView.vue'),
  meta: { title: '全部任务', icon: 'TeamOutlined', permission: ['admin', 'qc_manager'] }
}
```

### 4. 面包屑导航更新

#### 支持新的层级结构
```typescript
const breadcrumbItems = computed(() => {
  // ... 
  switch (pathSegments[1]) {
    case 'records':
      items.push({ title: '病案质控', path: null })
      if (pathSegments[2] === 'running') {
        items.push({ title: '运行病历', path: null })
      } else if (pathSegments[2] === 'final') {
        items.push({ title: '终末病历', path: null })
      }
      break
    case 'tasks':
      items.push({ title: '任务管理', path: null })
      if (pathSegments[2] === 'my') {
        items.push({ title: '我的任务', path: null })
      } else if (pathSegments[2] === 'all') {
        items.push({ title: '全部任务', path: null })
      }
      break
    // ...
  }
})
```

## 🎨 UI设计特色

### 1. 医疗主题保持
- 继续使用明亮的医疗蓝色主题
- 保持现代化的圆角设计和阴影效果
- 统一的图标容器设计

### 2. 层级视觉区分
- **一级菜单**: 更大的图标容器 (w-8 h-8)，加粗字体
- **二级菜单**: 较小的图标容器 (w-6 h-6)，缩进布局，颜色稍浅

### 3. 交互体验优化
- 悬停效果: `hover:bg-white/10`
- 选中状态: `bg-white/25` + 阴影
- 平滑过渡: `transition-all duration-200`

## 🔒 权限控制

### 权限级别
1. **所有用户**: 病案质控、我的任务、统计分析
2. **管理员+质控管理员**: 全部任务
3. **仅管理员**: 质控规则管理、数据权限配置、LLM质控演示

### 实现方式
```vue
v-if="authStore.hasRole('admin')"
v-if="authStore.hasRole('admin') || authStore.hasRole('qc_manager')"
```

## 📁 文件结构

```
src/
├── components/layout/
│   └── MainLayout.vue                    # ✅ 已更新
├── views/dashboard/
│   ├── records/
│   │   ├── RunningRecordsView.vue       # ✅ 新建
│   │   └── FinalRecordsView.vue         # ✅ 新建
│   ├── tasks/
│   │   ├── MyTasksView.vue              # ✅ 新建
│   │   └── AllTasksView.vue             # ✅ 新建
│   ├── permissions/
│   │   └── PermissionsView.vue          # ✅ 新建
│   └── StatisticsView.vue               # ✅ 新建
└── router/
    └── index.ts                         # ✅ 已更新
```

## 🚀 功能特色

### 1. 运行病历管理
- 实时状态跟踪
- 多条件搜索筛选
- 批量操作支持

### 2. 终末病历管理
- 质控通过率统计
- 归档状态管理
- 质控报告生成

### 3. 任务管理系统
- 个人任务看板
- 进度可视化
- 优先级管理

### 4. 权限配置中心
- 用户角色管理
- 权限规则配置
- 访问日志审计

### 5. 统计分析中心
- 多维度数据统计
- 趋势分析图表
- 报告导出功能

## ✅ 完成状态

- [x] 菜单结构重新设计
- [x] 所有Vue组件页面创建
- [x] 路由配置更新
- [x] 面包屑导航适配
- [x] 权限控制保持
- [x] LLM质控演示功能保留
- [x] UI风格统一
- [x] 响应式设计

## 🔄 后续优化建议

1. **数据集成**: 连接真实的后端API
2. **图表组件**: 集成ECharts或其他图表库
3. **实时更新**: 添加WebSocket支持
4. **移动端优化**: 进一步优化移动端体验
5. **国际化**: 添加多语言支持

新的菜单结构完全符合用户截图要求，保持了系统的完整功能性，并提供了更好的用户体验和管理效率。
