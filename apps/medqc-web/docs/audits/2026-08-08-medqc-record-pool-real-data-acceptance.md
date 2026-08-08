# 病历池准商用 Task 2 真实数据验收（只读）

日期：2026-08-08
范围：`/api/medical-records/workstation` 的真实 CDM 病历池、Task 2A 的已完成 Canonical 摘要投影。
边界：只读；未修改生产/测试代码、数据库、配置或任务数据。本文不记录姓名、住院号、病历正文、科室名称或原始三坐标。

## 冻结条件

| 项目       | 固定值                                                                                 |
| ---------- | -------------------------------------------------------------------------------------- |
| Git HEAD   | `db9ada1210b3a530732c2e50c7768e5ac3631596`                                             |
| 后端监听   | `0.0.0.0:8001`，PID `25500`                                                            |
| 数据库     | PostgreSQL 已配置；`split` schema 模式；`cdm`、`qc`、`public` 可见                     |
| 运行环境   | `ENV=development`                                                                      |
| 当前规则集 | `luxian_0609_qc_v1` / `2026-06-09`                                                     |
| 授权范围   | 全院已登录统一范围；暂不做机构、科室或角色分级。内部关联仍使用三坐标。                 |
| 验收筛选   | 无科室、关键词、日期筛选；`date_field=visit`；第 1/2 页各 50 条，并抽取 3 个科室聚合。 |

运行进程不是生产环境，因此 Task 1A 的生产演示病历失败关闭不在本次进程生效。该事实直接影响本次验收结论。

## 调用链与读法

已用 CodeGraph 核对正式链路：

```text
GET /api/medical-records/workstation
→ get_workstation_data
→ cdm.mr 三坐标筛选
→ build_luxian_0609_completed_record_result_summaries
→ qc.custom_qc_batch_jobs + qc.luxian_0609_record_result_envelopes
→ latest_qc_summary / qc_summary
```

验收调用了该路由处理器的同一服务路径。为遵守只读边界，对历史 `frontpage_generate` 队列回填作了进程内替身，避免该非 Task 2 的遗留逻辑可能写回队列；未改变 `latest_qc_summary` 或 `qc_summary` 的读取逻辑。HTTP 认证中间件未以伪造令牌绕过，故本报告验证的是已认证处理器之后的正式业务输出，而非网络层令牌签发。

## 聚合对账

### 全院无筛选

| 指标                              |         结果 |
| --------------------------------- | -----------: |
| CDM 中三坐标齐全的 `cdm.mr`       |          454 |
| 工作台处理器 `total`              |          456 |
| 工作台 `qc_summary.total_records` |          454 |
| 第 1、2 页 `total` 是否一致       | 是（均 456） |
| 两页 `qc_summary` 是否完全一致    |           是 |
| `qc_summary.running_state`        |    `unknown` |

结论：**不通过**。工作台记录总数比真实 CDM 多 2，而摘要仍正确仅覆盖 454 条真实三坐标记录；这是开发环境演示记录进入病历池的直接证据，不可作为真实病历池准商用验收通过。

### 三个脱敏科室抽样

科室只以 SHA-256 前 12 位标识。`in_hospital`/`discharged` 按 CDM 首页出院时间是否为空计算。

| 科室哈希       | CDM 总数 | 在院 | 出院 | 工作台 `total` | `qc_summary.total_records` | 处理耗时 |
| -------------- | -------: | ---: | ---: | -------------: | -------------------------: | -------: |
| `20e36d297d84` |       48 |   23 |   25 |             48 |                         48 | 977.0 ms |
| `725d093ea644` |       39 |   23 |   16 |             40 |                         40 | 874.4 ms |
| `c3b4bc47dfe7` |       38 |   14 |   24 |             38 |                         38 | 264.3 ms |

第二个科室同样多出 1 条，进一步证明该筛选范围内存在演示记录。三坐标真实记录聚合本身在无演示污染时与 CDM 一致。

## Canonical 投影与状态

以 454 条真实三坐标记录直接调用 `build_luxian_0609_completed_record_result_summaries`：

| 投影状态          | 病历数 | 原因                                          |
| ----------------- | -----: | --------------------------------------------- |
| `ready`           |      5 | 存在可验证的当前版本已完成 Canonical Envelope |
| `not_run`         |    220 | 未发现可投影的已完成当前版本结果              |
| `technical_error` |    229 | `canonical_envelope_missing`，严格失败关闭    |
| 合计              |    454 | 与 CDM 三坐标数一致                           |

该批量读取耗时 **9,218.3 ms**。第 1/2 页工作台读取耗时分别为 **9,766.0 ms**、**9,025.3 ms**；性能仅为本次基线，不作为 SLA。

抽查 10 个真实三坐标（仅输出不可逆短哈希）结果：

| 三坐标哈希     | 摘要状态          | 规则状态数 | 原因                         |
| -------------- | ----------------- | ---------: | ---------------------------- |
| `a0d15ad0b4b7` | `not_run`         |          0 | —                            |
| `8d6d1be7931b` | `ready`           |         75 | —                            |
| `25f1d1047502` | `ready`           |         75 | —                            |
| `4535921d5899` | `ready`           |         75 | —                            |
| `2416f626dc8a` | `technical_error` |          0 | `canonical_envelope_missing` |
| `c7b9e5bb813a` | `technical_error` |          0 | `canonical_envelope_missing` |
| `27acc62d8ed3` | `technical_error` |          0 | `canonical_envelope_missing` |
| `103a674822de` | `technical_error` |          0 | `canonical_envelope_missing` |
| `53392c197baa` | `technical_error` |          0 | `canonical_envelope_missing` |
| `a2a84f9e883f` | `technical_error` |          0 | `canonical_envelope_missing` |

展示哈希仅供本次脱敏抽查辨识，不能作为业务键；正式复核若需逐条重演，应在受控环境重新计算完整 SHA-256。

## unknown 合同与演示隔离

- 对 454 条真实 CDM 病历，`source_state.status` 均为 `unknown`；未按文书数量推断资料同步完整性。
- `qc_summary.running_state` 为 `unknown`；未将仅按 `visit_id` 存储的遗留队列状态投影为运行中质控状态。
- 工作台前两页前置的 2 条记录不具备真实三坐标与 `source_state`；它们就是本次演示污染证据。

## 验收结论和后续门禁

Task 2A 的失败关闭、分页无关摘要、`source_state=unknown` 与 `running_state=unknown` 合同在真实三坐标数据上成立；但本环境**不具备准商用真实病历池通过条件**，原因如下：

1. `ENV=development` 使 2 条演示病历混入工作台，导致接口 `total` 与真实 CDM 不一致；必须以生产配置重启并在 HTTP 实际入口复验。
2. 229/454 条真实病历为 `canonical_envelope_missing`，不能展示为可用质控结果；需要单独追查历史完成任务为何没有当前版本 Envelope，不能在病历池层回退或伪造结果。
3. 220/454 条未运行是如实状态，不应被解释为资料已同步或正在执行。
4. 当前是用户明确批准的全院统一范围，尚无机构/科室隔离；投入多院区前必须另立授权与数据隔离任务。

本报告不批准启动首页 UI、趋势、队列投影或任何修复。先满足以上两个阻断项后，再用固定生产进程、真实认证 HTTP 请求和相同无筛选条件重做本验收。
