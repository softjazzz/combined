# 语义质控规则引擎测试方案 📋

**创建时间**: 2025-10-11  
**创建人**: Augment Agent  
**版本**: 1.0

---

## 🎯 测试目标

基于我们澄清的语义质控规则本质（**基于 Prompt 模板的 LLM 调用**），为 health-qc-monorepo 项目设计全面的测试方案。

### 核心理解

1. ✅ **语义质控规则 = Prompt 模板**
2. ✅ **规则执行 = LLM API 调用**
3. ✅ **规则存储在数据库 `qc_rules` 表中**
4. ✅ **`prompt_template` 字段是规则的核心**

---

## 📊 测试范围

### 1. 语义规则引擎核心功能

| 功能模块 | 测试内容 | 测试文件 |
|---------|---------|---------|
| **规则 CRUD** | 创建、读取、更新、删除规则 | `test_semantic_rules_crud.py` |
| **规则加载** | 从数据库加载规则（包含 Prompt 模板） | `test_semantic_rules_engine.py` |
| **Prompt 构建** | 将病历内容填充到 Prompt 模板 | `test_semantic_rules_engine.py` |
| **LLM 调用** | 调用真实 LLM API（阿里云百炼） | `test_semantic_rules_engine.py` |
| **结果解析** | 解析 LLM 响应并提取质控结果 | `test_semantic_rules_engine.py` |
| **批量执行** | 批量执行多个规则 | `test_semantic_rules_engine.py` |

### 2. 数据库集成

| 功能模块 | 测试内容 | 测试文件 |
|---------|---------|---------|
| **Supabase 连接** | 测试 Supabase 连接状态 | `test_semantic_rules_crud.py` |
| **规则查询** | 测试规则查询（过滤、排序、分页） | `test_semantic_rules_crud.py` |
| **规则导入** | 测试批量导入规则 | `test_semantic_rules_crud.py` |
| **规则导出** | 测试导出规则 | `test_semantic_rules_crud.py` |

### 3. LLM API 调用

| 功能模块 | 测试内容 | 测试文件 |
|---------|---------|---------|
| **真实 API 调用** | 测试阿里云百炼 API 调用 | `test_semantic_rules_engine.py` |
| **Mock 模式** | 测试 Mock 模式（无 API Key 时） | `test_semantic_rules_engine.py` |
| **错误处理** | 测试 API 调用失败的处理 | `test_semantic_rules_engine.py` |
| **超时处理** | 测试 API 超时的处理 | `test_semantic_rules_engine.py` |

### 4. 对比测试

| 对比维度 | 测试内容 | 测试文件 |
|---------|---------|---------|
| **引擎对比** | 语义规则引擎 vs 四川质控引擎 | `test_semantic_rules_comparison.py` |
| **Prompt 对比** | 不同 Prompt 模板的结果差异 | `test_semantic_rules_comparison.py` |
| **模式对比** | 真实 LLM vs Mock 模式 | `test_semantic_rules_comparison.py` |
| **成本对比** | Token 使用量和成本分析 | `test_semantic_rules_comparison.py` |

---

## 🧪 测试类型

### 1. 单元测试（Unit Tests）

**目标**: 测试独立功能模块

**测试文件**: `tests/unit/test_semantic_rules_crud.py`

**测试内容**:
- ✅ 规则 CRUD 操作
- ✅ 规则查询（过滤、排序、分页）
- ✅ 规则导入/导出
- ✅ Supabase 连接状态检查
- ✅ 错误处理

**示例测试**:
```python
def test_get_all_rules_empty(client: TestClient):
    """测试获取所有规则 - 空列表"""
    response = client.get("/api/v1/semantic-rules")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["items"] == []

def test_create_rule(client: TestClient):
    """测试创建规则"""
    rule_data = {
        "rule_code": "SR-TEST-001",
        "name": "测试规则",
        "prompt_template": "这是一个测试 Prompt：{content}"
    }
    response = client.post("/api/v1/semantic-rules", json=rule_data)
    assert response.status_code == 200
```

### 2. 集成测试（Integration Tests）

**目标**: 测试完整的规则执行流程

**测试文件**: `tests/integration/test_semantic_rules_engine.py`

