# LX-008 优化实施指南

**目标**：修复 LX-008 串行模式的误判问题  
**预期效果**：串行和快速模式一致性从 77.78% 提升到 95%+

---

## 🚀 快速开始（推荐方案）

### 方案 1：优化提示词（5 分钟实施）

这是最简单、最快速的优化方案，预期可以解决 60-80% 的误判问题。

#### 步骤 1：备份当前配置

```bash
cd /home/ubuntu/coding/health-qc-monorepo
cp apps/medqc-web/backend/app/data/custom_rules_33.json \
   apps/medqc-web/backend/app/data/custom_rules_33.json.backup
```

#### 步骤 2：替换 LX-008 的提示词

打开 `apps/medqc-web/backend/app/data/custom_rules_33.json`，找到 LX-008 规则（第 101-113 行），将 `custom_prompt` 字段替换为 `docs/LX-008_OPTIMIZED_PROMPT.txt` 中的内容。

**关键改进点**：
- ✅ 明确的三步法检查流程
- ✅ 名称匹配规则（"胸部CT" = "胸部CT平扫"）
- ✅ 正面示例（合规病历的判定方法）
- ✅ 倾向性指导（不确定时倾向于合规）

#### 步骤 3：重启后端

```bash
# 停止旧进程
pkill -f "uvicorn app.main:app"

# 启动新进程
cd apps/medqc-web/backend
source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/qc-backend.log 2>&1 &

# 验证启动成功
sleep 3
curl -s http://127.0.0.1:8000/api/v1/health | jq .
```

#### 步骤 4：运行对比测试

```bash
cd /home/ubuntu/coding/health-qc-monorepo/apps/medqc-web
python3 scripts/compare_qc_results.py \
  --base-url http://127.0.0.1:8000 \
  --rules LX-008
```

#### 步骤 5：验证结果

检查 LX-008 是否判定为 `compliant`：

```bash
python3 -c "
import json
with open('qc_results_compare_report.json', 'r') as f:
    data = json.load(f)
seq = {r['rule_id']: r for r in data['sequential']['results']}
opt = {r['rule_id']: r for r in data['optimized']['results']}

print('LX-008 验证结果：')
print(f\"串行状态: {seq['LX-008']['status']}\")
print(f\"快速状态: {opt['LX-008']['status']}\")
print(f\"\\n一致性: {'✅ 通过' if seq['LX-008']['status'] == opt['LX-008']['status'] else '❌ 失败'}\")
"
```

**预期结果**：
- 串行状态：`compliant`
- 快速状态：`compliant`
- 一致性：✅ 通过

---

## 🔧 进阶方案（如果方案 1 不够）

### 方案 2：增加后处理验证（30 分钟实施）

如果方案 1 仍然有误判，可以增加后处理验证逻辑。

#### 步骤 1：在 unified_rule_engine.py 中增加后处理方法

在 `apps/medqc-web/backend/app/services/unified_rule_engine.py` 文件末尾（第 296 行之后）增加以下方法：

