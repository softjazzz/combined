# LX0609 肿瘤病理族结构迁移验收

## 范围

本次只迁移 `LX0609-013`、`LX0609-019`、`LX0609-026`、`LX0609-027`
的客户展示事实合同和旧聚合器所有权；不修改规则判定、Prompt、状态映射、
Canonical 合同、保存/API/前端或客户文案。

## 职责收口

- 新增 `tumor_pathology_result_mapping.py`，作为四条规则的唯一展示事实白名单。
  该模块只验证执行器已裁决的 facts，不读资料、不重新判断病理/化疗/出院计划。
- Finalizer 接收并 fail-closed 校验该合同。
- 证据仍唯一沿 `RuleDecision.fact_refs → Binding → 公共
selected-document projector` 产生；mapping 不拼装证据 DTO，也不反查文书。
- 聚合器中该族专属引用从基线 **5** 处降为 **0**：013、019、026、027 的
  facts 分支各一处，以及 026 的来源白名单一处。

## 行为等价证据

- typed 主链冻结：013/019/026/027 的 `status`、`reason_code`、受控展示事实、
  客户证据坐标集合、LLM 调用数与 Prompt 均由现有冻结夹具覆盖。
- 026 的客户证据只使用执行器实际选择的化疗医嘱与病程 `fact_refs`；诊断触发
  fact 不再由聚合器白名单二次过滤。
- 旧 direct aggregate 入口不从展示 facts 回查或补造证据坐标。
- 新增守卫测试确保四条规则不再以 `if rule_id == ...` 形式回流聚合器。

## 验证

```powershell
py -3.10 -m pytest -q `
  backend/tests/unit/test_luxian_0609_tumor_pathology_freeze.py `
  backend/tests/unit/test_luxian_0609_native_tumor_pathology_execution.py `
  backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py `
  backend/tests/unit/test_luxian_0609_result_aggregator.py `
  backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py `
  -k "013 or 019 or 026 or 027 or tumor or pathology or executor_customer_display_facts"
```

结果：**142 passed**。

另执行：

```powershell
py -3.10 -m py_compile `
  backend/app/services/luxian_0609/tumor_pathology_result_mapping.py `
  backend/app/services/luxian_0609/canonical_result_finalizer.py `
  backend/app/services/luxian_0609_result_aggregator.py
```

结果：通过；`git diff --check` 无输出。

## 剩余风险

本提交是本地结构等价迁移。真实客户病例的三入口验收仍应在候选版本部署后，
使用同一资料快照复核证据定位；该验收不改变本次结构提交范围。
