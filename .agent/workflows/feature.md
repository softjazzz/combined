---
description: 创建新的功能分支
---

# 创建功能分支

## 步骤

1. 确保在 demo-backend-support 分支
```bash
git checkout demo-backend-support
git pull origin demo-backend-support
```

2. 创建功能分支
```bash
git checkout -b feature/<功能名称>
```

**分支命名规范:**
- `feature/xxx` - 新功能
- `hotfix/xxx` - 紧急修复
- `release/xxx` - 发布准备

3. 开发完成后合并回主开发分支
```bash
git checkout demo-backend-support
git merge feature/<功能名称>
git push origin demo-backend-support
```

4. 删除本地功能分支
```bash
git branch -d feature/<功能名称>
```
