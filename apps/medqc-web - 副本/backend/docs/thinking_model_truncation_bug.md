# Thinking 模型 JSON 输出截断问题 — Debug 说明

> 供 Codex 排查和修复。项目根目录：`apps/medqc-web/backend/`

---

## 问题概述

使用 `qwen3.5-35b-a3b`（Qwen 3.5 Thinking 模型）进行病历质控时，**当规则数量较多（≥40条）时，LLM 输出被严重截断（仅 8 个字符），导致 JSON 解析失败**，系统降级为"全部不合规"（2.27%）。规则数量较少（≤20条）时正常（100%）。

## 复现方式

```bash
cd apps/medqc-web/backend
PYTHONUNBUFFERED=1 python -c "
import sys, asyncio
sys.path.insert(0, '.')
from app.services.sichuan_qc_service import SichuanQCService

async def test():
    s = SichuanQCService()
    s.client.model = 'qwen3.5-35b-a3b'
    
    # 场景1：44条规则 → 输出截断
    rules = list(await s._load_applicable_rules('入院记录'))
    print(f'规则数: {len(rules)}')  # 44
    prompt = await s._build_prompt(rules, '入院记录\n主诉：胸闷3年', '入院记录')
    print(f'Prompt 长度: {len(prompt)}')  # ~14804 字符
    raw = await s.client.generate(prompt)
    print(f'输出长度: {len(raw)}')  # 仅 8 字符！
    
    # 场景2：20条规则 → 正常
    rules2 = list(await s._load_applicable_rules('手术记录'))
    print(f'规则数: {len(rules2)}')  # 20
    prompt2 = await s._build_prompt(rules2, '手术记录内容...', '手术记录')
    raw2 = await s.client.generate(prompt2)
    print(f'输出长度: {len(raw2)}')  # 正常（数千字符）

asyncio.run(test())
"
```

## 根因分析

### 1. `max_tokens = 4000` 对 Thinking 模型严重不足

- 文件：[qc_llm_client.py](file:///d:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/services/qc_llm_client.py)
- 第 41 行和第 56 行：`self.max_tokens: int = 4000`
- 第 91 行：API 调用时传入 `"max_tokens": self.max_tokens`

**问题**：Qwen 3.5 系列是 Thinking 模型，输出会先生成 `<think>...</think>` 思考过程，然后才是实际 JSON。`<think>` 内容也算入 `max_tokens`。44 条规则的思考过程可能消耗 3500+ token，留给 JSON 输出的 token 几乎为零 → 截断。

### 2. `generate()` 方法返回值需要检查

- 文件：[qc_llm_client.py](file:///d:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/services/qc_llm_client.py)
- `generate()` 方法（约第 67 行）

需要确认：
- 返回值是否已剥离 `<think>` 标签？（从测试结果看 `Has think: False` 且 `length: 8`，说明可能剥离了 think 但剩余内容极短）
- `finish_reason` 是否为 `length`（达到 max_tokens 限制）？目前未检查此字段

### 3. `_parse_llm_json_response` 的降级逻辑不合理

- 文件：[sichuan_qc_service.py](file:///d:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/services/sichuan_qc_service.py)
- `_parse_llm_json_response` 方法（约第 262 行）
- 当 JSON 解析失败时调用 `_create_fallback_results`，该方法将所有规则标记为 `is_compliant: False`（看得到 2.27% 的结果 = 43/44 不合规）

## 期望的修复方案

### 方案 A：增大 max_tokens + 剥离 think 标签（快速修复）

1. **`qc_llm_client.py`**：
   - 将 `max_tokens` 默认值从 `4000` 提高到 `16384`（或根据规则数量动态计算）
   - 在 `generate()` 方法中检查 `finish_reason == "length"`，如果截断则记录 warning
   - 确保返回值中已剥离 `<think>...</think>` 标签

2. **`sichuan_qc_service.py`**：
   - 在 `_parse_llm_json_response` 入口处用正则 `re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)` 清理 think 标签（双重保险）

### 方案 B：分批评估（根本解决）

- `evaluate_document_fast` 目前将所有规则一次性发给 LLM
- 当规则数 > 15 时，应分批（每批 10-15 条）并行调用 LLM，然后合并结果
- 参考已有的 `SegmentedQCPipeline`（`app/services/segmented_qc_pipeline.py`），它已实现了分段+并发的逻辑

### 方案 C：API 参数禁用 thinking（最简单但损失思考能力）

- 在 API 调用中添加参数 `"enable_thinking": false`（如果 dashscope API 支持）
- 这样 `<think>` 标签不会生成，max_tokens 全部用于实际输出

## A/B 评测数据佐证

### qwen-turbo（非 thinking 模型，max_tokens=4000 够用）

| 文书类型 | 规则数 | current | plan_a | plan_c |
|---------|-------|---------|--------|--------|
| 入院记录 | 44 | 2.3% | 2.3% | 2.3% |
| 手术记录 | 20 | 85.0% | 95.0% | 95.0% |

> 入院记录结果差是因为 qwen-turbo 模型能力弱，不是截断问题

### qwen3.5-35b-a3b（thinking 模型，max_tokens=4000 不够）

| 文书类型 | 规则数 | current | plan_a | plan_c | JSON 解析 |
|---------|-------|---------|--------|--------|----------|
| 入院记录 | 44 | 2.3% | 2.3% | 2.3% | ❌ 全部失败（输出仅 8 字符）|
| 手术记录 | 20 | 100% | 100% | 100% | ✅ 全部成功 |

## 涉及文件

| 文件 | 关注点 |
|------|-------|
| `app/services/qc_llm_client.py` | `max_tokens` 默认值、`generate()` 方法、think 标签处理 |
| `app/services/sichuan_qc_service.py` | `_parse_llm_json_response`、`_create_fallback_results`、`evaluate_document_fast` |
| `app/services/segmented_qc_pipeline.py` | 已有的分批评估逻辑（可参考） |
| `app/services/qc_prompt_builder.py` | `build_prompt()`（Prompt 组装） |

## 验证标准

修复后运行以下命令，入院记录（44 条规则）应正常输出 JSON 并合规率 > 50%：

```bash
PYTHONUNBUFFERED=1 python -c "
import sys, asyncio
sys.path.insert(0, '.')
from app.services.sichuan_qc_service import SichuanQCService

async def test():
    s = SichuanQCService()
    s.client.model = 'qwen3.5-35b-a3b'
    result = await s.evaluate_document_fast(
        document_id='test-001',
        content='入院记录\n主诉：胸闷3年\n现病史：略\n体检：略\n诊断：心衰',
        document_type='入院记录',
    )
    summary = result.get('evaluation_summary', {})
    print(f'合规率: {summary.get(\"compliance_rate\")}%')
    print(f'总规则: {summary.get(\"total_rules\")}')
    print(f'问题数: {summary.get(\"issues_found\")}')
    # 不应该是 2.27%（降级结果）
    assert summary.get('compliance_rate', 0) > 5, '合规率不应为降级默认值'

asyncio.run(test())
"
```
