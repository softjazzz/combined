# MedQC 项目快速启动清单

> 📅 **更新日期**: 2025-10-12  
> 🎯 **目标**: 快速了解项目状态和下一步行动

---

## 🎯 项目概览

| 指标 | 数值 |
|------|------|
| **总体完成度** | 75% |
| **核心功能** | 90% |
| **测试覆盖率** | 40% → 目标 80% |
| **技术债务** | 中等 |
| **下一里程碑** | M1: 系统稳定 (Week 3) |

---

## ✅ 已完成的重要工作

### 最近完成（2025-10-11）

- ✅ **Migration 006**: 规则查询优化（性能提升 20倍）
- ✅ **权限系统分析**: RBAC vs Casbin 完整分析
- ✅ **实施指南**: 完整的 RBAC 实施代码和文档

### 之前完成（2025-10-09）

- ✅ **P1/P2 任务**: 88.9% 完成（8/9）
- ✅ **申诉流程**: 完整的申诉管理功能
- ✅ **API 版本控制**: 统一 `/api/v1` 路由
- ✅ **环境变量管理**: 完善的配置文档

---

## 🔴 本周必做（Week 1: 2025-10-14 ~ 2025-10-18）

### Day 1-2: 权限系统优化

```bash
# 1. 创建权限管理模块
cd apps/medqc-web/backend
touch app/core/permissions.py

# 2. 复制实施指南中的代码
# 参考: docs/RBAC_IMPLEMENTATION_GUIDE.md 第 1 节

# 3. 创建数据库迁移
cd ../../infra/supabase/medqc
touch migrations/007_enhance_rls_policies.sql
touch migrations/008_add_permission_audit_logs.sql

# 4. 复制 SQL 脚本
# 参考: docs/RBAC_IMPLEMENTATION_GUIDE.md 第 2-3 节
```

**验收标准**:
- [ ] `app/core/permissions.py` 创建完成
- [ ] 权限装饰器可用
- [ ] 数据库迁移脚本准备好

---

### Day 3-4: 执行迁移和更新路由

```bash
# 1. 在 Supabase Dashboard SQL Editor 中执行迁移
# 或使用命令行
psql -h your-db-host -U postgres -d medqc \
  -f migrations/007_enhance_rls_policies.sql

psql -h your-db-host -U postgres -d medqc \
  -f migrations/008_add_permission_audit_logs.sql

# 2. 更新 API 路由
# 在关键路由中添加权限装饰器
# 参考: docs/RBAC_IMPLEMENTATION_GUIDE.md 第 4 节
```

**验收标准**:
- [ ] 数据库迁移执行成功
- [ ] RLS 策略生效
- [ ] 权限审计日志表创建
- [ ] 至少 5 个 API 添加权限检查

---

### Day 5: 测试和验证

```bash
# 1. 运行单元测试
cd apps/medqc-web/backend
pytest tests/test_permissions.py -v

# 2. 手动测试
# 测试不同角色的权限
curl -H "Authorization: Bearer <token>" \
  http://localhost:8001/api/v1/medical-records

# 3. 检查审计日志
# 在 Supabase Dashboard 查看 permission_audit_logs 表
```

**验收标准**:
- [ ] 所有测试通过
- [ ] 权限检查正常工作
- [ ] 审计日志正确记录

---

## 🟡 下周计划（Week 2: 2025-10-21 ~ 2025-10-25）

### 测试覆盖率提升

- [ ] **Day 1-2**: 后端单元测试
  - 权限模块测试
  - API 路由测试
  - 服务层测试

- [ ] **Day 3-4**: 前端单元测试
  - 组件测试
  - Store 测试
  - 工具函数测试

- [ ] **Day 5**: 集成测试
  - API 集成测试
  - 数据库集成测试

**目标**: 测试覆盖率从 40% 提升到 60%

---

## 📊 本月目标（2025-10）

### 必须完成

- [ ] ✅ 权限系统优化（Week 1）
- [ ] ✅ 系统稳定性优化（Week 1）
- [ ] ✅ 测试覆盖率 > 60%（Week 2-3）
- [ ] 🔄 规则管理功能完善（Week 4）

### 可选完成

- [ ] 质控流程优化（部分）
- [ ] 性能优化（初步）

---

## 🚀 快速命令参考

### 启动服务

```bash
# 启动前后端
cd /home/ubuntu/coding/health-qc-monorepo
bash scripts/start_medqc.sh

# 或分别启动
# 后端
bash scripts/start_backend.sh

# 前端
cd apps/medqc-web
pnpm dev
```

### 运行测试

