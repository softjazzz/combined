# 贡献指南

感谢您对医疗质控系统项目的关注！我们欢迎所有形式的贡献。

## 🤝 如何贡献

### 报告问题
- 使用 [GitHub Issues](https://github.com/your-username/medqc-system/issues) 报告 bug
- 提供详细的问题描述和复现步骤
- 包含系统环境信息（操作系统、浏览器版本等）

### 提出功能建议
- 在 Issues 中使用 "enhancement" 标签
- 详细描述功能需求和使用场景
- 解释为什么这个功能对项目有价值

### 代码贡献

#### 开发环境设置
1. Fork 项目到您的 GitHub 账户
2. 克隆您的 fork：
   ```bash
   git clone https://github.com/your-username/medqc-system.git
   cd medqc-system
   ```
3. 安装依赖：
   ```bash
   # 前端依赖
   npm install
   
   # 后端依赖
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

#### 开发流程
1. 创建功能分支：
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. 进行开发并提交更改
3. 确保代码通过所有测试
4. 推送到您的 fork
5. 创建 Pull Request

## 📝 代码规范

### 前端代码规范
- 使用 TypeScript
- 遵循 ESLint 和 Prettier 配置
- 组件命名使用 PascalCase
- 文件命名使用 kebab-case

### 后端代码规范
- 使用 Python 3.12+
- 遵循 PEP 8 规范
- 使用 Black 进行代码格式化
- 使用 isort 进行导入排序

### 提交信息规范
使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
type(scope): description

[optional body]

[optional footer]
```

类型包括：
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式化
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

示例：
```
feat(auth): add password reset functionality
fix(api): resolve user authentication issue
docs(readme): update installation instructions
```

## 🧪 测试

### 运行测试
```bash
# 前端测试
npm run test

# 后端测试
cd backend
python test_api.py
```

### 测试要求
- 新功能必须包含相应的测试
- 确保所有现有测试通过
- 测试覆盖率应保持在 80% 以上

## 📋 Pull Request 检查清单

在提交 PR 之前，请确保：

- [ ] 代码遵循项目的代码规范
- [ ] 所有测试通过
- [ ] 添加了必要的测试
- [ ] 更新了相关文档
- [ ] 提交信息遵循规范
- [ ] PR 描述清晰，说明了更改内容

## 🔍 代码审查

所有的 Pull Request 都需要经过代码审查：

- 至少需要一个维护者的批准
- 解决所有审查意见
- 确保 CI/CD 检查通过

## 📚 开发资源

### 文档
- [API 文档](http://localhost:8001/docs)
- [前端组件文档](./docs/frontend.md)
- [后端架构文档](./docs/backend.md)

### 工具
- [Vue.js 文档](https://vuejs.org/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Ant Design Vue](https://antdv.com/)

## 🏷️ 版本发布

项目使用语义化版本控制：
- `MAJOR.MINOR.PATCH`
- 主要版本：不兼容的 API 更改
- 次要版本：向后兼容的功能添加
- 补丁版本：向后兼容的 bug 修复

## 📞 联系我们

如果您有任何问题或需要帮助：

- 创建 [GitHub Issue](https://github.com/your-username/medqc-system/issues)
- 发送邮件至：support@medqc.com
- 加入我们的讨论：[GitHub Discussions](https://github.com/your-username/medqc-system/discussions)

## 🙏 致谢

感谢所有为这个项目做出贡献的开发者！

---

**注意**：本项目涉及医疗数据处理，请确保您的贡献符合相关的医疗数据安全和隐私法规。

