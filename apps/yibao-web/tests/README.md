# 测试文件结构说明

本项目的测试文件已重新组织，按类型分类存放：

## 目录结构

```
tests/
├── frontend/          # 前端单元测试和组件测试
├── backend/           # 后端测试文件
│   ├── test_*.py      # Python 后端测试
│   └── test_data/     # 测试数据和工具
├── integration/       # 集成测试
│   ├── test-auth-persistence*.js
│   ├── test-complete-analytics.js
│   ├── test-data-analytics.js
│   └── test-qc-engine-improvements.js
├── e2e/              # 端到端测试
│   ├── test-medical-records.html
│   └── test-page-verification.html
└── helpers/          # 测试辅助工具
    ├── mock-analytics-server.js
    ├── verify-cloud-server.js
    └── verify-test-data.js
```

## 运行测试

### 前端测试
```bash
npm run test          # 运行所有前端测试
npm run test:unit     # 单元测试
npm run test:e2e      # 端到端测试
```

### 后端测试
```bash
npm run test:backend  # 运行后端测试
```

### 集成测试
```bash
npm run test:integration  # 运行集成测试
```

## 测试文件说明

### Backend 测试
- `test_qc_engine.py` - 质控引擎测试
- `test_descriptions.py` - 描述功能测试
- `test_sandbox.py` - 沙箱环境测试
- `test_filtering.py` - 过滤功能测试
- `test_rule_debug.py` - 规则调试测试

### Integration 测试
- `test-auth-persistence*.js` - 认证持久化测试
- `test-complete-analytics.js` - 完整分析功能测试
- `test-data-analytics.js` - 数据分析测试
- `test-qc-engine-improvements.js` - 质控引擎改进测试

### E2E 测试
- `test-medical-records.html` - 病历页面端到端测试
- `test-page-verification.html` - 页面验证测试

### Helpers
- `mock-analytics-server.js` - 分析服务模拟服务器
- `verify-*.js` - 验证脚本和工具