```bash
# 后端测试
cd apps/medqc-web/backend
pytest tests/ -v

# 前端测试
cd apps/medqc-web
pnpm test

# E2E 测试
pnpm test:e2e
```

### 数据库操作

```bash
# 连接数据库
psql -h your-db-host -U postgres -d medqc

# 执行迁移
psql -h your-db-host -U postgres -d medqc -f migrations/xxx.sql

# 查看表结构
\d qc_rules
\d permission_audit_logs
```

### 代码检查

```bash
# Python 代码检查
cd apps/medqc-web/backend
flake8 app/
black app/ --check

# TypeScript 代码检查
cd apps/medqc-web
pnpm lint
pnpm type-check
```

---

## 📚 关键文档

### 立即需要的

| 文档 | 用途 | 优先级 |
|------|------|--------|
| [RBAC_IMPLEMENTATION_GUIDE.md](./RBAC_IMPLEMENTATION_GUIDE.md) | 权限系统实施 | 🔴 高 |
| [PROJECT_STATUS_AND_ROADMAP.md](./PROJECT_STATUS_AND_ROADMAP.md) | 项目状态和路线图 | 🔴 高 |
| [DEVELOPMENT_ROADMAP.md](../DEVELOPMENT_ROADMAP.md) | 开发路线图 | 🟡 中 |

### 参考文档

| 文档 | 用途 |
|------|------|
| [RBAC_CASBIN_ANALYSIS.md](./RBAC_CASBIN_ANALYSIS.md) | 权限系统分析 |
| [MIGRATION_006_SUMMARY.md](../MIGRATION_006_SUMMARY.md) | 规则查询优化 |
| [FINAL_TASKS_COMPLETION_REPORT.md](./FINAL_TASKS_COMPLETION_REPORT.md) | P1/P2 任务报告 |
| [CODE_COMMENT_GUIDELINES.md](./CODE_COMMENT_GUIDELINES.md) | 代码注释规范 |
| [ENV_MANAGEMENT_GUIDE.md](./ENV_MANAGEMENT_GUIDE.md) | 环境变量管理 |

---

## ⚠️ 常见问题

### Q1: 服务启动失败？

**检查清单**:
```bash
# 1. 检查端口占用
lsof -ti:3000 | xargs kill -9
lsof -ti:8001 | xargs kill -9

# 2. 检查环境变量
cat apps/medqc-web/backend/.env

# 3. 检查数据库连接
psql -h your-db-host -U postgres -d medqc -c "SELECT 1"

# 4. 查看日志
tail -f apps/medqc-web/backend/logs/app.log
```

### Q2: 权限检查不工作？

**检查清单**:
```bash
# 1. 检查用户角色
SELECT * FROM user_roles WHERE user_id = 'xxx';

# 2. 检查 RLS 策略
SELECT * FROM pg_policies WHERE tablename = 'qc_rules';

# 3. 检查权限装饰器
# 确保路由函数有 @require_permission 装饰器

# 4. 查看审计日志
SELECT * FROM permission_audit_logs 
WHERE user_id = 'xxx' 
ORDER BY created_at DESC 
LIMIT 10;
```

### Q3: 测试失败？

**检查清单**:
```bash
# 1. 更新依赖
cd apps/medqc-web/backend
pip install -r requirements.txt

# 2. 检查测试数据库
# 确保使用测试数据库，不是生产数据库

# 3. 清理缓存
pytest --cache-clear

# 4. 运行单个测试
pytest tests/test_permissions.py::test_admin_has_all_permissions -v
```

---

## 📞 获取帮助

### 文档

- **项目文档**: `docs/` 目录
- **API 文档**: http://localhost:8001/docs
- **数据库文档**: `docs/database-schema.md`

### 工具

- **代码分析**: `python scripts/analyze_code_comments.py`
- **健康检查**: `bash scripts/health_check.sh`
- **安全审查**: `python scripts/security_audit.py`

### 联系

- **GitHub Issues**: 提交问题和建议
- **团队会议**: 每周技术讨论
- **紧急问题**: 联系技术负责人

---

## 🎯 成功指标

### Week 1 结束时

- [ ] 权限系统优化完成
- [ ] 所有 API 有权限检查
- [ ] RLS 策略生效
- [ ] 权限审计日志工作

### Week 2 结束时

- [ ] 测试覆盖率 > 60%
- [ ] 单元测试通过
- [ ] 集成测试通过

### Week 3 结束时

- [ ] 测试覆盖率 > 80%
- [ ] E2E 测试通过
- [ ] 系统稳定性优化完成
- [ ] **里程碑 M1: 系统稳定** ✅

---

**文档版本**: 1.0  
**最后更新**: 2025-10-12  
**维护者**: Augment Agent

