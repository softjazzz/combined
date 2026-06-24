# 人工审核模块项目结构

## 📁 完整项目结构

```
/home/ubuntu/KAG/kag/examples/002medqc/MedQC0817/
├── 📄 AUDIT_MODULE_README.md              # 审核模块实现文档
├── 📄 AUDIT_MODULE_STRUCTURE.md           # 项目结构说明（本文件）
│
├── 📁 database/                           # 数据库相关
│   └── migrations/
│       └── 📄 20241224_create_audit_tables.sql  # 审核模块数据表结构
│
├── 📁 src/                               # 源代码目录
│   ├── 📁 types/                         # 类型定义
│   │   └── 📄 audit-module.ts            # 审核模块类型定义
│   │
│   ├── 📁 services/                      # 服务层
│   │   ├── 📄 audit-task-service.ts      # 审核任务管理服务
│   │   ├── 📄 audit-result-service.ts    # 审核结果管理服务
│   │   └── 📄 notification-service.ts    # 消息通知服务
│   │
│   ├── 📁 components/                    # Vue组件
│   │   ├── 📁 audit/                     # 审核相关组件
│   │   │   ├── 📄 MultiLevelAuditTabs.vue    # 多级审核标签页
│   │   │   └── 📄 AuditResultPanel.vue       # 审核结果面板
│   │   └── 📁 notification/              # 通知相关组件
│   │       └── 📄 NotificationCenter.vue     # 消息通知中心
│   │
│   ├── 📁 views/                         # 页面组件
│   │   └── 📄 AuditModuleDemo.vue        # 审核模块演示页面
│   │
│   └── 📁 utils/                         # 工具函数
│       └── 📄 date-utils.ts              # 日期工具函数
│
├── 📁 tests/                             # 测试文件
│   └── 📄 audit-module.test.ts           # 审核模块测试
│
└── 📁 scripts/                           # 脚本文件
    └── 📄 start-audit-demo.sh            # 演示启动脚本
```

## 🔧 核心文件说明

### 数据库层
- **`20241224_create_audit_tables.sql`**: 包含8个核心表的完整DDL
  - `qc_audit_tasks` - 审核任务表
  - `qc_audit_task_items` - 审核任务明细表
  - `qc_audit_results` - 多级审核结果表
  - `qc_defects` - 质控缺陷表
  - `qc_notifications` - 消息通知表
  - `message_distribution_logs` - 消息分发日志表
  - `user_notification_preferences` - 用户通知偏好表
  - `defect_status_logs` - 缺陷状态变更日志表

### 类型定义层
- **`audit-module.ts`**: 完整的TypeScript类型定义
  - 审核任务相关接口 (QCAuditTask, QCAuditTaskItem等)
  - 审核结果相关接口 (QCAuditResult, QCDefect等)
  - 消息通知相关接口 (QCNotification, MessageAction等)
  - 枚举类型定义 (AuditLevel, MessageType等)

### 服务层
- **`audit-task-service.ts`**: 审核任务管理核心服务
  - 智能抽样算法实现
  - 任务创建和分配
  - 负载均衡机制
  
- **`audit-result-service.ts`**: 审核结果管理服务
  - AI辅助缺陷识别
  - 多级审核结果处理
  - 权限控制机制
  - 批量审核功能
  
- **`notification-service.ts`**: 消息通知服务
  - 智能消息生成
  - Supabase实时通信
  - 离线消息处理
  - 多通道分发

### 组件层
- **`MultiLevelAuditTabs.vue`**: 多级审核主界面
  - 三级审核标签页
  - 审核历史时间线
  - 权限控制展示
  
- **`AuditResultPanel.vue`**: 审核结果操作面板
  - 评分滑块和表单
  - AI辅助缺陷识别
  - 统计信息展示
  
- **`NotificationCenter.vue`**: 消息通知中心
  - 消息列表展示
  - 实时消息推送
  - 消息操作和筛选

### 演示和测试
- **`AuditModuleDemo.vue`**: 完整功能演示页面
  - 分模块功能展示
  - 交互式演示
  - 状态监控面板
  
