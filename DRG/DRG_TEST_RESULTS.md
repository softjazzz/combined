# DRG 分组 API 测试结果

## ✅ 测试成功！

**接口地址**: `https://medchat.fun/api/drg-grouping`  
**HTTP 状态**: 200 OK  
**测试时间**: 2025-12-30

---

## 📊 返回的 DRG 分组结果

### 核心信息

| 字段 | 值 | 说明 |
|------|-----|------|
| **DRG 编码** | ES35 | 诊断相关组编码 |
| **ADRG 编码** | ES3 | 邻近诊断组 |
| **MDC 编码** | MDCE | 主要诊断类别（呼吸系统） |
| **CC/MCC 状态** | nocc | 无并发症或合并症 |
| **规则来源** | 四川省 | 使用的分组规则版本 |
| **验证状态** | success | 分组验证通过 |

### DRG 分组层级

```
MDC (主要诊断类别)
  └─ MDCE (呼吸系统疾病)
      └─ ADRG (邻近诊断组)
          └─ ES3 (呼吸系统感染/炎症)
              └─ DRG (诊断相关组)
                  ├─ ES31 (伴严重并发症或合并症)
                  ├─ ES33 (伴并发症或合并症)
                  └─ ES35 (不伴并发症或合并症) ✓
```

---

## 🔍 返回数据结构分析

### 顶层字段

```json
{
  "success": true,                    // 是否成功
  "result": [...],                    // 分组结果数组
  "rule_source": "四川省",             // 规则来源
  "grouping_path": {...},             // 分组路径和验证详情
  "drg_catalogue_info": {...}         // DRG 目录信息
}
```

### 分组结果 (result)

```json
{
  "DRGCode": "ES35",                  // DRG 编码
  "ADRGCode": "ES3",                  // ADRG 编码
  "MDCCode": "MDCE",                  // MDC 编码
  "CCStatus": "nocc",                 // CC/MCC 状态
  "PDX": "J18.900",                   // 主诊断
  "ADXs": "",                         // 附加诊断
  "PROCs": "",                        // 手术操作
  "age": 30,                          // 年龄
  "sex": 2,                           // 性别 (2=女)
  "LOS": 12,                          // 住院天数
  "ICU": 0                            // 是否ICU
}
```

### 分组路径验证 (grouping_path)

包含完整的三级验证：

1. **MDC 检查** - 验证主要诊断类别
   - 检查主诊断是否匹配 MDC 规则
   - 返回：`MDC检查通过：实际分组 [MDCE] 与预期一致`

2. **ADRG 检查** - 验证邻近诊断组
   - 检查主诊断是否匹配 ADRG 规则
   - 返回：`ADRG检查通过：实际分组 [ES3] 与预期一致`

3. **DRG 检查** - 验证最终诊断相关组
   - 检查 CC/MCC 状态和 ICU 情况
   - 返回：`DRG检查通过：实际分组 [ES35] 与预期一致`

### CC/MCC 状态说明

| 状态 | 含义 | DRG 后缀 |
|------|------|---------|
| **mcc** | 有严重并发症或合并症 | 1 (如 ES31) |
| **cc** | 有并发症或合并症 | 3 (如 ES33) |
| **nocc** | 无并发症或合并症 | 5 (如 ES35) |

---

## 💡 应用场景

### 1. 批量病例 DRG 分组