```python
def _post_process_lx008(
    self, 
    parsed: Dict[str, Any], 
    medical_text: str
) -> Dict[str, Any]:
    """
    LX-008 专用后处理：验证 issues 中提到的"缺失检查"是否真的缺失
    
    策略：
    1. 提取 issues 中提到的检查项目名称
    2. 在病历的辅助检查章节中查找相似名称
    3. 如果找到，则过滤掉该 issue
    4. 如果所有 issues 都被过滤，改为合规
    """
    issues = parsed.get("issues", [])
    if not issues:
        return parsed
    
    # 提取辅助检查章节
    auxiliary_section = self._extract_auxiliary_section(medical_text)
    if not auxiliary_section:
        # 如果没有辅助检查章节，保持原判定
        return parsed
    
    verified_issues = []
    for issue in issues:
        description = issue.get("description", "")
        
        # 提取检查项目名称（如："胸部CT未记录结果" -> "胸部CT"）
        exam_name = self._extract_exam_name(description)
        if not exam_name:
            # 无法提取检查名称，保留该 issue
            verified_issues.append(issue)
            continue
        
        # 在辅助检查章节中查找相似名称
        if self._find_similar_exam(exam_name, auxiliary_section):
            # 找到了相似检查，说明 LLM 误判，过滤掉该 issue
            continue
        else:
            # 确实没找到，保留该 issue
            verified_issues.append(issue)
    
    # 更新结果
    if not verified_issues:
        # 所有 issues 都被过滤掉，改为合规
        parsed["is_compliant"] = True
        parsed["issues"] = []
        parsed["findings"] = "经后处理验证，现病史提到的检查在辅助检查中均有记录。"
        parsed["confidence"] = min(parsed.get("confidence", 0.7), 0.75)
    else:
        # 仍有未解决的 issues
        parsed["issues"] = verified_issues
    
    return parsed

def _extract_auxiliary_section(self, medical_text: str) -> str:
    """提取辅助检查章节"""
    import re
    
    # 查找"辅助检查"标题
    patterns = [
        r"辅助检查[：:](.*?)(?=\n\n[一二三四五六七八九十]+[、\.]|\n\n[A-Z]|$)",
        r"辅助检查[：:](.*?)(?=入院诊断|初步诊断|$)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, medical_text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return ""

def _extract_exam_name(self, description: str) -> str:
    """
    从问题描述中提取检查项目名称
    
    示例：
    - "胸部CT未记录结果" -> "胸部CT"
    - "血常规未记录结果" -> "血常规"
    - "肝功能缺失" -> "肝功能"
    """
    # 移除常见的后缀
    suffixes = ["未记录结果", "未记录", "缺失", "缺少", "未见", "待结果"]
    exam_name = description
    for suffix in suffixes:
        exam_name = exam_name.replace(suffix, "")
    
    return exam_name.strip()

def _find_similar_exam(self, exam_name: str, auxiliary_section: str) -> bool:
    """
    在辅助检查章节中查找相似的检查名称
    
    匹配规则：
    - "胸部CT" 匹配 "胸部CT平扫"、"胸部CT增强"等
    - "血常规" 匹配 "血常规检查"、"血常规："等
    - 使用模糊匹配，只要主体名称相同即可
    """
    # 标准化检查名称（移除空格、标点）
    normalized_exam = exam_name.replace(" ", "").replace("　", "")
    normalized_section = auxiliary_section.replace(" ", "").replace("　", "")
    
    # 直接包含匹配
    if normalized_exam in normalized_section:
        return True
    
    # 同义词匹配
    synonyms = {
        "胸部CT": ["胸部CT平扫", "胸部CT增强", "胸部计算机断层扫描", "胸部电子计算机断层扫描"],
        "血常规": ["血常规检查", "血液常规", "血细胞分析"],
        "肝功能": ["肝功能检查", "肝功能测定"],
        "肾功能": ["肾功能检查", "肾功能测定"],
        "心电图": ["心电图检查", "ECG", "EKG"],
    }
    
    if exam_name in synonyms:
        for synonym in synonyms[exam_name]:
            if synonym.replace(" ", "") in normalized_section:
                return True
    
    return False
```

#### 步骤 2：在 evaluate() 方法中调用后处理

在 `evaluate()` 方法中，找到第 182 行（`parsed = self._parse_llm_response(raw_output)`），在其后增加：

```python
parsed = self._parse_llm_response(raw_output)

# LX-008 专用后处理：验证 issues 的真实性
if rule_id == "LX-008" and not parsed.get("is_compliant"):
    parsed = self._post_process_lx008(parsed, medical_record["content"])

evidence_info = self._evidence_verifier.verify(
    parsed.get("evidence", ""),
    medical_record["content"]
)
```

#### 步骤 3：重启后端并测试

```bash
# 重启后端
pkill -f "uvicorn app.main:app"
cd apps/medqc-web/backend
source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/qc-backend.log 2>&1 &

# 运行测试
cd /home/ubuntu/coding/health-qc-monorepo/apps/medqc-web
python3 scripts/compare_qc_results.py \
  --base-url http://127.0.0.1:8000 \
  --rules LX-008
```

---

## 📊 验证标准

### 成功标准

运行对比测试后，LX-008 应满足：

1. **状态一致**：
   - 串行状态：`compliant`
   - 快速状态：`compliant`

2. **无误报**：
   - 串行模式的 `issues` 数组应为空：`[]`
   - 不应出现"胸部CT未记录结果"、"血常规未记录结果"等误报

3. **证据真实**：
   - `evidence` 字段应引用真实的病历原文
   - 不应出现幻觉内容（如"待回报"）

4. **合规率一致**：
   - 串行和快速模式的合规率差异应 < 5%

### 验证命令

```bash
cd /home/ubuntu/coding/health-qc-monorepo/apps/medqc-web

# 查看 LX-008 详细结果
python3 -c "
import json
with open('qc_results_compare_report.json', 'r') as f:
    data = json.load(f)

seq = {r['rule_id']: r for r in data['sequential']['results']}
opt = {r['rule_id']: r for r in data['optimized']['results']}

print('=' * 80)
print('LX-008 验证结果')
print('=' * 80)
print(f\"\\n串行状态: {seq['LX-008']['status']}\")
print(f\"快速状态: {opt['LX-008']['status']}\")
print(f\"\\n串行 issues: {seq['LX-008'].get('issues', [])}\")
print(f\"快速 issues: {opt['LX-008'].get('issues', [])}\")
print(f\"\\n串行 findings: {seq['LX-008']['findings'][:150]}...\")
print(f\"快速 findings: {opt['LX-008']['findings'][:150]}...\")
print(f\"\\n一致性: {'✅ 通过' if seq['LX-008']['status'] == opt['LX-008']['status'] else '❌ 失败'}\")
"
```

