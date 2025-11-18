# 新版演示页面 - 四川质控 API 集成测试指南

## 📋 概述

本文档说明如何测试新版 LLM 质控演示页面与四川质控引擎的集成。

## 🔧 修改内容

### 1. 添加了四川质控数据转换函数

**文件**: `src/stores/qcDemo.ts`

**函数**: `adaptSichuanQCResult()`

**功能**: 将四川质控 API 的响应格式转换为演示页面需要的 `QCResult` 格式

**转换映射**:
- `evaluation_summary.compliance_rate` → `overallScore` (0-100分)
- `evaluation_summary.overall_grade` → `overallGrade` (甲/乙/丙)
- `evaluation_results` (不合规项) → `issues[]`
- `evaluation_results` (全部) → `ruleResults[]`
- `performance_metrics.processing_time` → `metadata.processingTime`
- `performance_metrics.token_usage` → `metadata.totalTokens`

### 2. 修改了 runQCAnalysis() 函数

**文件**: `src/stores/qcDemo.ts`

**修改点**:
- 步骤 1: 准备调用四川质控引擎
- 步骤 2: 直接调用 `/api/v1/qc/sichuan/evaluate` (同步返回，无需轮询)
- 使用 `adaptSichuanQCResult()` 转换响应数据

### 3. 添加了通用 API 方法

**文件**: `src/services/apiService.ts`

**新增方法**:
- `ApiService.post<T>(url, data)` - 通用 POST 请求
- `ApiService.get<T>(url, params)` - 通用 GET 请求

## 🚀 测试步骤

### 前置条件

1. ✅ 后端服务运行在 `http://localhost:8000`
2. ✅ 前端服务运行在 `http://localhost:3000`
3. ✅ 已登录系统 (admin@medqc.com / admin123)
4. ✅ 四川质控引擎已配置 LLM API 密钥

### 测试流程

#### 步骤 1: 进入新版演示页面

1. 登录系统
2. 点击左侧菜单 "演示与工具" → "LLM质控演示新版（测试）"
3. 确认页面加载正常，看到：
   - 顶部紫色渐变控制面板
   - 右侧通知/申诉管理标签页
   - 底部统计面板（需要向下滚动）

#### 步骤 2: 选择测试对象

1. 在 "步骤 1：测试对象选择" 中：
   - 选择一个病历记录
   - 选择一个文书（如"首次病程记录"）
2. 点击 "下一步"

#### 步骤 3: 配置质控规则

1. 在 "步骤 2：规则配置" 中：
   - 勾选几个质控规则（建议 3-5 个）
2. 点击 "下一步"

#### 步骤 4: 运行质控分析

1. 在 "步骤 3：运行与结果" 中：
   - 点击顶部控制面板的 "开始演示" 按钮
2. 观察分析过程：
   - 进度条应该显示分析进度
   - 控制台应该输出日志信息
   - 等待 20-30 秒（真实 LLM API 调用）

#### 步骤 5: 查看分析结果

1. 分析完成后，检查：
   - **总体评分**: 应该显示 0-100 分
   - **总体等级**: 应该显示甲/乙/丙级
   - **发现问题**: 应该列出不合规的质控项
   - **改进建议**: 应该显示整改建议
   - **规则结果**: 应该显示所有规则的执行结果

2. 向下滚动，查看底部面板：
   - **统计与进度**: 显示规则数量、合规率等
   - **演示日志**: 显示详细的执行日志
   - **性能监控**: 显示 Token 使用量、处理时间等

## 🔍 验证要点

### 1. API 调用验证

打开浏览器开发者工具 (F12)，切换到 "Network" 标签页：

**预期请求**:
```
POST /api/v1/qc/sichuan/evaluate
```

**请求体**:
```json
{
  "document_id": "doc-xxx",
  "document_content": "病历内容...",
  "document_type": "首次病程记录",
  "persist": false
}
```

