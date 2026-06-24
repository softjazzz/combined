# 质控规则重构 — Codex Review 文档

> 本文档描述了质控引擎规则部分的完整重构，包含所有修改文件、设计决策和潜在风险点，供 Codex 做代码审查和调试。

---

## 一、变更概览

| Commit | 文件变更 | 说明 |
|--------|---------|------|
| `3d0c9c94` | 6 files, +703/-211 | Phase 1+2：14 个 ORM 模型 + 179 条规则文书映射 |
| `ee546f69` | 1 file, +396/-315 | 测试迁移：Supabase mock → SQLAlchemy + SQLite in-memory |
| `2d5432e3` | 1 file, +89/-10 | Phase 3：ApplicabilityChecker 增强 |
| `6895bbae` | 3 files, +684/-10 | 前端选择器 + TIME_RULES + ETL 同步配置 |

---

## 二、修改文件清单与代码说明

### 2.1 ORM 模型层

**文件**: `app/database/models/cdm.py`  
**变更**: 新增 14 个 ORM 类（第 609-778 行）

```python
# 新增的 14 个模型（均继承 Base，使用 AuditMixin + DocumentMixin + PatientBasicMixin）
class DiffcaseDiscussionRecord   # 疑难病例讨论记录
class DeathDiscussion             # 死亡病例讨论记录
class DeathRecord                 # 死亡记录
class HandoffRecord               # 交班记录
class HandoverRecord              # 接班记录
class SummaryRecord               # 阶段小结
class PresurgSummary              # 术前小结
class PresurgDiscussion           # 术前讨论
class SurgerySafecheckRecord      # 手术安全核查
class SurgeryRiskAssessment       # 手术风险评估
class AnesthesiaRecord            # 麻醉记录
class NewbornRecord               # 新生儿记录
class BloodtransRecord            # 输血记录
class NursingRecord               # 护理记录
```

**设计决策**: 
- 每个模型只有核心字段（三元主键 institute_id/patient_id/visit_id + document_id + record_content），与已有模型一致
- 这些表是**结构准备**，ETL 同步后才会有数据流入
- PG 数据库已成功创建对应的 34 张表

**Review 重点**:
- 检查主键定义是否与 DHC 远端一致（`cdm_field_list.csv` 可对照）
- 检查表名是否与存储过程名匹配（`dhc_interface_tables.md` 可对照）

---

### 2.2 规则 JSON 文件

**文件 1**: `app/data/sichuan_rules_146.json`（146 条 SC 规则）  
**文件 2**: `app/data/custom_rules_33.json`（33 条 LX 规则 + 56 条 LXE 规则）

**变更**: 更新所有规则的 `applicable_documents` 字段

```diff
 # 变更前（粗粒度）
-"applicable_documents": ["inpatient"]
 
 # 变更后（精确文书类型，使用英文标识）
+"applicable_documents": ["admission_record"]
```

**映射参考**: `docs/规则-文书类型映射清单.md`

**具体映射示例**:

| 规则范围 | applicable_documents | 中文 |
|---------|---------------------|------|
| SC-001~020, LX-001~009 | `["admission_record"]` | 入院记录 |
| SC-021~027 | `["first_course_record"]` | 首次病程记录 |
| SC-028~047, LX-010~014 | `["daily_course_record"]` | 日常病程记录 |
| SC-095~115, LX-025~028 | `["surgery_record"]` 等 | 手术相关 |
| SC-116~127, LX-029 | `["discharge_record"]` | 出院记录 |

**Review 重点**:
- **LXE 规则未修改**（56 条），因为它们不在原始映射清单中
- 每条规则的 `applicable_documents` 是否与 `规则-文书类型映射清单.md` 一致
- 是否有规则遗漏或错误映射

---

### 2.3 规则路由 — rule_router.py

**文件**: `app/services/rule_router.py`  
**变更**: 第 14-66 行 `SECTION_TO_RULE_TYPES` 映射 + 第 107-115 行 `_load_rules` 方法

**核心逻辑**:

