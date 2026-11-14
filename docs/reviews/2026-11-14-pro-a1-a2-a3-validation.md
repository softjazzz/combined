# A1 / A2 / A3 修复与隔离验证

基线：`3893a93c3193d6733c02a4425498fbc32ebe736c`，从已获取的 `github/codex/business-agent-integration` 创建独立分支 `codex/pro-a1-a2-a3-fixes-20261114`。

## 第一阶段行为（无首页新合同另行补充）

- **A1**：003 超时、031 明确签名不符分支只声明实际证明文书，并提供由既有 binding 验证的阳性引用。备选来源为空不再覆盖已证缺陷。缺文书、缺字段、截断、时间冲突、来源/哈希错误不享受该例外；未修改通用准入、绑定或 finalizer。执行器版本更新，旧结果与旧快照不改写。
- **A2**：latest-result、单份导出、整改草稿及批量导出均先解析持久账号。普通 qc_manager 仅可读取同机构；停用、坏角色、缺机构和账号库故障失败关闭。admin/sync_admin/super_admin 保留本入口原有全局角色合同。批量选中范围在读取前校验；筛选导出在读取结果前校验返回身份，混入其他机构则整体拒绝，不静默删行或导出越权结果。三坐标、来源、完整性和历史 DTO 校验保持原样。
- **A3**：正式 LX0609 legacy 任务没有精确失败范围时，返回受控 `409 new_task_required_preserve_history`，要求通过现有入口新建任务，禁止原地清空。父任务也不得经旧重试路径重置全部子任务。自动调用返回未入队；精确叶子失败补跑和 MQ 既有保护保持。**没有新增自动克隆或不可变 attempt 子系统**。

无数据库迁移、无前端协议变更、无历史数据修复脚本。用户随后明确所有质控不依赖首页，相关交叉取材路径已纳入后续修复；本节测试结果对应第一阶段，不能作为新合同全部通过的证明。A5模型重试仍不在本轮范围。

### 独立复审补修：相邻 qc-detail 入口

固定 `90caba76a` 的独立复审确认：旧 `/records/{id}/qc-detail` 也调用 Canonical，原有角色检查不足以限制普通 qc_manager 的机构。

已补强制身份授权回调，DTO 查询前核对持久机构；普通管理账号在旧无机构缓存读取前也核对机构。医生沿用全局病例归属守卫的完整三坐标，权限 HTTPException 不被通用错误处理吞掉。相邻调用者的只读审查未确认其他同类绕过；A3 未确认新的 P1/P2。

`test_qc_record_read_permissions.py`、`test_records_qc_detail_canonical.py`、`test_doctor_case_scope.py` 在最近定向集合中全部通过；该集合共118 passed/1 skipped/2 failed，两个失败属于另行调整的无首页合同（063旧执行断言、首页优先时间断言），不属于权限修复。Canonical 单测采用现成离线表准备夹具，结果字段/身份冲突/损坏/脱敏断言保留。

## 必要验证

统一使用 `python -B apps/medqc-web/backend/scripts/run_pr8_offline_tests.py <显式用例>`。该 runner 禁读 dotenv、阻断网络和非 SQLite 连接；未加载应用 lifespan、后台 worker 或调度。数据库仅为合成内存 SQLite；材料保存仅为临时目录中的合成对象。

| 范围 | 结果与边界 |
|---|---|
| 新增 A1 与原 003/031 定向用例 | 53 passed（`test_surgery_independent_positive_scope.py` + `test_luxian_0609_native_surgery_gate_execution.py -k '003 or 031 or independent or positive_surgery or positive_scope'`），覆盖24小时边界、时间冲突、结构化签名、截断、无模型及冻结读取保护 |
| 更新执行器版本后的 A1 / 通用 guard / 历史合同 | 30 passed，包含新增7项、guard 的独立缺口/零行/伪造引用/绑定来源用例及 `test_historical_diagnosis_trace_compat.py` |
| 权限、导出、医生隔离、最新结果、部分结果持久化 | 首轮117 passed；4个改写为独立新任务的用例因合成夹具误加非持久进度列失败；修正夹具后下行定向复验全部通过。未为通过检查修改生产合同 |
| A3 新增与相邻新任务/CAS保护 | 14 passed（`test_legacy_full_retry_preserves_history.py` + `test_qc_partial_failure_persistence.py -k 'full or late_root or parent_retry or full_retry_route'`），覆盖原任务/信封/快照逐字不变、父子保护、HTTP409无入队、新失败不混旧结果与迟到 claim 拒绝 |
| 1026来源身份 | `test_material_latest_result_identity.py` 6 passed，登记三坐标与路径映射保留 |

权限/持久化首轮的6个明确文件：`test_qc_record_read_permissions.py`、`test_qc_sichuan_record_result_exports.py`、`test_legacy_full_retry_preserves_history.py`、`test_qc_partial_failure_persistence.py`、`test_latest_full_record_result.py`、`test_doctor_case_scope.py`。包含原精确失败补跑与 MQ 用例，未排除失败用例。

修复前已复现：003/031 独立缺陷被错误降级、跨机构和失效持久账号请求到达结果读取、completed/failed/canceled 的原任务被清空。新增测试分别先失败，修复后通过。

两处既有测试夹具校正：latest-full-result 单测补挂仓库现成的离线表准备夹具；文书角色测试区分“医生允许角色”与全局病例归属守卫，并单独运行医生病例归属原有用例。未删掉身份、来源、完整性或医生范围断言。

## 未验证与边界

- 未执行真实 PG、浏览器交互、部署、真实临床材料和全量规则评估；没有把 SQLite 验证称为 PG 并发验收。
- 新任务与历史任务并存、旧材料不被写入已用合成事务验证；生产并发、进程重启/恢复未演练。
- 测试仅有既存 Pydantic/Starlette 弃用和 schema 字段警告。
- 没有连接服务器业务库/CDM/Caché，没有模型调用、质控任务、27份重跑、合并或部署。
- 独立复审已完成：首次固定 `cdcf5eb46` 发现三项权限/003边界阻断；集中补修与必要隔离验证后，固定源码 `866cbca3d` 逐项复核关闭，未确认新增P1/P2。详见 `2026-11-14-pro-fixes-independent-review.md`。
