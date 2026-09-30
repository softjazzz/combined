# V3.6 病案首页统计分析合同（P2，PRD 第 47 项）

> 日期：2026-09-30。PRD 验收：可统计病案数、问题病案数、编码/非编码缺陷和科室明细。

## 1. 证据

- 正式首页质控（`frontpage_formal_qc`）和编码质控（`coding_qc`）都通过 `qc_persistence_service.persist_analysis(verified_identity=...)` 写入 `qc.qc_results` 与 `qc.qc_defects`。写入的行带 `identity_version=1`、`source_key` 和三坐标。
- 单病例读取器 `modern_case_qc_result_service` 选“最新结果”的顺序是：`analysis_date`、`created_at`、`id`，均倒序、空值排最后。“本次结果缺陷”取 `qc_defects.result_id = 最新结果 id`。重新质控时，再次检出的缺陷会把 `result_id` 更新为新结果；未检出的缺陷被关闭。
- 首页质控只有四类规则：必填、格式、逻辑、一致性，不含编码类。编码质控另有独立 owner。因此：
  - **编码缺陷** = `coding_qc` 最新结果的缺陷；
  - **非编码缺陷** = `frontpage_formal_qc` 最新结果的缺陷。
- 业务库仍在 revision 44，`qc_results` 没有 `identity_version`/`source_key`，现存旧行不能作为核验身份的数据。报表只读现代行：在迁移 52 及之后部署前，业务库上显示“数据源未部署”（503 `schema_unavailable`），不回退旧行。

## 2. 口径

**病例集**：满足以下条件的三坐标病例：

- 有 `frontpage_formal_qc` 或 `coding_qc` 的现代结果；
- 每个来源取最新 1 条；
- 最新结果的 `analysis_date` 落在窗口内（闭区间；无时区的值按 Asia/Shanghai 解释）。

**科室与主治医师**：取病历池同一读取函数（`hospital_status=all`）按三坐标匹配；不在病历池中的病例计入“未分科室”。

- `department`/`doctor` 筛选作用于该匹配结果。
- 科室角色受工作台数据范围约束。

**KPI**：

| 字段                                                         | 含义                               |
| ------------------------------------------------------------ | ---------------------------------- |
| `case_total`                                                 | 病案数                             |
| `problem_case_total`                                         | 问题病案数：任一来源最新结果有缺陷 |
| `problem_rate`                                               | 问题病案率                         |
| `frontpage_case_total` / `coding_case_total`                 | 各来源有结果的病案数               |
| `noncoding_defect_total` / `coding_defect_total`             | 非编码 / 编码缺陷条数              |
| `noncoding_problem_case_total` / `coding_problem_case_total` | 非编码 / 编码问题病案数            |

**分布与明细**：

- 缺陷严重度分布、缺陷分类分布，按来源分开列出。
- 编码与非编码 top20 规则：按条数降序，并列时按规则号升序。
- 科室明细：病案数、问题病案数、问题率、编码缺陷、非编码缺陷，默认按问题病案数降序。

**病例下钻**：可按科室、来源、规则号、仅问题病案筛选。每行字段：三坐标、姓名、科室、医生、各来源最新质控时间与缺陷数。

**规模上限**：5000 例，超出返回 422 `range_too_large`。

## 3. 接口（`/api/v1/quality-reports`，admin、qc_manager；数据范围同工作台）

- `GET /frontpage-quality`：汇总。
- `GET /frontpage-quality/records`：下钻分页。
- `GET /frontpage-quality/export?sheet=departments|records`：UTF-8 BOM CSV，写审计事件。

| 错误             | 响应                     |
| ---------------- | ------------------------ |
| 参数非法         | 422                      |
| 越权科室         | 403                      |
| 现代身份列未部署 | 503 `schema_unavailable` |
| 读取故障         | 503，固定脱敏提示        |

## 4. 前端

新页面 `/dashboard/qc/reports/frontpage-quality`，挂在“统计分析”子菜单下。

- 分区：总览 / 筛选 / 分布 / 科室明细 / 下钻。
- 未部署时显示“首页质控数据源未部署”，不显示 0。

## 5. 不做

- 不重判缺陷，不读旧行（`identity_version` 为空的行），不含结算清单来源（不属本项）。
- 首页质控平均分：PRD 未要求，本批不做。
