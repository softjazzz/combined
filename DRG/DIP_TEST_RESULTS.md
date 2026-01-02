# DIP 分组 API 测试结果

## ✅ 测试成功！

**接口地址**: `https://medchat.fun/api/dip-grouping`  
**HTTP 状态**: 200 OK  
**测试时间**: 2025-12-30

---

## 📊 返回的 DIP 分组结果

### 核心信息

| 字段 | 值 | 说明 |
|------|-----|------|
| **DIP 编码** | J18.9-null | 主诊断-手术编码组合 |
| **DIP 名称** | 未特指的肺炎-保守治疗 | 病种名称 |
| **DIP 类型** | 核心内科组 | 分组类型 |
| **主诊断规则** | J18.9 | 主诊断匹配规则 |
| **操作规则** | BSZL (保守治疗) | 无主手术 |
| **规则来源** | 全国版 | 使用的分组规则版本 |
| **验证状态** | success | 分组验证通过 |

### 关键发现

**DIP vs DRG 的区别**：
- **DIP** (Diagnosis-Intervention Packet) - 按病种分值付费
  - 编码格式：`诊断编码-手术编码`（如 `J18.9-null`）
  - 保守治疗用 `null` 表示
  - 分组更细致，同一诊断+不同手术=不同病种
  
- **DRG** (Diagnosis Related Groups) - 按疾病诊断相关分组
  - 编码格式：字母+数字（如 `ES35`）
  - 按疾病严重程度和并发症分组

---

## 🔍 返回数据结构分析

### 顶层字段

```json
{
  "success": true,                    // 是否成功
  "result": [...],                    // 分组结果数组
  "rule_source": "全国版",             // 规则来源
  "grouping_path": {...},             // 分组路径和验证详情
  "dip_catalogue_info": {},           // DIP 目录信息
  "reference_grouping": {...}         // 参考病种列表
}
```

### 分组结果 (result)

```json
{
  "dipcode": "J18.9-null",           // DIP 编码
  "PDX": "J18.900",                   // 主诊断
  "PROC1": "null",                    // 主手术
  "age": 30,                          // 年龄
  "sex": 2,                           // 性别 (2=女)
  "LOS": 12,                          // 住院天数
  "ICU": 0                            // 是否ICU
}
```

### 分组路径验证 (grouping_path)

包含完整的验证步骤：
1. **类型检查** - 验证是否为内科/外科组
2. **主诊断检查** - 验证主诊断是否匹配规则
3. **操作组检查** - 验证手术操作
4. **最终分组对比** - 确认分组结果

### 参考病种列表 (reference_grouping)

返回了 **46 个相关病种**，包括：
- 同一主诊断 + 不同手术的组合
- 例如：`J18.9-33.2302` (未特指的肺炎-电子支气管镜检查)
- 例如：`J18.9-93.9000` (未特指的肺炎-无创机械性通气)
- 例如：`J18.9-null` (未特指的肺炎-保守治疗) ← 当前病例

---

## 💡 应用场景

### 1. 批量病例 DIP 分组

```python
import pandas as pd
import requests

def batch_dip_grouping(cases_df):
    """批量处理病例 DIP 分组"""
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
        
        resp = requests.post(
            "https://medchat.fun/api/dip-grouping",
            headers=HEADERS,
            json=payload
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success') and data.get('result'):
                dip_code = data['result'][0].get('dipcode', 'N/A')
                
                # 从参考病种中查找名称
                dip_name = 'N/A'
                for ref in data.get('reference_grouping', {}).get('pdx_related', []):
                    if ref['dip_code'] == dip_code:
                        dip_name = ref['dip_name']
                        break
                
                results.append({
                    '病例号': case['病例号'],
                    'DIP编码': dip_code,
                    'DIP名称': dip_name,
                    '规则来源': data.get('rule_source', 'N/A')
                })
    
    return pd.DataFrame(results)

# 使用示例
cases = pd.read_excel('病例列表.xlsx')
dip_results = batch_dip_grouping(cases)
dip_results.to_excel('DIP分组结果.xlsx', index=False)
```

### 2. 智能推荐相关病种

利用 `reference_grouping` 字段，可以推荐相关的 DIP 病种：

