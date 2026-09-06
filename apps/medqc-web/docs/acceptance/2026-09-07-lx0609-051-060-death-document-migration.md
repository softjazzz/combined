# LX0609-051/060 死亡文书族结构迁移验收

## 职责收口

051/060 的客户展示事实合同已迁至 `death_document_result_mapping.py`：

- 执行器负责死亡适用性、七日时限、死亡记录存在性和 `fact_refs`；
- Finalizer 仅白名单化已裁决事实，并校验展示事实与最终状态自洽；
- 公共 selected-document projector 根据 Binding 后的 `fact_refs` 生成客户证据；
- Aggregator 只装配结果，不再校验 051/060 事实、不再读取私有文书 ID，也不再
  对这两个规则作历史证据反查。

## 行为等价范围

- 051：按死亡后最早有效讨论记录核对七日时限；窗口未成熟继续保持
  `data_gap / evaluation_window_not_mature`。
- 060：已确认死亡时，有死亡记录为 `compliant`，无死亡记录为
  `non_compliant / required_document_missing`。
- 不修改来源目录、Prompt、Renderer、数据库、API 或前端状态解释。

`source_document_refs` 仅作为 Native 执行器内部的逐行选择辅助，不再进入
`customer_display_facts`，也不会被 Aggregator 直接投影。无 Evidence Snapshot 的
旧直调聚合测试验证该路径不会回查或泄露私有文书 ID。

## 归零守卫

```powershell
rg -n 'LX0609-(051|060)' backend/app/services/luxian_0609_result_aggregator.py
```

预期无输出；两个规则在 Aggregator 中的专属事实、证据和状态分支均归零。

## 聚焦验收

在 `backend` 目录执行：

```powershell
py -3.10 -m pytest -q `
  tests/unit/test_luxian_0609_death_document_result_mapping.py `
  tests/unit/test_luxian_0609_result_aggregator.py `
  tests/unit/test_luxian_0609_native_extended_document_execution.py
```

验证重点：状态/原因码保持、051 仅定位最早有效讨论、060 缺失死亡记录的确定问题、
私有 ID 不进入展示事实，以及 Aggregator 无旧回查。
