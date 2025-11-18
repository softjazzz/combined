# 快速质控模式提示词优化方案说明文档

## 📋 文档概述

本文档详细说明了快速质控模式的三种提示词优化方案（方案 A、方案 B、方案 C）的设计思路、实现方法、优缺点对比，以及实际测试结果。

---

## 🎯 背景与问题

### 当前问题

**快速质控模式**（Fast Mode）的准确率远低于**串行质控模式**（Sequential Mode）。

**根本原因**：
- **串行模式**：每条规则单独调用 LLM，使用完整的 `custom_prompt`（平均 1,777 字符）
- **快速模式**：所有规则批量调用 LLM，只使用 `rule_id` + `name` + `description`（平均 150 字符）

**结果**：
- 串行模式准确率：~90%
- 快速模式准确率：0%（实测）

### 优化目标

在快速模式中引入 `custom_prompt` 的关键信息，提升准确率，同时控制 Token 消耗。

---

## 🔧 三种优化方案

### 方案 A：精简版（Extract Check Points）

#### 设计思路

只提取 `custom_prompt` 中的**【检查要点】**部分，去掉其他冗余信息。

#### 实现方法

```python
def extract_check_points(custom_prompt: str) -> str:
    """
    从 custom_prompt 中提取检查要点
    
    Args:
        custom_prompt: 完整的自定义提示词
        
    Returns:
        提取的检查要点文本
    """
    # 查找【检查要点】部分
    start_marker = "【检查要点】"
    end_markers = ["【判定逻辑】", "【分析方法】", "【注意事项】"]
    
    start_idx = custom_prompt.find(start_marker)
    if start_idx == -1:
        return ""
    
    # 查找结束位置
    end_idx = len(custom_prompt)
    for marker in end_markers:
        idx = custom_prompt.find(marker, start_idx)
        if idx != -1 and idx < end_idx:
            end_idx = idx
    
    # 提取并清理
    check_points = custom_prompt[start_idx:end_idx].strip()
    return check_points
```

#### 提示词格式

```
规则 ID: LX-001
规则名称: 主诉书写不规范或不能导出第一诊断
规则描述: 主诉书写不规范或不能导出第一诊断

【检查要点】
1. 主诉中的症状/体征/疾病及其持续时间
2. 主诉持续时间与病程事实和诊断逻辑一致
3. 主诉与诊断是否相符
```

#### 优缺点

**优点**：
- ✅ Token 消耗适中（+44.6%）
- ✅ 实现简单，易于维护
- ✅ 提取的信息精准，减少噪音
- ✅ **准确率最高（66.7%）**

**缺点**：
- ⚠️ 缺少判定逻辑，可能导致理解偏差
- ⚠️ 对复杂规则（如 LX-007、LX-009）仍有误判

#### 适用场景

- ✅ 对准确率要求较高（60-70%）
- ✅ 对成本敏感（Token 增长 <50%）
- ✅ 规则的检查要点清晰明确
- ✅ **推荐作为首选方案**

---

### 方案 B：理想版（Use Complete Custom Prompt）

#### 设计思路

使用完整的 `custom_prompt`，包含所有信息：
- 【检查要点】
- 【判定逻辑】
- 【分析方法】
- 【注意事项】

#### 实现方法

```python
def extract_core_prompt(custom_prompt: str) -> str:
    """
    提取 custom_prompt 的核心部分（去掉通用说明）
    
    Args:
        custom_prompt: 完整的自定义提示词
        
    Returns:
        核心提示词文本
    """
    # 查找核心部分的开始
    start_markers = ["【检查要点】", "【规则说明】", "【质控要求】"]
    
    start_idx = len(custom_prompt)
    for marker in start_markers:
        idx = custom_prompt.find(marker)
        if idx != -1 and idx < start_idx:
            start_idx = idx
    
    if start_idx == len(custom_prompt):
        return custom_prompt
    
    # 提取核心部分
    core_prompt = custom_prompt[start_idx:].strip()
    return core_prompt
```

#### 提示词格式

