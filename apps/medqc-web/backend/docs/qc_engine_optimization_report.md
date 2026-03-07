# 质控引擎优化完成情况说明

> 本文档供 Codex 检查所有修改是否正确、完整、无遗漏。

---

## 一、Codex 上轮审查 6 个 Bug 修复

### Bug #1 + #2: 重复方法定义 + TIME_RULES 未生效（High）

**问题**：`sichuan_qc_service.py` 中存在重复方法定义（`_extract_check_points` / `_extract_core_guidance` / `_extract_enhanced_guidance` / `_precompute_time_facts` / `_build_prompt`），Python 只保留后定义的版本，导致委托到 `QCPromptBuilder` 的新实现被覆盖，12 条 `TIME_RULES` 永远不会执行。

**修复**：删除了 181 行旧内联代码（原第 267-448 行），现在只保留第 209-231 行的薄代理方法，所有调用走 `QCPromptBuilder`。

**验证命令**：
```bash
python -c "
from app.services.sichuan_qc_service import SichuanQCService
s = SichuanQCService()
result = s._precompute_time_facts('SC-002', '入院时间：2025-01-01 10:00  书写时间：2025-01-02 08:30')
print('TIME_RULES 生效:', '系统预计算' in result)
"
```

**检查要点**：
- `sichuan_qc_service.py` 中 `_parse_llm_json_response` 应只有 1 个定义（约第 287 行）
- `_build_prompt` / `_precompute_time_facts` / `_extract_check_points` 等方法应只有简单的 `self.prompt_builder.xxx()` 委托调用，无内联实现

---

### Bug #3: `_load_rules_from_db` 未合并 custom 规则（High）

**问题**：`_load_rules_from_db`（现已重命名为 `_load_applicable_rules`）只加载 `sichuan_rules_146.json`，漏掉了 `custom_rules_33.json` 中的 LX + LXE 规则。

**修复**：在 `_load_applicable_rules` 中增加 `self._load_custom_rules_from_json()` 调用并 `.extend()` 到 `all_rules`。

**关键代码**（`sichuan_qc_service.py` 约第 149-153 行）：
```python
all_rules = self._load_rules_from_json()
# 合并自定义规则（LX + LXE），修复 Codex #3
custom_rules = self._load_custom_rules_from_json()
all_rules.extend(custom_rules)
```

**验证命令**：
```bash
python -c "
from app.services.sichuan_qc_service import SichuanQCService
import asyncio
s = SichuanQCService()
rules = asyncio.run(s._load_applicable_rules('入院记录'))
has_lx = any(r.get('rule_id','').startswith('LX') for r in rules)
has_lxe = any(r.get('rule_id','').startswith('LXE') for r in rules)
print(f'入院记录 {len(rules)} 条, LX={has_lx}, LXE={has_lxe}')
"
```

---

### Bug #4: RuleRouter 兼容映射不全（Medium）

**问题**：`SECTION_TO_RULE_TYPES` 中 `course_record` 缺少 `rescue_record` 和自身；`operation_record` 缺少 `surgery_safecheck_record` / `surgery_risk_assessment` / `anesthesia_record` 和自身。

**修复**：`rule_router.py` 第 50-65 行已补全映射。

**检查要点**（`rule_router.py`）：
```python
'course_record': [
    'first_course_record', 'daily_course_record',
    'senior_course_record', 'rescue_record',
    'course_record',  # LXE 规则使用此旧类型
],
'operation_record': [
    'surgery_record', 'presurg_summary', 'presurg_discussion',
    'postsurg_firstcourse_record', 'surgery_safecheck_record',
    'surgery_risk_assessment', 'anesthesia_record',
    'operation_record',  # LXE 规则使用此旧类型
],
```

---

### Bug #5: ETL 缺 `handover_record`（Medium）

**问题**：`SYNC_TABLES` 列表中有 `handoff_record`（交班记录）但缺 `handover_record`（接班记录）。

**修复**：在 `etl_sync.py` 的 `SYNC_TABLES` 中 `handoff_record` 后添加了 `handover_record` 配置。

---

### Bug #6: 前端隐藏项 value 错误（Low）

**问题**：`SichuanQCView.vue` 中有隐藏的"医嘱"选项，其 value 错误写成了 `日常病程记录`。

**修复**：直接删除了该隐藏选项行。

---

## 二、4 项新优化任务

### 优化 1: doc_type_mapping 去重

