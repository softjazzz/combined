# 科室级质控规则 - 集成测试套件

## 📋 概述

本目录包含科室级质控规则功能的完整集成测试套件，包括：
- 端到端测试（E2E）
- 性能测试
- 数据库性能分析
- 手动测试清单

---

## 📁 文件结构

```
tests/integration/
├── README.md                          # 本文件
├── prepare_test_data.sql              # 测试数据准备脚本
├── test_department_rules_e2e.py       # 端到端测试脚本
├── test_performance.py                # 性能测试脚本
├── analyze_db_performance.sql         # 数据库性能分析脚本
├── run_all_tests.sh                   # 集成测试执行脚本
├── MANUAL_TEST_CHECKLIST.md           # 手动测试清单
└── reports/                           # 测试报告目录（自动生成）
    ├── e2e_test_*.log
    ├── performance_test_*.log
    ├── db_performance_*.log
    └── integration_test_report_*.md
```

---

## 🚀 快速开始

### 前置条件

1. **后端服务运行**:
   ```bash
   cd apps/medqc-web/backend
   source venv/bin/activate
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
   ```

2. **前端服务运行**（可选，用于手动测试）:
   ```bash
   cd apps/medqc-web
   npm run dev
   ```

3. **Python 依赖**:
   ```bash
   pip3 install requests
   ```

4. **数据库访问**:
   - 确保可以访问 PostgreSQL 数据库
   - 设置环境变量（可选）:
     ```bash
     export DB_HOST=localhost
     export DB_PORT=5432
     export DB_NAME=postgres
     export DB_USER=postgres
     export PGPASSWORD=your_password
     ```

### 一键运行所有测试

```bash
cd tests/integration
chmod +x run_all_tests.sh
./run_all_tests.sh
```

这将自动执行：
1. 前置条件检查
2. 测试数据准备
3. 端到端测试
4. 性能测试
5. 数据库性能分析
6. 生成测试报告

---

## 📝 单独运行测试

### 1. 准备测试数据

```bash
psql -h localhost -U postgres -d postgres -f prepare_test_data.sql
```

**输出示例**:
```
NOTICE:  ✓ 清理旧的测试数据完成
NOTICE:  ✓ 创建测试科室: 4 个
NOTICE:  ✓ 创建测试全局规则: 5 条
========================================
测试数据准备完成
========================================
测试科室数量: 4
测试全局规则数量: 5
```

---

### 2. 运行端到端测试

```bash
python3 test_department_rules_e2e.py
```

**测试内容**:
- 创建科室规则（全新创建模式）
- 创建科室规则（基于全局规则创建模式）
- 更新科室规则
- 发布科室规则
- 查看变更历史
- 获取适用规则（仅全局规则）
- 获取适用规则（包含科室覆盖规则）
- 生效期控制测试

**预期输出**:
```
[INFO] 开始集成测试
[INFO] 运行测试: 创建科室规则（全新创建）
[SUCCESS] ✓ 创建科室规则（全新创建） - 通过 (0.25s)
...
========================================
测试总结
========================================
总测试数: 8
通过: 8
失败: 0
```

---

### 3. 运行性能测试

```bash
python3 test_performance.py
```

**测试内容**:
- 规则列表加载性能（目标 < 500ms）
- 规则匹配性能（目标 < 100ms）
- 质控执行性能（50条规则，目标 < 5s）

**预期输出**:
```
========================================
测试 1: 规则列表加载性能
目标: < 500 ms
========================================

测试名称: 规则列表加载
迭代次数: 10
平均时间: 245.32 ms
最小时间: 198.45 ms
最大时间: 312.67 ms
P95 时间: 298.12 ms
性能目标: < 500.00 ms
测试结果: ✓ 通过

...

========================================
性能测试总结
========================================
总测试数: 3
通过: 3
未达标: 0
```

---

### 4. 运行数据库性能分析

```bash
psql -h localhost -U postgres -d postgres -f analyze_db_performance.sql
```

**分析内容**:
- 规则列表查询性能（EXPLAIN ANALYZE）
- 规则匹配查询性能
- 索引使用情况
- 变更历史查询性能
- 表统计信息
- 慢查询分析

