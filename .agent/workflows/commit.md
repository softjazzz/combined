---
description: 提交代码更改到 Git
---

# Git 提交工作流

// turbo-all

## 步骤

1. 查看当前更改状态
```bash
git status
```

2. 暂存所有更改
```bash
git add .
```

3. 提交更改（根据类型选择前缀，使用中文描述）
```bash
git commit -m "<type>: <中文描述>"
```

**Commit 前缀规范:**
- `feat`: 新增功能
- `fix`: 修复 bug
- `docs`: 仅文档更改
- `style`: 代码格式（不影响功能）
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建/工具变动

4. 推送到远程仓库
```bash
git push
```

## 注意事项
- 当前在 `demo-backend-support` 分支进行开发
- commit message 必须使用中文
