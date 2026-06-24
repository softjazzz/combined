# 🏥 医疗质控系统 (MedQC)

基于大语言模型的智能医疗质控分析系统，提供专业的病案质量控制和改进建议。

## ✨ 项目特色

- 🤖 **AI驱动质控**：集成大语言模型进行智能病案分析
- 📊 **可视化分析**：直观的质控结果展示和数据可视化
- 🔄 **实时处理**：支持实时质控分析和进度跟踪
- 👥 **多角色支持**：管理员、质控主管、医务人员等不同角色
- 📱 **响应式设计**：完美适配桌面端和移动端
- 🔒 **安全可靠**：JWT认证、权限控制、数据加密

## 🏗️ 技术架构

### 前端技术栈
- **框架**: Vue 3 + TypeScript
- **构建工具**: Vite
- **UI组件**: Ant Design Vue
- **状态管理**: Pinia
- **路由**: Vue Router
- **样式**: Tailwind CSS
- **图表**: ECharts (计划中)

### 后端技术栈
- **框架**: FastAPI + Python 3.12
- **数据库**: PostgreSQL (计划中) / 内存存储 (当前)
- **认证**: JWT + OAuth2
- **API文档**: OpenAPI/Swagger
- **异步处理**: Celery + Redis (计划中)
- **AI集成**: OpenAI GPT-4 (计划中)

## 🚀 快速开始

### 环境要求
- Node.js 18+
- Python 3.12+
- npm/yarn/pnpm

### 安装和运行

#### 1. 克隆项目
```bash
git clone https://github.com/your-username/medqc-system.git
cd medqc-system
```

#### 2. 启动后端服务
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main_api.py
```
后端服务将在 http://localhost:8000 启动

#### 3. 启动前端服务
```bash
# 在项目根目录
npm install
npm run dev
```
前端服务将在 http://localhost:3000 启动

### 演示账户
- **管理员**: admin@medqc.com / admin123
- **质控主管**: qc@medqc.com / qc123456  
- **医务人员**: doctor@medqc.com / doctor123

## 📋 功能特性

### ✅ 已完成功能

#### 用户认证系统
- [x] 用户登录/注册
- [x] JWT令牌管理
- [x] 角色权限控制
- [x] 用户资料管理
- [x] 密码重置

#### 医疗记录管理
- [x] 病案记录CRUD操作
- [x] 文件上传和管理
- [x] 高级搜索和筛选
- [x] 批量操作
- [x] 数据统计

#### 质控分析系统
- [x] AI质控分析引擎
- [x] 实时分析进度跟踪
- [x] 质控结果可视化
- [x] 问题识别和分类
- [x] 改进建议生成
- [x] 质控规则管理
- [x] 历史记录查询

#### 系统管理
- [x] 用户管理
- [x] 权限配置
- [x] 系统设置
- [x] API文档

### 🔄 开发中功能
- [ ] 数据库持久化
- [ ] 真实AI模型集成
- [ ] 高级数据可视化
- [ ] 实时通知系统
- [ ] 移动端优化

## 📊 API接口

系统提供28个完整的REST API接口：

### 用户认证 (9个接口)
- `POST /api/auth/login` - 用户登录
- `POST /api/auth/register` - 用户注册
- `GET /api/auth/me` - 获取当前用户
- `PUT /api/auth/profile` - 更新用户资料
- `PUT /api/auth/password` - 修改密码
- `POST /api/auth/logout` - 用户登出
- `POST /api/auth/refresh` - 刷新令牌
- `POST /api/auth/forgot-password` - 忘记密码
- `POST /api/auth/reset-password` - 重置密码

### 医疗记录 (10个接口)
- `GET /api/records` - 获取记录列表
- `GET /api/records/{id}` - 获取记录详情
- `POST /api/records` - 创建记录
- `PUT /api/records/{id}` - 更新记录
- `DELETE /api/records/{id}` - 删除记录
- `DELETE /api/records/batch` - 批量删除
- `POST /api/records/export` - 导出记录
- `GET /api/records/statistics` - 获取统计
- `POST /api/records/upload` - 文件上传
- `POST /api/records/{id}/duplicate` - 复制记录

### 质控分析 (9个接口)
- `POST /api/qc/analyze/{id}` - 开始分析
- `POST /api/qc/analyze/batch` - 批量分析
- `GET /api/qc/result/{id}` - 获取结果
- `GET /api/qc/progress/{id}` - 获取进度
- `GET /api/qc/rules` - 获取规则
- `POST /api/qc/rules` - 创建规则
- `PUT /api/qc/rules/{id}` - 更新规则
- `DELETE /api/qc/rules/{id}` - 删除规则
- `GET /api/qc/history` - 获取历史

详细API文档：http://localhost:8000/docs

## 🧪 测试

### API测试
访问 http://localhost:3000/debug/api-test 进行完整的API功能测试

### 运行测试脚本
```bash
cd backend
python test_api.py
```

## 📁 项目结构

```
MedQC0817/
├── src/                    # 前端源码
│   ├── components/         # Vue组件
│   ├── views/             # 页面视图
│   ├── stores/            # 状态管理
│   ├── services/          # API服务
│   ├── types/             # TypeScript类型
│   └── router/            # 路由配置
├── backend/               # 后端源码
│   ├── main_api.py        # 主API服务
│   ├── test_api.py        # API测试脚本
│   ├── requirements.txt   # Python依赖
│   └── venv/              # 虚拟环境
├── docs/                  # 项目文档
├── tests/                 # 测试文件
└── README.md              # 项目说明
```

## 🔧 开发指南

### 环境变量配置
创建 `.env.development` 文件：
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_TITLE=医疗质控系统
VITE_ENABLE_DEBUG=true
```

创建 `backend/.env` 文件：
```env
JWT_SECRET=your-secret-key-here
DATABASE_URL=postgresql://user:pass@localhost/medqc
OPENAI_API_KEY=your-openai-key-here
```

### 代码规范
- 前端：ESLint + Prettier
- 后端：Black + isort
- 提交：Conventional Commits

### 贡献指南
1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📈 路线图

### 近期计划 (1-2个月)
- [ ] 数据库持久化集成
- [ ] 真实AI质控分析引擎
- [ ] 高级数据可视化仪表板
- [ ] 实时通知和协作功能

### 中期计划 (3-6个月)
- [ ] 移动端应用开发
- [ ] 多医院多租户支持
- [ ] 高级报表和分析
- [ ] 第三方系统集成

### 长期计划 (6-12个月)
- [ ] 机器学习模型训练
- [ ] 预测性质控分析
- [ ] 知识图谱集成
- [ ] 国际化支持

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🤝 支持

如果您觉得这个项目有用，请给我们一个 ⭐️

## 📞 联系我们

- 项目主页: https://github.com/your-username/medqc-system
- 问题反馈: https://github.com/your-username/medqc-system/issues
- 邮箱: support@medqc.com

---

**注意**: 这是一个演示项目，包含模拟数据。在生产环境中使用前，请确保符合相关医疗数据安全和隐私法规。
