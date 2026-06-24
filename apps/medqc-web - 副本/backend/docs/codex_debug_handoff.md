# Codex Debug 交接文档 — Codex 审查问题修复进展

> 本文档描述基于 Codex 代码审查的 6 个问题的修复进展，以及当前需要 debug 的 3 个失败测试。

---

## 一、Codex 审查 6 个问题的修复状态

| # | 问题 | 严重度 | 修复状态 | 修复方式 |
|---|------|--------|---------|---------|
| 1 | `sichuan_qc_service.py` 重复方法定义，委托层被旧内联实现覆盖 | High | ✅ 已修复 | 删除 181 行旧内联代码（`_extract_check_points`/`_extract_core_guidance`/`_extract_enhanced_guidance`/`_precompute_time_facts`/`_build_prompt`），保留委托到 `QCPromptBuilder` 的薄代理方法 |
| 2 | 新增 TIME_RULES 不在运行路径 | High | ✅ 已修复 | #1 修复后自动解决，现在 `_precompute_time_facts` 调用走 `QCPromptBuilder.precompute_time_facts()`，12 条规则全部生效 |
| 3 | `_load_rules_from_db` 未合并 `custom_rules_33.json` | High | ✅ 已修复 | 在 `_load_rules_from_db` 中增加 `self._load_custom_rules_from_json()` 调用并 `.extend()` 到 `all_rules` |
| 4 | `RuleRouter` 兼容映射不全 | Medium | ✅ 已修复 | `course_record` 展开增加 `rescue_record` + `course_record` 自身；`operation_record` 展开增加 `surgery_safecheck_record`/`surgery_risk_assessment`/`anesthesia_record` + `operation_record` 自身 |
| 5 | ETL 缺 `handover_record` | Medium | ✅ 已修复 | `SYNC_TABLES` 新增 `handover_record`（接班记录），总计 27 张表 |
| 6 | 前端隐藏项 value 错误 | Low | ✅ 已修复 | 删除 `<a-select-option value="日常病程记录" disabled style="display:none">医嘱</a-select-option>` |

### 修改涉及的文件

| 文件 | 修改要点 |
|------|---------|
| `app/services/sichuan_qc_service.py` | 删除第 267-448 行旧内联代码（-181行）；第 191 行合并自定义规则 |
| `app/services/rule_router.py` | 第 50-65 行 `SECTION_TO_RULE_TYPES` 兼容映射完善 |
| `app/services/etl_sync.py` | 第 332 行后新增 `handover_record` 配置 |
| `src/views/qc/SichuanQCView.vue` | 第 153 行删除隐藏选项 |

---

## 二、当前问题：3 个单元测试失败

修复 #3（合并 custom 规则）后，`_load_rules_from_db` 现在返回的规则数量增加了（因为合并了 LX + LXE 规则），导致 3 个测试的**断言数字不再正确**。

### 失败的 3 个测试

```
FAILED tests/unit/test_sichuan_qc_service.py::TestRuleLoading::test_filter_rules_for_admission_record
FAILED tests/unit/test_sichuan_qc_service.py::TestEvaluation::test_evaluate_with_admission_rules
FAILED tests/unit/test_sichuan_qc_service.py::TestEvaluation::test_evaluate_compliance_rate
```

### 原因分析

修复前 `_load_rules_from_db` 只加载 `sichuan_rules_146.json`（268 条规则），修复后同时加载 `custom_rules_33.json`（89 条规则），总计 357 条。

按文书类型筛选的结果变化：

| 文书类型 | 修复前（仅SC） | 修复后（SC+LX+LXE） |
|---------|-------------|-------------------|
| 入院记录 | 29 条 | **53 条** |
| 日常病程记录 | 44 条 | **62 条** |

### 需要 Codex 做的

1. **运行测试确认失败**: `python -m pytest tests/unit/test_sichuan_qc_service.py -v --tb=short`
2. **更新断言数字**: 修改 `tests/unit/test_sichuan_qc_service.py` 中 3 个失败测试的断言，使用正确的规则数量
3. **确认 21 个通过的测试仍然通过**
4. **验证 `_load_rules_from_db` 行为正确**: 运行以下命令确认新的规则数量：
   ```bash
   python -c "
   from app.services.sichuan_qc_service import SichuanQCService
   import asyncio
   s = SichuanQCService()
   rules = asyncio.run(s._load_rules_from_db('入院记录'))
   print(f'入院记录: {len(rules)} 条')
   rules2 = asyncio.run(s._load_rules_from_db('日常病程记录'))
   print(f'日常病程记录: {len(rules2)} 条')
   all_sc = s._load_rules_from_json()
   all_custom = s._load_custom_rules_from_json()
   print(f'SC: {len(all_sc)}, Custom: {len(all_custom)}, Total: {len(all_sc)+len(all_custom)}')
   "
   ```

### 测试文件位置

- 测试代码: `tests/unit/test_sichuan_qc_service.py`
- 被测代码: `app/services/sichuan_qc_service.py`

### 关键修复位置参考

```python
# app/services/sichuan_qc_service.py 第 191-196 行（修复 #3 的核心变更）
async def _load_rules_from_db(self, document_type: str) -> List[Dict[str, Any]]:
    ...
    all_rules = self._load_rules_from_json()
    # 合并自定义规则（LX + LXE），修复 Codex #3
    custom_rules = self._load_custom_rules_from_json()
    all_rules.extend(custom_rules)
    if not all_rules:
        return []
    ...
```

---

## 三、额外注意事项

1. **`sichuan_qc_service.py` 当前 829 行**（原 1222 行，删除了 ~393 行冗余代码），确认文件结构完整、Python 语法正确
2. **`doc_type_mapping` 双重维护问题**（`sichuan_qc_service.py` 和 `unified_rule_engine.py` 各有一份中英文映射表）仍然存在，但不影响功能正确性，可以后续重构
3. **Vue 前端 ~40 个 TS lint 错误**是预存的 `ref<unknown>` 类型缺失问题，与本次修改无关