```python
# 精确文书类型 → 规则类型映射（用于按 section 加载规则）
SECTION_TO_RULE_TYPES = {
    "admission_record": ["admission_record"],
    "first_course_record": ["first_course_record"],
    "daily_course_record": ["daily_course_record"],
    # ... 30+ 个精确类型
    
    # ⚠️ 旧类型兼容入口（前端可能传 "progress_note"）
    "progress_note": [
        "first_course_record", "daily_course_record",
        "senior_course_record", "rescue_record"
    ],
    "operation_record": [
        "surgery_record", "presurg_summary", "presurg_discussion",
        "anesthesia_record", ...
    ],
}
```

**_load_rules 方法变更**: 从仅加载 `sichuan_rules_146.json` 改为同时加载 `sichuan_rules_146.json` + `custom_rules_33.json`。

**Review 重点**:
- `progress_note` / `operation_record` 等旧类型的展开列表是否完整
- 前端传来的中文文书类型 → 英文标识的转换链路是否正确

---

### 2.4 质控服务 — sichuan_qc_service.py

**文件**: `app/services/sichuan_qc_service.py`  
**变更**: 三处修改

#### 2.4.1 doc_type_mapping 扩展（第 38-79 行）

```python
doc_type_mapping = {
    # 原有 5 个
    "admission_record": "入院记录",
    "progress_note": "病程记录",
    ...
    # 新增 23 个（与 ORM 模型一一对应）
    "first_course_record": "首次病程记录",
    "daily_course_record": "日常病程记录",
    "surgery_record": "手术记录",
    "presurg_summary": "术前小结",
    ...
}
```

**用途**: JSON 中的英文 `applicable_documents` → 中文的转换层。`_load_rules_from_json` 加载规则后，将英文标识翻译为中文，与前端传来的中文文书类型做匹配。

#### 2.4.2 _load_rules_from_json / _load_custom_rules_from_json（第 87-151 行）

加载规则后遍历 `applicable_documents`，通过 `doc_type_mapping` 翻译为中文。

#### 2.4.3 _load_rules_from_db（第 153-178 行）

合并加载两个 JSON 文件的规则，按 `document_type`（中文）做**精确匹配**筛选。

**Review 重点**:
- `doc_type_mapping` 是否覆盖了 JSON 中所有出现的英文标识
- 中文匹配逻辑：如果有规则的 `applicable_documents` 包含 `["入院记录", "出院记录"]`，传入 `document_type="入院记录"` 能否正确匹配
- `_load_rules_from_db` 方法名有误导性（实际从 JSON 加载而非数据库），是否需要重命名

---

### 2.5 语义规则 API — semantic_rules.py

**文件**: `app/routers/semantic_rules.py`  
**变更**: 第 680-830 行 `_RULE_DOCUMENT_MAPPING` 字典

从约 20 条手动映射扩展为完整 179 条，key 为规则 ID（如 `"SC-001"`），value 为中文文书类型列表。用于 API 返回时展示规则对应的文书类型。

**Review 重点**:
- 这个映射是否与 JSON 文件中的 `applicable_documents`（英文→中文转换后）一致
- 是否有重复或遗漏

---

### 2.6 统一规则引擎 — unified_rule_engine.py

**文件**: `app/services/unified_rule_engine.py`  
**变更**: 第 20-155 行 `ApplicabilityChecker` 类重写

**原有逻辑**: 仅有 LX-003/LX-005/LX-006 三条规则的年龄检查

**新增逻辑（按检查顺序）**:

```python
class ApplicabilityChecker:
    # 1. 文书类型匹配（新增）
    #    如果规则的 applicable_documents 非空 且 当前 document_type 不匹配 → 跳过
    #    支持中英文双向匹配（通过 _DOC_TYPE_CN_MAP）
    
    # 2. 手术标志检测（新增）
    #    36 条手术规则（SURGERY_ONLY_RULES 集合）
    #    13 个手术关键词（SURGERY_HINTS 列表）
    #    如果病历内容无手术特征 → 跳过
    
    # 3. 年龄/规则特定逻辑（保留不变）
    #    LX-003: 交给 LLM
    #    LX-005: 交给 LLM
    #    LX-006: 年龄 <7 或 >=18 → 跳过
```