**测试内容**:
- ✅ 完整的规则执行流程（加载 → 填充 → 调用 LLM → 解析）
- ✅ 真实 LLM API 调用
- ✅ 不同类型病历的质控
- ✅ 不同类别规则的执行
- ✅ LLM 响应解析的鲁棒性

**示例测试**:
```python
def test_semantic_rule_execution_with_real_llm(client: TestClient):
    """测试语义规则执行 - 使用真实 LLM API"""
    response = client.post(
        "/api/v1/qc/sichuan/evaluate",
        json={
            "document_id": "test-001",
            "document_content": medical_record_content,
            "document_type": "首次病程记录"
        }
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"
```

### 3. 对比测试（Comparison Tests）

**目标**: 对比不同实现方式的结果差异

**测试文件**: `tests/integration/test_semantic_rules_comparison.py`

**测试内容**:
- ✅ 语义规则引擎 vs 四川质控引擎
- ✅ 不同 Prompt 模板的结果
- ✅ 真实 LLM vs Mock 模式
- ✅ 成本和性能分析

**示例测试**:
```python
def test_compare_sichuan_engine_vs_mock_engine(client: TestClient):
    """对比测试：四川质控引擎 vs 通用质控引擎"""
    # 测试四川质控引擎（真实 LLM）
    response_sichuan = client.post("/api/v1/qc/sichuan/evaluate", ...)
    
    # 对比结果
    print(f"四川引擎合规率：{result_sichuan['compliance_rate']}%")
    print(f"四川引擎成本：${result_sichuan['cost']}")
```

### 4. 性能测试（Performance Tests）

**目标**: 测试批量规则执行的性能

**测试文件**: `tests/integration/test_semantic_rules_comparison.py`

**测试内容**:
- ✅ 单次质控的执行时间
- ✅ 批量质控的性能
- ✅ Token 使用量统计
- ✅ API 调用成本分析

**示例测试**:
```python
def test_performance_and_cost_analysis(client: TestClient):
    """性能和成本分析测试"""
    # 执行多次测试
    for i in range(10):
        start_time = time.time()
        response = client.post("/api/v1/qc/sichuan/evaluate", ...)
        execution_time = time.time() - start_time
        
    # 计算平均值
    avg_time = sum(times) / len(times)
    avg_cost = sum(costs) / len(costs)
```

---

## 📝 测试场景

### 场景 1: 完整的首次病程记录

**病历特点**:
- ✅ 包含所有必需要素
- ✅ 主诉、现病史、诊断一致
- ✅ 用药合理

**预期结果**:
- 合规率：≥ 85%
- 等级：A 或 B
- 严重违规数：0

### 场景 2: 不完整的首次病程记录

**病历特点**:
- ❌ 缺少部分要素
- ❌ 描述过于简单
- ❌ 缺少辅助检查

**预期结果**:
- 合规率：< 75%
- 等级：C 或 D
- 严重违规数：≥ 1

### 场景 3: 不一致的病历

**病历特点**:
- ❌ 主诉与现病史不一致
- ❌ 诊断与症状不符
- ❌ 用药与诊断不符

**预期结果**:
- 合规率：< 70%
- 等级：C 或 D
- 发现一致性问题

### 场景 4: 不同类型的病历

**测试病历类型**:
- 首次病程记录
- 入院记录
- 出院记录
- 手术记录
- 病程记录

**预期结果**:
- 每种类型都能正确识别
- 应用对应的质控规则
- 返回准确的质控结果

---

## 🔍 测试数据

### 1. 规则数据（Fixtures）

**文件**: `tests/fixtures/semantic_rules_fixtures.py`

**包含**:
- ✅ 完整性检查规则（Prompt 模板）
- ✅ 一致性检查规则（Prompt 模板）
- ✅ 合理性检查规则（Prompt 模板）
- ✅ 批量规则数据

**示例**:
```python
@pytest.fixture
def sample_semantic_rule_completeness():
    return {
        "rule_code": "SR-COMP-001",
        "name": "主诉完整性检查",
        "prompt_template": """
你是一位资深病案质控专家。请检查主诉是否完整：
{content}
返回JSON格式：{"is_compliant": true/false, "score": 0-100}
"""
    }
```

### 2. 病历数据（Fixtures）

**文件**: `tests/fixtures/semantic_rules_fixtures.py`