**响应体**:
```json
{
  "document_id": "doc-xxx",
  "evaluation_summary": {
    "total_rules": 68,
    "compliant_rules": 58,
    "compliance_rate": 85.3,
    "overall_grade": "乙级",
    "critical_violations": 3
  },
  "performance_metrics": {
    "processing_time": 25.6,
    "token_usage": 3500,
    "estimated_cost": 0.007
  },
  "evaluation_results": [...]
}
```

### 2. 控制台日志验证

打开浏览器控制台，应该看到：

```
[Demo Log] 准备调用四川质控引擎 API...
[Demo Log] 正在调用四川质控引擎进行分析...
[Demo Log] 发送质控请求到后端...
✅ [四川质控] 分析完成: { documentId: "...", complianceRate: 85.3, ... }
[Demo Log] 质控分析完成
```

### 3. 数据转换验证

检查 `analysisResult` 的数据结构：

```javascript
// 在浏览器控制台运行
const store = window.__PINIA__.state.value.qcDemo
console.log('Analysis Result:', store.analysisResult)
```

**预期输出**:
```javascript
{
  id: "doc-xxx",
  recordId: "record-xxx",
  overallScore: 85,  // 从 compliance_rate 转换
  overallGrade: "乙级",
  analysisDate: "2025-10-17T...",
  issues: [  // 只包含不合规项
    {
      id: "...",
      ruleName: "规则名称",
      ruleId: "SC-001",
      description: "检测到质控问题",
      severity: "medium",
      category: "general",
      location: "病历正文",
      suggestion: "请根据规则要求进行整改",
      evidence: "...",
      canAppeal: true
    }
  ],
  suggestions: [...],
  ruleResults: [  // 包含所有规则
    {
      ruleId: "SC-001",
      ruleName: "规则名称",
      passed: false,
      score: 0,
      maxScore: 100,
      details: "...",
      executionTime: 25.6,
      confidence: 0.85
    }
  ],
  metadata: {
    analysisVersion: "2.0.0",
    modelVersion: "Sichuan-QC-Single-Prompt",
    processingTime: 25.6,
    rulesApplied: 68,
    totalTokens: 3500,
    confidence: 0.85,
    engine: "Sichuan-QC-Engine",
    ...
  }
}
```

## ❌ 常见问题

### 问题 1: 请求超时

**症状**: 显示 "timeout of 15000ms exceeded"

**原因**: 
- 后端服务未启动
- LLM API 响应慢

**解决**:
```bash
# 检查后端服务
curl http://localhost:8000/api/v1/health

# 重启后端
cd apps/medqc-web/backend
source venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 问题 2: 返回 Mock 数据

**症状**: 响应中包含 `"_mock": true`

**原因**: 四川质控引擎未配置 LLM API 密钥

**解决**:
```bash
# 检查环境变量
cd apps/medqc-web/backend
cat .env | grep SICHUAN

# 应该看到:
# SICHUAN_API_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1
# SICHUAN_API_KEY=sk-xxx
# SICHUAN_MODEL=qwen2.5-14b-instruct
```

### 问题 3: 数据格式错误

**症状**: 页面显示异常或控制台报错

**原因**: 数据转换函数有问题

**解决**:
1. 检查 `adaptSichuanQCResult()` 函数
2. 查看控制台错误信息
3. 检查 API 响应格式是否符合预期

## 📊 性能指标

**预期性能**:
- **API 响应时间**: 20-30 秒（真实 LLM 调用）
- **Token 使用量**: 3000-5000 tokens
- **合规率**: 70-95%
- **规则数量**: 60-70 条

## ✅ 测试完成标准

- [ ] 能够成功调用四川质控 API
- [ ] 能够正确显示分析结果
- [ ] 能够查看详细的问题列表
- [ ] 能够查看规则执行结果
- [ ] 能够查看性能指标（Token 使用量、处理时间）
- [ ] 控制台无错误信息
- [ ] 数据格式正确转换

## 🎯 下一步

测试通过后，可以：
1. 优化数据转换逻辑
2. 添加更多错误处理
3. 改进 UI 显示
4. 添加更多统计指标
5. 支持批量分析

---

**文档版本**: 1.0.0  
**更新时间**: 2025-10-17  
**作者**: Augment Agent