**Review 重点**:
- `_DOC_TYPE_CN_MAP` 是否与 `sichuan_qc_service.py` 中的 `doc_type_mapping` 保持一致（两处维护同一份映射，存在重复风险）
- `SURGERY_ONLY_RULES` 集合是否完整，是否有非手术规则被误加入
- `SURGERY_HINTS` 关键词是否存在误判风险（如"移植"在器官移植 vs 皮瓣移植场景）
- `_match_document_type` 的三重匹配逻辑是否有边界情况遗漏

---

### 2.7 Prompt 构建器 — qc_prompt_builder.py

**文件**: `app/services/qc_prompt_builder.py`  
**变更**: 第 214-302 行 `TIME_RULES` 字典

```python
TIME_RULES = {
    # 原有 5 条
    'SC-054': (抢救结束→记录完成, 6h),
    'SC-048': (入院→首次查房, 48h),
    'LX-017': (会诊申请→完成, 48h),
    'LX-026': (手术结束→记录, 24h),
    'LX-029': (出院→记录, 24h),
    
    # 新增 7 条
    'SC-002': (入院→入院记录书写, 24h),
    'SC-003': (入院→24h入出院记录, 24h),
    'SC-022': (入院→首次病程记录, 8h),
    'SC-062': (交班→交班记录, 24h),
    'SC-071': (会诊申请→会诊意见, 24h),
    'SC-096': (手术结束→手术记录, 24h),
    'SC-117': (出院/死亡→记录, 24h),
}
```

**工作原理**: 对每条规则，用正则在病历文本中搜索起始/结束标签附近的时间戳，精确计算间隔时长，注入到 Prompt 中让 LLM 直接采信，避免 LLM 做时间算术。

**Review 重点**:
- 起始/结束标签的正则是否能覆盖常见的病历书写格式
- 如果病历中有多个同名标签（如两次"入院时间"），`find_time_near_label` 只取第一个是否正确
- SC-022 和 SC-048 共用 `入院时间` 作为起始标签但限时不同（8h vs 48h），互不干扰

---

### 2.8 ETL 同步 — etl_sync.py

**文件**: `app/services/etl_sync.py`  
**变更**: 第 220-418 行 `SYNC_TABLES` 列表

从 5 张表扩展到 26 张表。

```python
SYNC_TABLES = [
    # 基础表 4 张: mr, diagnosis, mr_surgery, mr_cost
    # 入院/出院/死亡 3 张: admission_record, discharge_record, death_record
    # 病程记录 4 张: first_course, daily_course, senior_course, rescue
    # 讨论/会诊 3 张: diffcase_discussion, death_discussion, consultation
    # 交接班/小结 2 张: handoff, summary
    # 手术相关 7 张: surgery, presurg_summary/discussion, postsurg_firstcourse,
    #               surgery_safecheck, surgery_risk_assessment, anesthesia
    # 其他 3 张: newborn, bloodtrans, nursing
]
```

**Review 重点**:
- 存储过程名称 `web.表名` 是否与远端 DHC 数据库一致（需要 DBA 确认）
- `key_fields` 的选择：多文档类型用 `["patient_id", "visit_id", "document_id"]` 三元键，单文档类型用 `["patient_id", "visit_id"]` 二元键，是否正确
- `admission_record` 从原来的位置移到了"入院/出院/死亡"分组，功能不变

---

### 2.9 前端 — SichuanQCView.vue

**文件**: `src/views/qc/SichuanQCView.vue`  
**变更**: 第 118-155 行选择器 + 第 450 行默认值

```vue
<!-- 变更前：3 个 option -->
<a-select v-model:value="documentType">
  <a-select-option value="病程记录">病程记录</a-select-option>
  <a-select-option value="入院记录">入院记录</a-select-option>
  <a-select-option value="出院记录">出院记录</a-select-option>
</a-select>

<!-- 变更后：28 个 option，分 5 组，支持搜索 -->
<a-select v-model:value="documentType" show-search>
  <a-select-opt-group label="入院/出院">...</a-select-opt-group>
  <a-select-opt-group label="病程记录">...</a-select-opt-group>
  <a-select-opt-group label="讨论/会诊">...</a-select-opt-group>
  <a-select-opt-group label="手术相关">...</a-select-opt-group>
  <a-select-opt-group label="其他文书">...</a-select-opt-group>
</a-select>
```

