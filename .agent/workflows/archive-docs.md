---
description: 将重要设计文档从 AI 对话 artifact 归档到项目 docs 目录
---

# 文档归档工作流

// turbo-all

## 触发时机

当以下文档产出时，**必须归档到项目 Git 仓库**：
- 📋 PRD / 需求文档
- 🏗️ 设计方案（架构、实施计划）
- 🧪 评测/测试方案
- 📊 招标对照分析
- 🔍 Gap 分析报告

**不需要归档**的：临时调试记录、一次性脚本说明、任务清单。

## 步骤

### 1. 确认归档目录

```
docs/
├── PRD-*.md                    # PRD 和需求文档（顶层）
├── plans/                      # 设计方案和实施计划
│   ├── settlement-llm-extraction-plan.md
│   ├── llm-coding-qc-eval-plan.md
│   └── ...
├── reports/                    # 评测报告和分析结果
│   └── ...
└── specs/                      # 技术规格和接口文档
    └── ...
```

### 2. 复制文件（从 artifact 到 docs）

```bash
# 文件命名规范：全小写、短横线分隔、英文
Copy-Item "<artifact_path>" "d:\大模型项目\lx0222\health-qc-monorepo\docs\<子目录>\<文件名>.md"
```

### 3. 提交

```bash
cd "d:\大模型项目\lx0222\health-qc-monorepo"
git add docs/
git commit -m "docs: 归档<文档简述>"
```

## 命名规范

| 文档类型 | 目录 | 命名示例 |
|---|---|---|
| PRD | `docs/` | `PRD-泸县验收收尾.md` |
| 设计方案 | `docs/plans/` | `settlement-llm-extraction-plan.md` |
| 评测方案 | `docs/plans/` | `llm-coding-qc-eval-plan.md` |
| 评测报告 | `docs/reports/` | `coding-qc-eval-report-2026-03.md` |
| 招标分析 | `docs/plans/` | `coding-qc-bidding-analysis.md` |

## 注意事项

- **适用文件**：只归档 `.md` 设计文档，不归档 `.resolved` 或 `.metadata.json`
- **去重**：归档前检查 `docs/` 下是否已存在同名文件
- **同步更新**：如果 artifact 更新了，记得同步更新 `docs/` 中的副本
