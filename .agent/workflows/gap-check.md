---
description: 招标参数 vs 代码实现 gap 核查
---

# Gap 核查工作流

## 触发时机

- 每周五下午
- 每次完成一个大功能模块后
- 验收准备期

## 步骤

### 1. 读取招标参数

查看原始招标参数文档中所有"未实现/未上线"条款。

### 2. 逐条对照代码

对每个未实现条款：

```bash
# 搜索后端相关代码
cd "d:\大模型项目\lx0222\health-qc-monorepo"
grep -r "<关键词>" apps/medqc-web/backend/app/ --include="*.py" -l

# 搜索前端相关代码
grep -r "<关键词>" apps/medqc-web/src/ --include="*.vue" --include="*.ts" -l
```

### 3. 判定实现状态

| 状态 | 标准 |
|---|---|
| ✅ 已完成 | 后端 + 前端 + 测试全部到位 |
| 🟡 基本完成 | 核心功能已有，缺少细节或测试 |
| ❌ 未开始 | 无相关代码 |

### 4. 更新 PRD

```bash
# 编辑 PRD 文档
code "d:\大模型项目\lx0222\health-qc-monorepo\docs\PRD-泸县验收收尾.md"
```

更新：
- §2 总览表的状态列
- §8 覆盖矩阵
- §11 遗留 gap 工作量

### 5. 提交

```bash
cd "d:\大模型项目\lx0222\health-qc-monorepo"
git add docs/PRD-泸县验收收尾.md
git commit -m "docs: 更新招标参数 gap 核查结果"
```
