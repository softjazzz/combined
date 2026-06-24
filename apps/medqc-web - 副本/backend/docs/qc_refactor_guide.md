# 质控规则重构指导文档

> 写给新的 subagent，用于基于最新的数据表和映射文档重构 MedQC 系统的质控规则和质控功能。

---

## 一、你首先需要了解的上下文

### 项目位置

```
d:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web\
├── backend/           # FastAPI 后端
│   ├── app/
│   │   ├── routers/   # API 路由
│   │   ├── services/  # 业务逻辑
│   │   ├── database/  # ORM 模型
│   │   └── data/      # 规则 JSON 文件
│   └── docs/          # ★ 数据文档（必读）
└── src/               # Vue 3 前端
```

### ★ 必读文档（按优先级）

| 文档 | 路径 | 说明 |
|------|------|------|
| **规则-文书类型映射清单** | `backend/docs/规则-文书类型映射清单.md` | 179 条规则与 25 种文书类型的精确映射，**这是重构的核心参考** |
| **数据对接总览** | `backend/docs/data_integration.md` | 57 个接口对接状态、三层取数架构、API 清单 |
| **CDM 字段清单** | `backend/docs/cdm_field_list.csv` | 57 个接口的 2530 个字段完整定义（CSV 格式） |
| **DHC 接口清单** | `backend/docs/dhc_interface_tables.md` | 存储过程名称、参数、分批信息 |
| **规则分析** | `backend/rules_analysis.txt` | 179 条规则的原始分组和中文描述 |
| **MedQC workflow** | `.agents/workflows/medqc.md` | 项目规则和约定 |

---

## 二、现有质控架构

### 规则数据源

| 文件 | 说明 | 规则数 |
|------|------|--------|
| `app/data/sichuan_rules_146.json` | 四川省质控规则（SC-xxx） | 146 条（实际启用 68 条） |
| `app/data/custom_rules_33.json` | 泸县自定义规则（LX-xxx） | 33 条 |
| Supabase `qc_rules` 表 | 云端规则管理（CRUD） | 动态 |

### 核心代码文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `app/services/sichuan_qc_service.py` | 1198 | **主服务**：加载规则、调用 LLM、执行批量质控 |
| `app/services/qc_prompt_builder.py` | 479 | Prompt 构建器：提取检查要点、时间预计算、智能截断 |
| `app/services/unified_rule_engine.py` | 426 | 统一规则引擎：适用性检查、LLM 调用、结果解析 |
| `app/services/rule_router.py` | — | 规则路由：按文书类型分发规则 |
| `app/routers/semantic_rules.py` | 807 | API 路由：规则 CRUD、执行、导入导出 |
| `app/routers/department_qc_rules.py` | — | 科室专属规则 API |

### 执行流程

```
用户选择患者 → 前端请求质控 → SichuanQCService
  1. 加载 JSON 规则 → 按文书类型筛选适用规则
  2. 从数据库读取病历内容（record_content 字段）
  3. QCPromptBuilder 构建 Prompt（检查要点 + 截断内容）
  4. 调用 LLM（通过 UnifiedRuleEngine）
  5. 解析结果 → 返回 pass/fail + 证据 + 建议
```

### 已知问题（需要重构解决）

1. **文书类型映射粗糙**：`semantic_rules.py` 中的 `_RULE_DOCUMENT_MAPPING` 只有部分规则的手动映射（约 20 条），其余规则靠名称关键词推断
2. **规则与文书的对应不精确**：很多规则标注了 `inpatient/outpatient/emergency`（就诊类型），而非具体文书类型（入院记录/病程记录等）
3. **ORM 模型精简**：大部分病程记录类表只建了 `record_content` 字段，缺少结构化字段（CDM 有 30-50 个字段/表）
4. **未对接的 40 个接口**：57 个中只有 17 个建了 ORM，质控规则引用的文书类型中有些（如疑难讨论、死亡讨论、交接班、阶段小结等）CDM 表尚未建立

---

## 三、重构目标

### 3.1 规则-文书类型精确映射

**当前状态**：规则存储的 `applicable_documents` 多数为 `["inpatient", "outpatient", "emergency"]`

**目标**：每条规则精确对应到具体文书类型，参考 `规则-文书类型映射清单.md`

**实施建议**：
- 更新 `sichuan_rules_146.json` 中每条规则的 `applicable_documents` 字段
- 将 `semantic_rules.py` 中的 `_RULE_DOCUMENT_MAPPING` 替换为完整的 179 条映射
- 同步更新 Supabase 云端的 `qc_rules` 表