**变更**：
- **新建** `app/constants/doc_types.py`：定义 `DOC_TYPE_MAP`（29 项精确映射）、`DOC_TYPE_COMPAT_MAP`（9 项兼容映射）、`DOC_TYPE_FULL_MAP`（合并）、`DOC_TYPE_CN_TO_EN`（反向映射）
- **新建** `app/constants/__init__.py`
- **修改** `sichuan_qc_service.py`：`self.doc_type_mapping = dict(DOC_TYPE_FULL_MAP)` 替代 42 行手写字典
- **修改** `unified_rule_engine.py`：`_DOC_TYPE_CN_MAP = DOC_TYPE_MAP` 替代 25 行手写字典

**检查要点**：
- `doc_types.py` 的 `DOC_TYPE_MAP` 应覆盖所有 CDM 表名对应的文书类型
- `sichuan_qc_service.py` 和 `unified_rule_engine.py` 应 import 自 `app.constants.doc_types`，不再本地维护映射

---

### 优化 2: 方法重命名

**变更**：全局将 `_load_rules_from_db` 重命名为 `_load_applicable_rules`（方法实际从 JSON 加载，原名具有误导性）。

**影响**：
- `sichuan_qc_service.py`：5 处（1 个定义 + 4 个调用）
- `test_sichuan_qc_service.py`：8 处调用

**检查要点**：全局搜索 `_load_rules_from_db` 应返回 0 结果。

---

### 优化 3: Prompt 模板按文书类型定制化

**变更**：在 `qc_prompt_builder.py` 的 `build_prompt()` 中添加 `DOC_TYPE_FOCUS` 字典，为 8 种高频文书类型注入专属评审要点。

**覆盖的文书类型**：入院记录、首次病程记录、日常病程记录、上级查房记录、手术记录、出院记录、会诊记录、知情同意书。

**检查要点**：
- `DOC_TYPE_FOCUS` 在 `base_template.format()` 前定义
- `{focus_hint}` 占位符在模板中 `{rules_count}` 后面
- `format()` 调用包含 `focus_hint=focus_hint`
- 未覆盖的文书类型（如护理记录）应正常工作，`focus_hint` 为空字符串

---

### 优化 4: LXE 规则 applicable_documents 精确化

**变更**：`custom_rules_33.json` 中 27 条 LXE 规则的 `applicable_documents` 从旧粗粒度类型展开为精确类型。

**展开映射**：
| 旧类型 | 展开为 |
|--------|-------|
| `course_record` | `first_course_record`, `daily_course_record`, `senior_course_record`, `rescue_record` |
| `operation_record` | `surgery_record`, `presurg_summary`, `presurg_discussion`, `postsurg_firstcourse_record`, `surgery_safecheck_record`, `surgery_risk_assessment`, `anesthesia_record` |
| `informed_consent` | `consent_form` |
| `lab_report` | `labtest_item_report` |
| `transfusion_record` | `bloodtrans_record` |

**检查要点**：
- `custom_rules_33.json` 中不应再出现 `course_record` / `operation_record` / `informed_consent` / `lab_report` / `transfusion_record` 等旧类型
- 保留的精确类型（`admission_record` / `discharge_record` / `death_record`）不变

**验证命令**：
```bash
python -c "
import json
with open('app/data/custom_rules_33.json','r',encoding='utf-8') as f:
    rules = json.load(f)
old_types = {'course_record','operation_record','informed_consent','lab_report','transfusion_record'}
for r in rules:
    if r.get('rule_id','').startswith('LXE'):
        found = old_types & set(r.get('applicable_documents',[]))
        if found: print(f'ERROR: {r[\"rule_id\"]} 仍有旧类型: {found}')
print('检查完成')
"
```

---

## 三、测试状态

```
24 passed, 0 failed (0.46s)
```

**运行命令**：
```bash
cd apps/medqc-web/backend
python -m pytest tests/unit/test_sichuan_qc_service.py -v --tb=short
```

---

## 四、变更文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `app/constants/__init__.py` | NEW | 常量包初始化 |
| `app/constants/doc_types.py` | NEW | 共享文书类型映射 |
| `app/services/sichuan_qc_service.py` | MODIFIED | 删除重复方法 + 合并规则 + 导入常量 + 重命名 |
| `app/services/unified_rule_engine.py` | MODIFIED | 导入共享常量 |
| `app/services/qc_prompt_builder.py` | MODIFIED | DOC_TYPE_FOCUS 评审要点 |
| `app/services/rule_router.py` | MODIFIED | 兼容映射完善 |
| `app/services/etl_sync.py` | MODIFIED | 新增 handover_record |
| `app/data/custom_rules_33.json` | MODIFIED | 27条 LXE 精确化 |
| `tests/unit/test_sichuan_qc_service.py` | MODIFIED | 断言数字 + 方法名同步 |
| `src/views/qc/SichuanQCView.vue` | MODIFIED | 删除隐藏项 |