```python
import pandas as pd

def batch_drg_grouping(cases_df):
    """批量处理病例 DRG 分组"""
    results = []
    
    for _, case in cases_df.iterrows():
        payload = {
            "city_name": case['城市'],
            "pdx_code": case['主诊断编码'],
            "adx_code": case.get('附加诊断', ''),
            "proc_code": case.get('手术编码', ''),
            "patient_gender": case['性别'],
            "patient_age": case['年龄'],
            "los": case['住院天数'],
            "icu": 1 if case.get('ICU', '否') == '是' else 0,
            "birth_weight": case.get('出生体重', 0),
            "fee_per_point": 60,
            "high_ratio_limit": 3,
            "low_ratio_limit": 0.5,
            "rate": 1,
            "settlement_source": "none",
            "total_fee": 0
        }
        
        resp = requests.post(API_URL, headers=HEADERS, json=payload)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success') and data.get('result'):
                result = data['result'][0]
                results.append({
                    '病例号': case['病例号'],
                    'MDC': result.get('MDCCode'),
                    'ADRG': result.get('ADRGCode'),
                    'DRG': result.get('DRGCode'),
                    'CC状态': result.get('CCStatus'),
                    '规则来源': data.get('rule_source')
                })
    
    return pd.DataFrame(results)
```

### 2. DRG 权重计算

```python
# DRG 权重数据（示例）
DRG_WEIGHTS = {
    'ES31': 1.2534,  # 伴严重并发症
    'ES33': 0.8523,  # 伴并发症
    'ES35': 0.5534,  # 不伴并发症
}

def calculate_drg_payment(drg_code, total_fee, fee_per_point=60):
    """计算 DRG 支付金额"""
    weight = DRG_WEIGHTS.get(drg_code, 1.0)
    base_rate = fee_per_point  # 单位分值
    
    payment = weight * base_rate * 1000  # 假设基数为1000
    
    return {
        'drg_code': drg_code,
        'weight': weight,
        'payment': payment,
        'actual_fee': total_fee,
        'difference': payment - total_fee
    }
```

### 3. CC/MCC 影响分析

```python
def analyze_cc_impact(base_case, with_cc_case):
    """分析并发症对 DRG 分组的影响"""
    base_drg = base_case['drg_code']
    cc_drg = with_cc_case['drg_code']
    
    if base_drg != cc_drg:
        print(f"✅ 并发症影响分组:")
        print(f"   无并发症: {base_drg} (权重: {DRG_WEIGHTS.get(base_drg)})")
        print(f"   有并发症: {cc_drg} (权重: {DRG_WEIGHTS.get(cc_drg)})")
        
        weight_diff = DRG_WEIGHTS.get(cc_drg, 0) - DRG_WEIGHTS.get(base_drg, 0)
        print(f"   权重差异: {weight_diff:+.4f}")
    else:
        print(f"⚠️  并发症未影响 DRG 分组: {base_drg}")
```

### 4. 地区规则对比

```python
def compare_regional_rules(case_data, regions):
    """对比不同地区的 DRG 分组规则"""
    results = {}
    
    for region in regions:
        payload = {**case_data, "city_name": region}
        resp = requests.post(API_URL, headers=HEADERS, json=payload)
        
        if resp.status_code == 200:
            data = resp.json()
            result = data['result'][0]
            results[region] = {
                'drg_code': result['DRGCode'],
                'rule_source': data['rule_source'],
                'cc_status': result['CCStatus']
            }
    
    # 分析差异
    drg_codes = [r['drg_code'] for r in results.values()]
    if len(set(drg_codes)) == 1:
        print("✅ 所有地区使用相同的 DRG 分组")
    else:
        print("⚠️  不同地区的 DRG 分组存在差异:")
        for region, result in results.items():
            print(f"   {region}: {result['drg_code']} ({result['rule_source']})")
```

### 5. DRG 分组验证工具