### 3.2 补充缺失的 ORM 模型

**当前已建 ORM（17 张 CDM 表，在 `app/database/models/cdm.py`）**，但质控规则涉及的文书类型还需要：

| 需要的文书类型 | 对应存储过程 | 是否已建 ORM |
|-------------|------------|-----------|
| 疑难病例讨论记录 | `web.diffcase_discussion_record` | ❌ |
| 死亡病例讨论记录 | `web.death_discussion` | ❌ |
| 死亡记录 | `web.death_record` | ❌ |
| 交班记录 | `web.handoff_record` | ❌ |
| 接班记录 | `web.handover_record` | ❌ |
| 阶段小结 | `web.summary_record` | ❌ |
| 术前小结 | `web.presurg_summary` | ❌ |
| 术前讨论 | `web.presurg_discussion` | ❌ |
| 手术安全核查 | `web.surgery_safecheck_record` | ❌ |
| 手术风险评估 | `web.surgery_risk_assessment` | ❌ |
| 麻醉记录 | `web.anesthesia_record` | ❌ |
| 新生儿记录 | `web.newborn_record` | ❌ |
| 输血记录 | `web.bloodtrans_record` | ❌ |
| 护理记录 | `web.nursing_record` | ❌ |

**实施建议**：
- 查阅 `cdm_field_list.csv` 获取每张表的完整字段定义
- 参考 `cdm.py` 中已有的 Mixin 模式（`AuditMixin`, `DocumentMixin`, `PatientBasicMixin`）
- 对于病程类文书，关键字段是 `record_content`（非结构化全文），结构化字段可后续按需扩展

### 3.3 优化规则引擎

**当前问题**：
- `UnifiedRuleEngine` 只有 LX-003 的专用规则（硬编码），其余全走 LLM
- 适用性检查 `ApplicabilityChecker` 只有年龄判断，缺少文书类型、手术标志等判断

**目标**：
- 为更多可用代码判断的规则（如时间性规则 SC-002/SC-022/SC-096 等）添加代码预判逻辑
- 增强适用性检查：例如手术相关规则只对有手术的患者触发

---

## 四、关键数据结构

### 规则 JSON 格式（`sichuan_rules_146.json`）

```json
{
  "rule_id": "SC-001",
  "rule_name": "无入院记录检查",
  "category": "admission_record",
  "severity": "critical",
  "applicable_documents": ["inpatient"],  // ← 需要改为具体文书类型
  "custom_prompt": "...",  // LLM 的检查指令
  "check_points": ["..."],
  "is_enabled": true
}
```

### 病历数据格式（传给质控引擎的）

```python
medical_record = {
    "visit_id": "...",
    "document_type": "入院记录",  # 文书类型
    "content": "...",             # record_content 全文
    "metadata": {                 # 结构化信息
        "admission_datetime": "...",
        "discharge_datetime": "...",
        "diagnosis": [...]
    }
}
```

---

## 五、建议的重构步骤

### Phase 1：数据层（补充 ORM 模型）
1. 在 `cdm.py` 中为缺失的 14 张表添加 ORM 模型
2. 运行数据库迁移
3. 验证 ETL 同步能正常导入数据

### Phase 2：规则映射（精确化）
1. 更新 `sichuan_rules_146.json` 的 `applicable_documents` 字段
2. 更新 `custom_rules_33.json` 的 `applicable_documents` 字段
3. 完善 `semantic_rules.py` 中的 `_RULE_DOCUMENT_MAPPING`
4. 同步更新 Supabase `qc_rules` 表

### Phase 3：引擎优化
1. 增强 `ApplicabilityChecker`：按文书类型、手术标志等预判
2. 在 `QCPromptBuilder` 中针对不同文书类型使用不同的 Prompt 模板
3. 为时间性规则扩展 `precompute_time_facts`

### Phase 4：前端适配
1. 前端质控面板按文书类型分组展示规则
2. V4 工作站的文书预览与质控结果联动

---

## 六、注意事项

1. **先读后改**：改代码前先通读 `sichuan_qc_service.py` 和 `qc_prompt_builder.py`，理解现有流程
2. **保持兼容**：`rules_analysis.txt` 中的规则分组是**权威来源**，务必以它为准
3. **渐进式**：先完成 Phase 1-2（数据+映射），再做 Phase 3-4（引擎+前端）
4. **测试**：每完成一个 Phase 后用 `backend/tests/` 中的测试验证不破坏现有功能
5. **提交规范**：commit message 使用中文，每个功能点单独提交