```python
def recommend_related_dip(response_data):
    """推荐相关 DIP 病种"""
    current_dip = response_data['result'][0]['dipcode']
    related = response_data['reference_grouping']['pdx_related']
    
    print(f"当前病种: {current_dip}")
    print(f"\n相关病种 ({len(related)} 个):")
    
    for dip in related:
        marker = "✓" if dip['dip_code'] == current_dip else " "
        print(f"  [{marker}] {dip['dip_code']}: {dip['dip_name']}")
```

### 3. DIP 分组验证工具

```python
def validate_dip_grouping(expected_dip, actual_response):
    """验证 DIP 分组是否符合预期"""
    actual_dip = actual_response['result'][0]['dipcode']
    grouping_path = actual_response['grouping_path']
    
    validation_result = {
        'expected': expected_dip,
        'actual': actual_dip,
        'match': expected_dip == actual_dip,
        'checks': grouping_path['check_steps'],
        'final_outcome': grouping_path['final_outcome']
    }
    
    if not validation_result['match']:
        print(f"⚠️  分组不一致:")
        print(f"   预期: {expected_dip}")
        print(f"   实际: {actual_dip}")
    else:
        print(f"✅ 分组验证通过: {actual_dip}")
    
    return validation_result
```

### 4. 城市规则对比

```python
def compare_city_rules(case_data, cities):
    """对比不同城市的 DIP 分组规则"""
    results = {}
    
    for city in cities:
        payload = {**case_data, "city_name": city}
        resp = requests.post(API_URL, headers=HEADERS, json=payload)
        
        if resp.status_code == 200:
            data = resp.json()
            results[city] = {
                'dip_code': data['result'][0]['dipcode'],
                'rule_source': data['rule_source']
            }
    
    # 分析差异
    dip_codes = [r['dip_code'] for r in results.values()]
    if len(set(dip_codes)) == 1:
        print("✅ 所有城市使用相同的 DIP 分组规则")
    else:
        print("⚠️  不同城市的 DIP 分组规则存在差异:")
        for city, result in results.items():
            print(f"   {city}: {result['dip_code']} ({result['rule_source']})")
```

---

## ⚠️ 重要注意事项

### 1. DIP 编码格式

- 格式：`主诊断-手术编码`
- 保守治疗：`诊断编码-null`
- 示例：
  - `J18.9-null` - 未特指的肺炎，保守治疗
  - `J18.9-33.2302` - 未特指的肺炎，电子支气管镜检查

### 2. 手术编码处理

如果病例没有手术操作：
- `proc_code` 传空字符串 `""`
- 返回的 `PROC1` 为 `"null"`
- DIP 编码后缀为 `-null`

### 3. 性别编码

- `1` = 男
- `2` = 女

### 4. ICU 字段

- `0` = 否
- `1` = 是

### 5. Cookie 时效性

当前 Cookie 可能会过期，建议：
- 定期更新 Cookie
- 或实现自动登录机制

### 6. 请求频率

建议添加请求间隔（0.5-1秒），避免触发限流。

---

## 📈 与 DRG 的对比

| 特性 | DIP | DRG |
|------|-----|-----|
| **全称** | Diagnosis-Intervention Packet | Diagnosis Related Groups |
| **编码格式** | 诊断-手术 (如 J18.9-null) | 字母+数字 (如 ES35) |
| **分组粒度** | 更细（诊断+手术组合） | 较粗（按疾病严重程度） |
| **保守治疗** | 明确标注 `-null` | 包含在分组中 |
| **适用场景** | 按病种付费 | 按疾病诊断相关分组付费 |
| **参考病种** | 返回相关病种列表 | 返回分组信息 |

---

## 🚀 下一步建议

### 立即可做

1. **完善脚本功能**
   - 添加 Excel 批量导入/导出
   - 实现相关病种推荐
   - 添加分组验证功能

2. **测试更多场景**
   - 不同城市的分组规则
   - 有手术操作的病例
   - 复杂病例（多诊断、多手术）

### 中期规划

3. **构建 DIP 分组服务**
   - FastAPI 封装
   - 标准化输入输出
   - 缓存机制

4. **数据分析工具**
   - DIP 分布统计
   - 城市规则对比
   - 病种推荐系统

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

✅ **DIP 分组 API 完全可用**  
✅ **返回数据结构完整**（分组结果、验证路径、参考病种）  
✅ **支持全国版规则**  
✅ **可用于批量处理、病种推荐、分组验证等场景**  

⚠️ **注意事项**：Cookie 时效、请求频率、法律合规性