**输出示例**:
```
========================================
测试 1: 规则列表查询性能
========================================

QUERY PLAN
---------------------------------------------------------------------------
Limit  (cost=0.15..1.37 rows=20 width=1234) (actual time=0.023..0.156 rows=20 loops=1)
  ->  Index Scan using idx_qc_rules_scope_department on qc_rules  (cost=0.15..12.34 rows=202 width=1234) (actual time=0.022..0.145 rows=20 loops=1)
        Index Cond: (scope = 'department'::text)
Planning Time: 0.123 ms
Execution Time: 0.189 ms

分析：检查是否使用了索引，扫描行数是否合理
```

---

## 🧪 手动测试

参考 `MANUAL_TEST_CHECKLIST.md` 文档进行手动测试。

### 测试步骤

1. 打开手动测试清单文档
2. 按照清单逐项执行测试
3. 记录测试结果（通过/失败）
4. 记录发现的问题
5. 填写测试总结

### 测试部分

- **完整流程测试** (6 项)
- **筛选功能测试** (4 项)
- **规则匹配逻辑测试** (3 项)
- **生效期控制测试** (2 项)
- **审计日志测试** (1 项)
- **UI/UX 测试** (3 项)

---

## 📊 查看测试报告

测试报告自动生成在 `reports/` 目录下：

```bash
# 查看最新的集成测试报告
ls -lt reports/integration_test_report_*.md | head -1 | xargs cat

# 查看端到端测试日志
ls -lt reports/e2e_test_*.log | head -1 | xargs cat

# 查看性能测试日志
ls -lt reports/performance_test_*.log | head -1 | xargs cat

# 查看数据库性能分析日志
ls -lt reports/db_performance_*.log | head -1 | xargs cat
```

---

## 🔧 故障排查

### 问题 1: 后端服务未运行

**错误信息**:
```
[ERROR] 后端 API 服务未运行，请先启动后端服务
```

**解决方案**:
```bash
cd apps/medqc-web/backend
source venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

---

### 问题 2: 数据库连接失败

**错误信息**:
```
psql: error: connection to server at "localhost" (::1), port 5432 failed
```

**解决方案**:
1. 检查数据库是否运行
2. 检查连接参数（host, port, user, password）
3. 设置正确的环境变量

---

### 问题 3: Python 依赖缺失

**错误信息**:
```
ModuleNotFoundError: No module named 'requests'
```

**解决方案**:
```bash
pip3 install requests
```

---

### 问题 4: 权限不足

**错误信息**:
```
[ERROR] 权限不足
```

**解决方案**:
1. 确保使用 ADMIN 或 QC_MANAGER 角色的用户
2. 检查 token 是否有效
3. 重新登录获取新 token

---

## 📈 性能基准

### 目标性能指标

| 测试项 | 目标 | 说明 |
|--------|------|------|
| 规则列表加载 | < 500ms | 加载 20 条规则 |
| 规则匹配 | < 100ms | 单次规则匹配 |
| 质控执行 | < 5s | 执行 50 条规则 |

### 实际性能（待测试后填写）

| 测试项 | 实际结果 | 状态 |
|--------|---------|------|
| 规则列表加载 | ⏳ 待测试 | - |
| 规则匹配 | ⏳ 待测试 | - |
| 质控执行 | ⏳ 待测试 | - |

---

## 🐛 Bug 报告

如果发现 bug，请记录以下信息：

1. **Bug 描述**: 简要描述问题
2. **重现步骤**: 详细的重现步骤
3. **预期结果**: 应该发生什么
4. **实际结果**: 实际发生了什么
5. **环境信息**: 操作系统、浏览器、数据库版本等
6. **日志**: 相关的错误日志
7. **优先级**: P0（严重）/ P1（重要）/ P2（一般）

---

## 📚 相关文档

- [第四阶段完成报告](../../docs/PHASE_4_INTEGRATION_TEST_REPORT.md)
- [快速启动指南](../../docs/DEPARTMENT_RULES_QUICK_START.md)
- [PRD 文档](../../docs/PRD_DEPARTMENT_QC_RULES.md)
- [后端 API 文档](http://localhost:8001/docs)

---

## 🤝 贡献

如果你想改进测试套件，请：

1. 添加新的测试用例
2. 改进现有测试
3. 修复测试中的 bug
4. 更新文档

---

## 📝 更新日志

### v1.0 (2025-01-15)
- ✅ 创建测试数据准备脚本
- ✅ 创建端到端测试脚本
- ✅ 创建性能测试脚本
- ✅ 创建数据库性能分析脚本
- ✅ 创建集成测试执行脚本
- ✅ 创建手动测试清单
- ✅ 创建测试文档

---

**最后更新**: 2025-01-15  
**维护者**: Augment Agent  
**版本**: v1.0