默认值从 `'病程记录'` 改为 `'入院记录'`。

**Review 重点**:
- 前端传递的中文文书类型字符串是否与后端 `doc_type_mapping` 的 value 完全一致
- "其他文书"组中有一个 `disabled style="display:none"` 的隐藏项"医嘱"需要清理

---

### 2.10 单元测试 — test_sichuan_qc_service.py

**文件**: `tests/unit/test_sichuan_qc_service.py`  
**变更**: 全部重写（396 行新代码）

```python
# 5 个测试类，24 个测试用例
TestRuleLoading          # 10 项：JSON 加载 + 按文书类型筛选
TestPromptBuilding       # 2 项：有/无规则时的 Prompt 构建
TestCDMDataAccess        # 4 项：SQLAlchemy 查询入院/首次病程/手术/出院记录
TestEvaluation           # 4 项：评估流程 + 合规率 + 指定规则
TestRuleRouter           # 4 项：路由器加载 + 旧类型兼容 + 精确类型 + 未知类型
```

**测试基础设施**:
- 使用 SQLite in-memory（`create_engine("sqlite:///:memory:")`）模拟 PG
- `seed_cdm_data` fixture 注入标准化测试数据（5 份文书）
- 规则加载测试直接读取真实 JSON 文件

**Review 重点**:
- `TestRuleLoading` 中的断言数字（如入院记录 29 条）是否与 JSON 文件实际匹配
- `TestEvaluation` 中 mock 的 `rule_engine.evaluate` 返回格式是否匹配实际引擎
- `seed_cdm_data` 的 SQLite INSERT 语句是否兼容 PG 语法

---

## 三、已知风险和待确认项

| # | 风险 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | doc_type_mapping **双重维护** | ⚠️ 中 | `sichuan_qc_service.py` 和 `unified_rule_engine.py` 各有一份相同的映射表 |
| 2 | `_load_rules_from_db` 方法名误导 | ⚠️ 低 | 实际从 JSON 加载，名字暗示数据库操作 |
| 3 | ETL 存储过程名 **未与 DBA 确认** | ⚠️ 中 | 26 张表的 `web.xxx` 存储过程是否已在远端创建 |
| 4 | SichuanQCView.vue **40+ TS lint 错误** | ⚠️ 低 | 预存的类型定义缺失（`ref<unknown>`），非本次引入 |
| 5 | TIME_RULES `sichuan_qc_service.py` 副本 **未同步** | ⚠️ 中 | `sichuan_qc_service.py:398` 有一份旧的 TIME_RULES，与 `qc_prompt_builder.py` 不一致 |

---

## 四、验证命令

```bash
# 运行单元测试
cd apps/medqc-web/backend
python -m pytest tests/unit/test_sichuan_qc_service.py -v

# 验证规则加载
python -c "from app.services.sichuan_qc_service import SichuanQCService; s=SichuanQCService(); import asyncio; r=asyncio.run(s._load_rules_from_db('入院记录')); print(len(r), 'rules')"

# 验证 ETL 配置
python -c "from app.services.etl_sync import SYNC_TABLES; print(len(SYNC_TABLES), 'tables')"

# 验证 ApplicabilityChecker
python -c "
from app.services.unified_rule_engine import ApplicabilityChecker
c = ApplicabilityChecker()
# 应返回 False（文书不匹配）
r = c.check({'rule_id':'SC-001','applicable_documents':['admission_record']}, {'content':'test','document_type':'手术记录'})
print('doc_type_guard:', not r.is_applicable)
# 应返回 False（无手术特征）
r = c.check({'rule_id':'SC-095','applicable_documents':['surgery_record']}, {'content':'普通病历','document_type':'手术记录'})
print('surgery_guard:', not r.is_applicable)
"
```