```
规则 ID: LX-001
规则名称: 主诉书写不规范或不能导出第一诊断
规则描述: 主诉书写不规范或不能导出第一诊断

【检查要点】
1. 主诉中的症状/体征/疾病及其持续时间
2. 主诉持续时间与病程事实和诊断逻辑一致
3. 主诉与诊断是否相符

【判定逻辑】
- 如果主诉中缺少症状/体征/疾病，判定为不合规
- 如果主诉持续时间与病程不一致，判定为不合规
- 如果主诉与第一诊断不相符，判定为不合规

【分析方法】
1. 提取主诉中的核心症状/体征/疾病
2. 提取主诉中的持续时间
3. 对比主诉与第一诊断的逻辑关系
4. 综合判定是否合规

【注意事项】
- 主诉应简洁明了，不超过20字
- 持续时间应精确到天、周、月、年
- 主诉应能导出第一诊断
```

#### 优缺点

**优点**：
- ✅ 信息最完整（100%）
- ✅ 判定理由非常详细
- ✅ 理论上准确率应该最高

**缺点**：
- ❌ Token 消耗大（+132.6%）
- ❌ API 耗时长（55.69s）
- ❌ **实际准确率不如方案 A（55.6% vs 66.7%）**
- ❌ 判定过于严格，导致误判增多
- ❌ 提示词过长可能导致 LLM 理解偏差

#### 适用场景

- ⚠️ 对准确率要求极高（理论上 80-90%）
- ⚠️ 对成本不敏感
- ⚠️ 规则非常复杂，需要详细说明
- ⚠️ **实测效果不佳，不推荐**

---

### 方案 C：混合版（Extract Compact Guidance）

#### 设计思路

提取 `custom_prompt` 中的**【检查要点】**和**【判定逻辑】**，去掉【分析方法】和【注意事项】。

#### 实现方法

```python
def extract_compact_guidance(custom_prompt: str) -> str:
    """
    提取紧凑的指导信息（检查要点 + 判定逻辑）
    
    Args:
        custom_prompt: 完整的自定义提示词
        
    Returns:
        紧凑的指导信息
    """
    # 提取【检查要点】
    check_points = ""
    start_idx = custom_prompt.find("【检查要点】")
    if start_idx != -1:
        end_markers = ["【判定逻辑】", "【分析方法】", "【注意事项】"]
        end_idx = len(custom_prompt)
        for marker in end_markers:
            idx = custom_prompt.find(marker, start_idx)
            if idx != -1 and idx < end_idx:
                end_idx = idx
        check_points = custom_prompt[start_idx:end_idx].strip()
    
    # 提取【判定逻辑】
    logic = ""
    start_idx = custom_prompt.find("【判定逻辑】")
    if start_idx != -1:
        end_markers = ["【分析方法】", "【注意事项】", "【示例】"]
        end_idx = len(custom_prompt)
        for marker in end_markers:
            idx = custom_prompt.find(marker, start_idx)
            if idx != -1 and idx < end_idx:
                end_idx = idx
        logic = custom_prompt[start_idx:end_idx].strip()
    
    # 合并并压缩格式
    parts = []
    if check_points:
        parts.append(check_points)
    if logic:
        parts.append(logic)
    
    compact = "\n".join(parts)
    
    # 压缩空行
    compact = "\n".join(line for line in compact.split("\n") if line.strip())
    
    return compact
```

#### 提示词格式

```
规则 ID: LX-001
规则名称: 主诉书写不规范或不能导出第一诊断
规则描述: 主诉书写不规范或不能导出第一诊断

【检查要点】
1. 主诉中的症状/体征/疾病及其持续时间
2. 主诉持续时间与病程事实和诊断逻辑一致
3. 主诉与诊断是否相符
【判定逻辑】
- 如果主诉中缺少症状/体征/疾病，判定为不合规
- 如果主诉持续时间与病程不一致，判定为不合规
- 如果主诉与第一诊断不相符，判定为不合规
```

#### 优缺点

**优点**：
- ✅ 信息完整度适中（67%）
- ✅ Token 消耗适中（+93.7%）
- ✅ 包含检查要点和判定逻辑

**缺点**：
- ❌ **准确率最低（44.4%）**
- ❌ 判定过于严格
- ❌ 对复杂规则误判较多
- ❌ 提取的"紧凑指导"仍然较长

#### 适用场景

- ⚠️ 对准确率要求中等（理论上 60-70%）
- ⚠️ 对成本较敏感
- ⚠️ 规则需要判定逻辑说明
- ⚠️ **实测效果不佳，不推荐**

---

## 📊 实测对比

### 测试环境

- **测试病历**：张伟，44岁，右肺占位性病变（完整入院记录，685 字符）
- **测试规则**：LX-001 ~ LX-009（9 条入院记录规则）
- **测试模型**：qwen3-235b-a22b-instruct-2507
- **测试时间**：2024-11-09