**包含**:
- ✅ 完整的首次病程记录
- ✅ 不完整的首次病程记录
- ✅ 不一致的病历
- ✅ 不同类型的病历

### 3. LLM 响应数据（Fixtures）

**文件**: `tests/fixtures/semantic_rules_fixtures.py`

**包含**:
- ✅ 合规的 LLM 响应
- ✅ 不合规的 LLM 响应
- ✅ 格式错误的 LLM 响应

---

## 📊 测试执行

### 1. 运行所有测试

```bash
cd apps/medqc-web/backend
source .venv/bin/activate
pytest tests/ -v
```

### 2. 运行单元测试

```bash
pytest tests/unit/test_semantic_rules_crud.py -v
```

### 3. 运行集成测试

```bash
pytest tests/integration/test_semantic_rules_engine.py -v
```

### 4. 运行对比测试

```bash
pytest tests/integration/test_semantic_rules_comparison.py -v
```

### 5. 运行特定测试

```bash
pytest tests/integration/test_semantic_rules_engine.py::TestSemanticRulesEngine::test_semantic_rule_execution_with_real_llm -v -s
```

### 6. 生成测试报告

```bash
pytest tests/ -v --html=test_report.html --self-contained-html
```

---

## 📈 预期结果

### 1. 测试覆盖率

| 模块 | 目标覆盖率 | 当前状态 |
|------|-----------|---------|
| 规则 CRUD | ≥ 90% | 🟡 待测试 |
| 规则执行 | ≥ 85% | 🟡 待测试 |
| LLM 调用 | ≥ 80% | 🟡 待测试 |
| 结果解析 | ≥ 90% | 🟡 待测试 |

### 2. 性能指标

| 指标 | 目标值 | 当前值 |
|------|-------|-------|
| 单次质控时间 | < 20 秒 | 🟡 待测试 |
| Token 使用量 | < 3000 | 🟡 待测试 |
| 单次成本 | < $0.01 | 🟡 待测试 |
| 合规率准确性 | ≥ 85% | 🟡 待测试 |

### 3. 质量指标

| 指标 | 目标值 | 当前状态 |
|------|-------|---------|
| 测试通过率 | 100% | 🟡 待测试 |
| 代码覆盖率 | ≥ 85% | 🟡 待测试 |
| 文档完整性 | 100% | ✅ 完成 |

---

## 🎯 下一步行动

### 立即执行（今天）

1. ✅ **创建测试 Fixtures** - `semantic_rules_fixtures.py`
2. ✅ **创建单元测试** - `test_semantic_rules_crud.py`
3. ✅ **创建集成测试** - `test_semantic_rules_engine.py`
4. ✅ **创建对比测试** - `test_semantic_rules_comparison.py`
5. 🟡 **运行测试并生成报告**

### 短期（本周）

1. 🟡 **完善测试用例**（覆盖更多场景）
2. 🟡 **优化测试性能**（减少重复调用）
3. 🟡 **添加性能基准测试**
4. 🟡 **生成测试覆盖率报告**

### 中期（本月）

1. 🟡 **实现真实的语义规则引擎执行端点**（替换占位实现）
2. 🟡 **集成语义规则引擎到四川质控流程**
3. 🟡 **添加规则版本控制**
4. 🟡 **实现规则 A/B 测试**

---

## 📄 交付物

### 1. 测试文件

- ✅ `tests/fixtures/semantic_rules_fixtures.py` - 测试数据 Fixtures
- ✅ `tests/unit/test_semantic_rules_crud.py` - 单元测试
- ✅ `tests/integration/test_semantic_rules_engine.py` - 集成测试
- ✅ `tests/integration/test_semantic_rules_comparison.py` - 对比测试

### 2. 文档

- ✅ `SEMANTIC_RULES_ENGINE_TEST_PLAN.md` - 测试计划文档
- 🟡 `SEMANTIC_RULES_ENGINE_TEST_REPORT.md` - 测试报告（待生成）

### 3. 测试报告

- 🟡 HTML 测试报告
- 🟡 覆盖率报告
- 🟡 性能分析报告

---

**文档创建时间**: 2025-10-11  
**文档状态**: ✅ 完成  
**下一步**: 运行测试并生成报告

