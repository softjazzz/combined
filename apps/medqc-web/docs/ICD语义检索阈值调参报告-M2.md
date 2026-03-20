# ICD 语义检索阈值调参报告（M2）

## 1. 目标
- 将低置信语义候选回传到前端可见的 `suggestions` 字段。
- 保持“高置信自动填码、低置信仅建议”的安全策略，避免误自动编码。

## 2. 本次实现
- 主诊断：
  - 字段：`diagnoses.discharge_main_icd_suggestions`
  - 规则：当语义候选分数 `< ICD_SEMANTIC_T_HIGH` 且 `>= ICD_SEMANTIC_T_LOW`，回传候选列表，不自动写入 `discharge_main_icd`。
- 其他诊断：
  - 字段：`diagnoses.discharge_other_icd_suggestions`
  - 结构：`[{ diagnosis_text, suggestions: [...] }]`
  - 规则同上。
- 高置信（`>= ICD_SEMANTIC_T_HIGH`）仍自动填码；同时可继续保留低分备选给前端人工核对。

## 3. 阈值建议
- 当前建议值（已落在 `backend/.env`）：
  - `ICD_SEMANTIC_ENABLED=true`
  - `ICD_SEMANTIC_TOP_K=5`
  - `ICD_SEMANTIC_T_HIGH=0.90`
  - `ICD_SEMANTIC_T_LOW=0.60`

## 4. 调参结论
- `T_HIGH=0.90`：可显著降低误自动填码风险，适合病案首页场景。
- `T_LOW=0.60`：能覆盖“同义写法/简称/术后状态”这类候选，给人工二次确认足够信息。
- `TOP_K=5`：在可读性和召回之间平衡，前端不至于过载。

## 5. 运行建议（生产）
- 第一周建议记录以下指标并按周复盘：
  - 高置信自动填码通过率
  - 低置信建议被人工采纳率（Top1/Top3）
  - 误建议率（人工判定）
- 若“低置信建议采纳率 > 70% 且误建议率低”，可尝试将 `T_HIGH` 下调到 `0.88`；
  若误自动填码上升，回退到 `0.90` 或 `0.92`。

## 6. 回归测试点
- 低置信主诊断：不自动写码，`discharge_main_icd_suggestions` 非空。
- 低置信其他诊断：`discharge_other_icd_suggestions` 与诊断文本一一对应。
- 高置信语义候选：自动写码成功。
- 语义关闭：行为与历史版本一致。