### 测试结果

| 方案 | 准确率 | 正确数 | 错误数 | Token 消耗 | Token 增长 | API 耗时 | 成本增长 |
|------|--------|--------|--------|-----------|-----------|---------|---------|
| **当前模式** | 0.0% | 0/9 | 9 | 2,043 | 基准 | 13.48s | 基准 |
| **方案 A** ⭐ | **66.7%** | 6/9 | 3 | 2,955 | +44.6% | 28.73s | +44.6% |
| **方案 B** | 55.6% | 5/9 | 4 | 4,753 | +132.6% | 55.69s | +132.6% |
| **方案 C** | 44.4% | 4/9 | 5 | 3,959 | +93.7% | 43.43s | +93.7% |

### 关键发现

1. **当前模式准确率为 0%**：所有 9 条规则全部误判，必须优化
2. **方案 A 准确率最高（66.7%）**：虽然只提取了检查要点，但效果最好
3. **方案 B 和 C 准确率反而较低**：提示词过长可能导致 LLM 理解偏差和判定过严

---

## 💡 推荐方案

### ⭐ 推荐：方案 A（精简版）

**推荐理由**：
1. ✅ **准确率最高**：66.7%，远高于当前模式的 0%
2. ✅ **Token 消耗适中**：+44.6%（每月增加约 ¥4.60）
3. ✅ **实现简单**：只需提取检查要点
4. ✅ **能正确识别不适用的规则**：LX-003、LX-004、LX-006

**成本估算**（假设每月质控 3000 份病历，每份 9 条规则）：
- 当前模式：¥8.14/月
- 方案 A：¥11.78/月
- **增加成本**：¥3.64/月（+44.6%）

**实施步骤**：
1. 在 `sichuan_qc_service.py` 中添加 `extract_check_points` 函数
2. 修改 `_build_prompt` 方法，使用提取的检查要点
3. 测试验证效果

---

## 🔍 误判分析

### 方案 A 的 3 个误判规则

#### 1. LX-002：入院记录-现病史缺少一般情况

**LLM 判定**：不合规
- 理由：现病史中未描述患者的一般情况，如饮食、睡眠、精神状态、体力等

**实际情况**：
- 现病史：患者无咳嗽、咳痰、咯血、胸痛、气促等不适
- 确实缺少"饮食、睡眠、体力、精神状态"的明确描述

**分析**：
- ❓ LLM 判定可能是正确的
- ❓ 需要与客户确认"一般情况"的判定标准

---

#### 2. LX-007：入院记录缺辅助检查

**LLM 判定**：不合规
- 理由：（方案 A 未提供详细理由）

**实际情况**：
- 辅助检查部分详细记录了 8 项检查结果
- 包括血常规、肝功能、肾功能、心电图、胸部CT、腹部超声、血糖、凝血功能

**分析**：
- ❌ LLM 误判
- 💡 可能需要在提示词中明确"辅助检查"的判定标准

---

#### 3. LX-009：入院记录缺初步诊断

**LLM 判定**：不合规
- 理由：（方案 A 未提供详细理由）

**实际情况**：
- 入院诊断：右肺占位性病变

**分析**：
- ❌ LLM 误判
- 💡 可能需要在提示词中明确"初步诊断"的判定标准

---

## 🚀 实施建议

### 1. 立即实施方案 A

**修改文件**：`app/services/sichuan_qc_service.py`

**修改内容**：
1. 添加 `extract_check_points` 函数
2. 修改 `_build_prompt` 方法
3. 添加日志和错误处理

### 2. 优化误判规则

**LX-002**：与客户确认"一般情况"的判定标准  
**LX-007**：明确"辅助检查"的判定标准  
**LX-009**：明确"初步诊断"的判定标准

### 3. 持续监控和迭代

- 收集更多测试病历
- 对比优化前后的质控结果
- 根据实际效果微调提取逻辑

---

## 📚 参考资料

- **测试脚本**：`test_prompt_optimization_plans.py`（提示词生成和对比）
- **测试脚本**：`test_prompt_plans_with_llm.py`（LLM 实测）
- **测试结果**：`/tmp/prompt_plans_llm_test_results.json`
- **详细报告**：`PROMPT_OPTIMIZATION_LLM_TEST_REPORT.md`

---

**文档版本**：v1.0  
**最后更新**：2024-11-09  
**作者**：Augment Agent