---

## 🐛 调试技巧

### 查看 LLM 原始输出

如果仍然有问题，查看 LLM 的原始输出来分析思考过程：

```bash
python3 -c "
import json
with open('qc_results_compare_report.json', 'r') as f:
    data = json.load(f)
seq = {r['rule_id']: r for r in data['sequential']['results']}
print('LX-008 LLM 原始输出：')
print('=' * 80)
print(seq['LX-008'].get('llm_raw_output', ''))
"
```

### 测试单个规则

```bash
curl -X POST http://127.0.0.1:8000/api/v1/qc/sichuan/test-rule \
  -H "Content-Type: application/json" \
  -d @- <<'EOF' | jq .
{
  "rule_id": "LX-008",
  "medical_text": "患者信息：张伟，男，44岁，入院科室：呼吸与危重症医学科，病区：呼吸内一科。\n\n主诉：体检发现肺部结节1周。\n\n现病史：患者1周前单位组织体检，行胸部CT发现右肺下叶磨玻璃结节，直径约1.8cm，边界清晰。患者无咳嗽、咳痰、咯血、胸痛、气促等不适。为进一步诊治来我院就诊，门诊完善相关检查后以'右肺占位性病变'收入院。\n\n辅助检查：\n1. 血常规：WBC 8.6×10⁹/L，N 72%，Hb 135g/L，PLT 210×10⁹/L\n2. 肝功能：ALT 38U/L，AST 42U/L，TBIL 16μmol/L，ALB 41g/L\n3. 肾功能：Cr 78μmol/L，BUN 5.2mmol/L\n4. 心电图：窦性心律，大致正常心电图\n5. 胸部CT平扫（2024-10-25，外院）：右肺下叶见直径约1.8cm磨玻璃结节，边界清晰，无毛刺征，未见明显淋巴结肿大\n6. 腹部超声：肝胆胰脾未见明显异常，双肾未见结石及积水\n7. 空腹血糖：5.9mmol/L\n8. 凝血功能：PT 12.3s，APTT 31.5s，FIB 3.8g/L\n\n入院诊断：右肺占位性病变",
  "use_positive_example": false
}
EOF
```

### 查看后端日志

```bash
tail -f /tmp/qc-backend.log
```

---

## 📈 预期效果对比

### 优化前（当前状态）

| 指标 | 串行模式 | 快速模式 | 差异 |
|------|---------|---------|------|
| LX-008 状态 | non_compliant | compliant | ❌ 不一致 |
| LX-008 issues | 2 个误报 | 0 个 | ❌ 差异 |
| 合规率 | 33.33% | 66.67% | ❌ 差异 33.34% |

### 优化后（方案 1）

| 指标 | 串行模式 | 快速模式 | 差异 |
|------|---------|---------|------|
| LX-008 状态 | compliant | compliant | ✅ 一致 |
| LX-008 issues | 0 个 | 0 个 | ✅ 一致 |
| 合规率 | 55-60% | 66.67% | ⚠️ 差异 5-10% |

### 优化后（方案 1 + 方案 2）

| 指标 | 串行模式 | 快速模式 | 差异 |
|------|---------|---------|------|
| LX-008 状态 | compliant | compliant | ✅ 一致 |
| LX-008 issues | 0 个 | 0 个 | ✅ 一致 |
| 合规率 | 63-67% | 66.67% | ✅ 差异 < 5% |

---

## ✅ 实施检查清单

### 方案 1（优化提示词）

- [ ] 备份 `custom_rules_33.json`
- [ ] 替换 LX-008 的 `custom_prompt`
- [ ] 重启后端服务
- [ ] 运行对比测试
- [ ] 验证 LX-008 状态为 `compliant`
- [ ] 验证 issues 数组为空
- [ ] 验证证据无幻觉内容
- [ ] 记录优化效果

### 方案 2（增加后处理）

- [ ] 在 `unified_rule_engine.py` 中增加 4 个方法
- [ ] 在 `evaluate()` 方法中调用后处理
- [ ] 重启后端服务
- [ ] 运行对比测试
- [ ] 验证后处理是否正确过滤误报
- [ ] 验证合规率差异 < 5%
- [ ] 记录优化效果

---

## 📚 相关文档

- **优化方案详细说明**：`docs/LX-008_OPTIMIZATION_PROPOSAL.md`
- **优化后的提示词**：`docs/LX-008_OPTIMIZED_PROMPT.txt`
- **验证报告**：`docs/QC_FIX_VERIFICATION_REPORT.md`
- **任务总结**：`VERIFICATION_SUMMARY.md`

---

**文档版本**：1.0  
**创建日期**：2024-11-08  
**预计实施时间**：方案 1（5 分钟）+ 方案 2（30 分钟）

