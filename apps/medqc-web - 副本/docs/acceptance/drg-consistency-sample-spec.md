# 6.2.2 一致率样本与口径（固化）

## 1. 样本来源

- 医院分组结果：院内分组器输出（`hospital_group`）
- 医保对照结果：医保分组结果或对照清单（`insurance_group`）
- 样本键：优先 `case_key`，可使用 `admission_id`

## 2. 样本格式

后端接口 `POST /api/v1/drg/config/consistency-check` 的 `samples` 字段结构：

```json
[
  {
    "case_key": "LXA001",
    "admission_id": "ZY0001",
    "hospital_group": "AB15",
    "insurance_group": "AB15"
  }
]
```

## 3. 统计口径

- 有效样本：`hospital_group` 与 `insurance_group` 同时非空
- 匹配样本：`hospital_group == insurance_group`
- 公式：`一致率 = 匹配成功样本数 / 有效对照样本数`

## 4. 报告字段

- `summary.matched_count`
- `summary.valid_count`
- `summary.consistency_rate`
- `summary.difference_count`
- `differences[]`（差异明细）
