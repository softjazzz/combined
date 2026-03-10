# 病案首页验收报告模板

## 1. 报告信息

- 项目名称：
- 报告版本：
- 生成时间：
- 执行人：
- 后端地址：
- 数据集版本：

## 2. 验收范围

- 接口范围：
  - `/api/v1/frontpage/auto-generate-draft-stream`
  - `/api/v1/qc/coding-qc/check`
  - `/api/v1/icd/search`
  - `/api/v1/frontpage/export`
- 功能范围：
  - 首页流式提取
  - 编码质控
  - ICD 查询
  - 三格式导出（卫健委/医保/结算清单）

## 3. 关键指标

| 指标 | 目标阈值 | 本次结果 | 是否达标 |
| --- | --- | --- | --- |
| 首页生成时延 P95 | <= 30s |  |  |
| 首页生成时延均值 | <= 20s（建议） |  |  |
| 字段填充率均值 | >= 90% |  |  |
| 主诊断名称命中率 | >= 90%（有标注样本） |  |  |
| 主诊断编码命中率 | >= 90%（有标注样本） |  |  |
| 编码质控响应 P95 | < 1s |  |  |
| ICD 搜索响应 P95 | < 500ms |  |  |

## 4. 分样本结果

| case_id | success | latency_ms | modules | fill_rate% | diag_name_hit | diag_code_hit | coding_qc_ms | icd_search_ms | error |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | --- |
|  |  |  |  |  |  |  |  |  |  |

## 5. 导出能力验证

| 导出格式 | 接口参数 | 文件下载 | 文件内容抽检 | 结论 |
| --- | --- | --- | --- | --- |
| 卫健委首页 | `nhc` | 通过/失败 | 通过/失败 |  |
| 医保首页 | `insurance` | 通过/失败 | 通过/失败 |  |
| 医保结算清单 | `settlement` | 通过/失败 | 通过/失败 |  |

## 6. 主要问题与风险

1. 
2. 
3. 

## 7. 结论与建议

- 本轮是否满足验收：通过 / 有条件通过 / 不通过
- 建议的修复优先级：
  1. 
  2. 
  3. 

## 8. 附录

- 原始结果文件：
  - JSON：
  - Markdown：
- 脚本命令：

```bash
cd apps/medqc-web/backend
python scripts/run_frontpage_acceptance.py \
  --base-url http://localhost:8000 \
  --dataset docs/frontpage_acceptance_dataset_template.json \
  --output-dir docs/acceptance
```

