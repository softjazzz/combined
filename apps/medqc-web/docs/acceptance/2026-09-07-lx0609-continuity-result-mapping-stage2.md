# LX0609 连续性/会诊族结果映射阶段 2 验收

## 范围

本次只接线 LX0609-069、071、072、073、074 的客户展示 facts 合同：

- `continuity_result_mapping.py` 是五条规则 facts 白名单的唯一映射所有者；它不读取材料、不选择证据、不生成客户 DTO，也不解释状态或原因码。
- Finalizer 委托该映射，并声明五规则的客户文书证据只能由公共、逐行的 `RuleDecision.fact_refs` 投影。
- Aggregator 已物理删除五条规则的 facts 白名单、`controlled_consultation_events` 和 071 的 `source_document_refs` 旧证据分支；不存在精确选中文书时输出不带客户文书证据。迁移入口的遗留白名单尾部及其 `controlled_list`、`controlled_trigger_orders` 死 helper 也已删除。

未修改 native 执行器、Renderer、API、前端，且未增加 status↔facts 推断或改变业务口径。

## 结构收益

验证时相对 `HEAD` 的父文件行数为：

| 文件                                                             | HEAD | 当前 | 变化 |
| ---------------------------------------------------------------- | ---: | ---: | ---: |
| `backend/app/services/luxian_0609_result_aggregator.py`          | 1766 | 1066 | -700 |
| `backend/app/services/luxian_0609/canonical_result_finalizer.py` |  888 |  908 |  +20 |
| `backend/app/services/luxian_0609/continuity_result_mapping.py`  | 新增 |  216 | +216 |

Aggregator 仍负责装配、排序及公共证据投影；迁出的完整职责是五规则现有可达 facts 形状的白名单校验与私有字段剥离。

## 合同验证

- 映射测试冻结全部可达 facts 形状和非法形状 fail-closed；069 保持接受 date-only，并将长度合规但日历非法的日期安全拒绝为 `None`；071 multi-event 保持接受旧逻辑允许的非 ISO 短字符串。
- Finalizer 测试覆盖五条规则的映射委托、`fact_refs` 公共证据要求和非法 typed facts 降级为 `technical_error/model_invalid_output`。
- Aggregator 测试覆盖五规则均调用公共选中文书投影、无 `fact_refs` 时不从 071 私有 `source_document_refs` 回退，并断言 Aggregator 源码中五个规则号及 `controlled_consultation_events` 均为零。

## 验证命令与结果

```powershell
py -3.10 -m pytest -q tests/unit/test_luxian_0609_surgery_presence_freeze.py tests/unit/test_luxian_0609_continuity_result_mapping.py tests/unit/test_luxian_0609_canonical_result_finalizer.py tests/unit/test_luxian_0609_result_aggregator.py
# 478 passed

py -3.10 -m ruff check app/services/luxian_0609/canonical_result_finalizer.py app/services/luxian_0609_result_aggregator.py app/services/luxian_0609/continuity_result_mapping.py tests/unit/test_luxian_0609_canonical_result_finalizer.py tests/unit/test_luxian_0609_continuity_result_mapping.py
# All checks passed

git diff --check -- backend/app/services/luxian_0609_result_aggregator.py backend/app/services/luxian_0609/canonical_result_finalizer.py backend/app/services/luxian_0609/continuity_result_mapping.py backend/tests/unit/test_luxian_0609_result_aggregator.py backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py backend/tests/unit/test_luxian_0609_continuity_result_mapping.py
# 无输出
```

`test_luxian_0609_result_aggregator.py` 整文件 ruff 另有本任务前已有的 E701/F821（2489–2516、4248、6214、6681–6682），未在本次无关结构迁移中修改；本次生产文件、新模块和新增 Finalizer 测试均通过 ruff。