- **`audit-module.test.ts`**: 单元测试和集成测试
  - 核心功能测试
  - 数据验证测试
  - 集成流程测试

## 🚀 快速开始

### 1. 环境准备
```bash
# 进入项目目录
cd /home/ubuntu/KAG/kag/examples/002medqc/MedQC0817

# 安装依赖（如果需要）
npm install
```

### 2. 数据库初始化
```bash
# 在Supabase控制台执行SQL脚本
# 或使用psql命令行工具
psql -h <host> -U <user> -d <database> -f database/migrations/20241224_create_audit_tables.sql
```

### 3. 环境变量配置
```bash
# 创建.env文件并配置
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key
```

### 4. 启动演示
```bash
# 使用启动脚本
./scripts/start-audit-demo.sh

# 或手动启动
npm run dev
```

### 5. 访问演示
- 主页: http://localhost:3000
- 演示页面: http://localhost:3000/audit-module-demo

## 🔗 与现有系统集成

### Phase 1组件依赖
```typescript
// 需要确保以下现有组件可用
import { integratedQCEngine } from './integrated-qc-engine'
import { intelligentQCCache } from './intelligent-cache'
import { dynamicPromptGenerator } from './dynamic-prompt-generator'
import { supabase } from '@/lib/supabase'
```

### 路由配置
```typescript
// 需要在路由中添加演示页面
{
  path: '/audit-module-demo',
  name: 'AuditModuleDemo',
  component: () => import('@/views/AuditModuleDemo.vue')
}
```

### 权限配置
```typescript
// 需要在用户权限系统中添加审核相关角色
const auditRoles = [
  'qc_reviewer_dept',     // 科室级审核员
  'qc_reviewer_hospital', // 院级审核员
  'qc_reviewer_expert'    // 专家级审核员
]
```

## 📊 功能特性总览

### ✅ 已实现功能
- [x] 数据库表结构设计
- [x] 完整的TypeScript类型定义
- [x] 审核任务管理服务
- [x] 智能抽样算法
- [x] 多级审核流程
- [x] AI辅助缺陷识别
- [x] 消息通知系统
- [x] Supabase实时集成
- [x] Vue组件实现
- [x] 演示页面
- [x] 单元测试
- [x] 启动脚本

### 🔄 待完善功能
- [ ] 缺陷卡片组件 (DefectCard.vue)
- [ ] AI建议面板组件 (AISuggestionsPanel.vue)
- [ ] 缺陷表单组件 (DefectForm.vue)
- [ ] 审核时间线组件 (AuditTimeline.vue)
- [ ] 消息详情组件 (MessageDetail.vue)
- [ ] 任务创建表单组件 (CreateAuditTaskForm.vue)
- [ ] 任务列表组件 (AuditTaskList.vue)

### 🎯 扩展方向
- [ ] 移动端适配
- [ ] 报表统计功能
- [ ] 工作流引擎集成
- [ ] 第三方系统集成
- [ ] 性能优化
- [ ] 国际化支持

## 🛠️ 开发指南

### 添加新的审核级别
1. 在 `audit-module.ts` 中扩展 `AuditLevel` 类型
2. 更新权限矩阵配置
3. 修改多级审核组件
4. 更新数据库约束

### 添加新的消息类型
1. 在 `audit-module.ts` 中扩展 `MessageType` 类型
2. 更新消息生成服务
3. 添加消息处理逻辑
4. 更新前端展示组件

### 集成新的AI功能
1. 扩展 `AIDefectSuggestion` 接口
2. 在审核结果服务中添加AI调用
3. 更新前端AI建议组件
4. 添加相应的测试用例

## 📞 技术支持

如有问题或需要帮助，请参考：
- 📖 [AUDIT_MODULE_README.md](./AUDIT_MODULE_README.md) - 详细实现文档
- 🧪 [tests/audit-module.test.ts](./tests/audit-module.test.ts) - 测试用例
- 🚀 [scripts/start-audit-demo.sh](./scripts/start-audit-demo.sh) - 启动脚本

---

*项目结构文档 - 最后更新: 2024-12-24*