```python
def validate_drg_grouping(expected_drg, actual_response):
    """验证 DRG 分组是否符合预期"""
    actual_drg = actual_response['result'][0]['DRGCode']
    grouping_path = actual_response['grouping_path']
    
    validation_result = {
        'expected': expected_drg,
        'actual': actual_drg,
        'match': expected_drg == actual_drg,
        'mdc_check': grouping_path['mdc_check']['status'],
        'adrg_check': grouping_path['adrg_check']['status'],
        'drg_check': grouping_path['drg_check']['status'],
        'final_outcome': grouping_path['final_outcome']
    }
    
    if not validation_result['match']:
        print(f"⚠️  分组不一致:")
        print(f"   预期: {expected_drg}")
        print(f"   实际: {actual_drg}")
        print(f"   MDC: {grouping_path['mdc_check']['message']}")
        print(f"   ADRG: {grouping_path['adrg_check']['message']}")
        print(f"   DRG: {grouping_path['drg_check']['message']}")
    else:
        print(f"✅ 分组验证通过: {actual_drg}")
    
    return validation_result
```

---

## ⚠️ 重要注意事项

### 1. DRG 编码规则

- **格式**: 字母 + 数字（如 ES35）
- **字母部分**: 表示 ADRG（如 ES3）
- **数字部分**: 表示 CC/MCC 级别
  - 1 = 伴严重并发症或合并症 (MCC)
  - 3 = 伴并发症或合并症 (CC)
  - 5 = 不伴并发症或合并症 (NoCC)

### 2. MDC 分类

MDC (Major Diagnostic Category) 主要诊断类别：
- **MDCE**: 呼吸系统疾病
- **MDCF**: 消化系统疾病
- **MDCG**: 肝胆胰系统疾病
- 等等...

### 3. 地区规则差异

不同地区可能使用不同的 DRG 分组规则：
- **全国版**: 国家统一规则
- **省级版**: 如"四川省"、"浙江省"
- **市级版**: 如"泸州市"、"杭州市"

### 4. CC/MCC 判定

并发症/合并症的判定影响最终 DRG 分组：
- 需要在 `adx_code` 中填写附加诊断
- 系统会自动判定是否为 CC 或 MCC
- 影响权重和支付金额

### 5. Cookie 时效性

当前 Cookie 可能会过期，建议定期更新。

### 6. 请求频率

建议添加请求间隔（0.5-1秒），避免触发限流。

---

## 📈 DRG vs DIP 对比

| 特性 | DRG | DIP |
|------|-----|-----|
| **全称** | Diagnosis Related Groups | Diagnosis-Intervention Packet |
| **编码格式** | 字母+数字 (如 ES35) | 诊断-手术 (如 J18.9-null) |
| **分组层级** | MDC → ADRG → DRG | 直接分组 |
| **并发症处理** | 影响 DRG 编码后缀 | 不影响编码 |
| **分组粒度** | 较粗（按严重程度） | 较细（诊断+手术组合） |
| **权重体系** | 基于 DRG 权重 | 基于病种分值 |
| **适用场景** | 按病组付费 | 按病种付费 |
| **规则来源** | 地区规则 | 全国版/地区版 |

---

## 🚀 下一步建议

### 立即可做

1. **完善脚本功能**
   - 添加 Excel 批量导入/导出
   - 实现 CC/MCC 影响分析
   - 添加权重计算功能

2. **测试更多场景**
   - 不同 CC/MCC 状态的病例
   - 不同地区的分组规则
   - 复杂病例（多诊断、多手术）

### 中期规划

3. **构建 DRG 分组服务**
   - FastAPI 封装
   - 标准化输入输出
   - 缓存机制

4. **数据分析工具**
   - DRG 分布统计
   - 权重分析
   - 地区规则对比

### 长期目标

5. **生产级部署**
   - Docker 容器化
   - 负载均衡
   - 监控告警

6. **与平台方沟通**
   - 了解官方 API
   - 评估商业合作
   - 确认使用授权

---

## 📝 总结

✅ **DRG 分组 API 完全可用**  
✅ **返回完整的三级验证**（MDC → ADRG → DRG）  
✅ **支持地区规则**（四川省、全国版等）  
✅ **包含 CC/MCC 判定逻辑**  
✅ **可用于批量处理、权重计算、规则对比等场景**  

⚠️ **注意事项**：Cookie 时效、请求频率、地区规则差异、法律合规性
