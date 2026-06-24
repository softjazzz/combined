# Claude 验收清单（向量检索 M2）

## 1. 范围确认
- M1：语义检索兜底已接入（精确失败后触发）。
- M2：低置信候选回传到 `suggestions` 字段。
- 本清单用于验证 `frontpage` + `case-front-page` 两条链路的“可用性与稳定性”。

## 2. 必跑命令
在 `apps/medqc-web/backend` 目录执行：

```powershell
py -3.10 -m py_compile app/routers/frontpage.py app/schemas/frontpage.py app/services/local_icd_service.py tests/unit/test_frontpage_router_api_postprocess.py tests/unit/test_frontpage_router_postprocess.py tests/unit/test_local_icd_semantic.py
```

```powershell
py -3.10 -m pytest tests/unit/test_frontpage_router_api_postprocess.py tests/unit/test_frontpage_router_postprocess.py tests/unit/test_local_icd_semantic.py -q
```

期望：`8 passed`

## 3. 关键验收点
1. 精确命中不被覆盖  
- 诊断文本能被本地 ICD 精确匹配时，直接写 `..._icd`，不走 suggestions。

2. 高置信语义候选自动填码  
- `score >= ICD_SEMANTIC_T_HIGH` 时，自动写 `discharge_main_icd` 或对应其他诊断编码。

3. 低置信语义候选仅回传 suggestions  
- `ICD_SEMANTIC_T_LOW <= score < ICD_SEMANTIC_T_HIGH`：
  - 不写最终编码
  - 回传：
    - `diagnoses.discharge_main_icd_suggestions`
    - `diagnoses.discharge_other_icd_suggestions`

4. `/api/v1/frontpage/auto-generate-draft` 兜底可用  
- 当 LLM 抽取诊断为空时，能从“出院诊断”段兜底解析并再执行本地编码/语义候选回填。

## 4. 手工接口验收（UTF-8）
建议使用 UTF-8 脚本请求，避免 PowerShell 控制台中文被转 `??`。

示例请求文本：

```text
姓名：张三
出院诊断：
1. PCI术后状态
2. 高血压病3级（极高危组）
3. 2型糖尿病
手术名称：经皮冠状动脉造影
```

期望：
- `discharge_main_diagnosis_text = "PCI术后状态"`
- `discharge_other_diagnoses_texts` 至少含高血压、糖尿病
- `discharge_main_icd_suggestions` 或 `discharge_other_icd_suggestions` 可按阈值出现

## 5. 环境开关核对
`backend/.env`：

```env
ICD_SEMANTIC_ENABLED=true
ICD_SEMANTIC_TOP_K=5
ICD_SEMANTIC_T_HIGH=0.90
ICD_SEMANTIC_T_LOW=0.60
```

## 6. 失败排查优先级
1. 先看后端是否为新进程（端口 8001 + 重启时间）。
2. 再看输入是否 UTF-8（是否被转成 `??`）。
3. 再看日志中 `frontpage auto-generate fallback parse filled diagnoses` 是否出现。
4. 最后检查阈值配置是否被实际加载。
