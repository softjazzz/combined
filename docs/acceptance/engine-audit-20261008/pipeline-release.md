# 0609 公共正式链路与交付前置审查归档

本轮完成公共链路代码审查、已有测试覆盖核对，以及 67 项局部工程门禁；没有确认新的 0609 生产缺陷。正式链路已有隔离集成证据可继承，但本轮未重跑完整三入口、HTTP 回读或跨进程重启链，因此不能宣布候选版本完整验收或客户部署通过。

## 范围与来源

- 仅审查 LX0609 的任务创建、冻结范围、worker、保存、latest、批详情、导出、重试取消及历史兼容；不审医学判据。
- 按用户最新指令，0916 为 `scope_excluded_by_user`，不计审查分母、阻断或完成率，先前相关观察不进入本报告问题清单。
- 初始源码基线：`7b894dc84491b7b72eb096de58fe61f772cc0080`。
- 归档时候选 HEAD：`6930540f27e9c279241d35ac05d1c1c6e9134f82`。
- 已核对两 SHA 差异仅为 `apps/medqc-web/docs/plans/2026-10-08-full-engine-acceptance.md`；backend、src、scripts 的提交差异为空，生产源码审查仍对应初始基线。没有把文档提交解释为生产代码变动。
- 已读取根 `AGENTS.md`；仓库没有 `.codegraph/`。本代理未改生产、共享测试或 TODO，未提交，未启服务或浏览器，未访问真实 `.env`、PG 或网络模型。

## 当前完成层级

| 层级 | 本轮状态 | 可作出的结论 |
| --- | --- | --- |
| 公共链路静态审查 | 已完成 | 正式路径、冻结合同及已有测试已逐段核对；本轮无确认的新 0609 缺陷 |
| 同步合同/隔离存储局部回归 | 36 项通过 | 仅覆盖选中的同步测试，不等同完整 worker、三入口或 API 链重跑 |
| 交付脚本局部工程回归 | 31 项通过 | 白名单、来源、旧产物拒绝及预检脚本合同已检验，不等同实际交付包安装 |
| 既有正式三入口/HTTP 集成证据 | 已审查，可继承覆盖 | 测试保留生产路由、派发、worker、SQLite 保存和 Canonical 回读，只替换外部边界；本轮未重跑 |
| 最终候选产物及客户链 | 门禁仍待执行 | 缺此层证据不表示未审查；不能据局部工程通过宣称部署通过 |

## 0609 公共链路覆盖核对

以下路径均相对仓库根。测试名称及源代码是覆盖证据；除“本轮执行”一节外，不主张这些用例已在本轮再次运行。

| 环节 | 正式实现和已有证据 | 本轮结论及剩余门禁 |
| --- | --- | --- |
| 创建与派发 | `backend/app/routers/qc_sichuan.py` 的 `create_workspace_batch_job`、`_run_sichuan_workspace_batch_job`；`test_qc_sichuan_workspace_batch_flow.py`、`test_custom_qc_workspace_batch_record_refs.py` | 服务端冻结三坐标病例范围，拒绝重复/歧义坐标；需最终 SHA 的实际路由、派发及同住院号多病例回归 |
| 规则、配置与执行时点冻结 | `qc_sichuan.py:2016`、`:2099`；`luxian_0609/rule_decision_settings.py`、`phase_scope.py`；`test_luxian_0609_task_settings_snapshot.py`、`test_luxian_0609_task_plan_freeze_probe.py`、`test_luxian_0609_task_runtime_identity.py`、`test_luxian_0609_frozen_horizon_entry.py` | 已有设置和实现/模型身份漂移前置拒绝、病例范围不能缩水及冻结时点测试。本轮只重跑其中选中的同步身份/设置用例；完整异步范围与时点门禁待重跑 |
| worker 正式执行 | `sichuan_workspace_batch_worker.py`、`luxian_0609/execution.py`；`tests/integration/test_luxian_0609_all_rules_three_entry_acceptance.py` | 三入口测试保留生产路由、BackgroundTask、detached worker 与聚合交付，并禁止正式入口走 legacy adapter；本轮仅核对，未跑整条链 |
| 保存与失败交付 | `custom_qc_workspace_service.py:4968`、`qc_workspace/canonical_result_store.py`；`test_luxian_0609_result_persistence_contract.py`、`test_luxian_0609_attempt_boundary_audit.py` | 任务完成和 Envelope 同事务；合同非法/保存失败回滚；取消或旧 attempt 不得发布新结果。本轮选中的同步保存/代次用例通过 |
| latest、批详情与一致性 | `qc_sichuan.py:2404`、`:2451`；`luxian_0609/record_result_read_model.py`；`test_luxian_0609_record_result_read_model.py`及三入口集成测试 | latest 按病例三坐标与权威代次选择，批详情校验 Canonical；整链测试核对保存内容与 latest/详情一致，并含坏合同 409。本轮选择规则的同步单测通过，API 门禁待最终 SHA 重跑 |
| HTML/CSV/XLSX 导出 | `custom_qc_workspace_service.py:5238`、`:5447`、`:5549`；`luxian_0609_result_export_service.py`、`qc_workspace/export_service.py`；`test_qc_sichuan_record_result_exports.py`、`test_custom_qc_workspace_export_html.py`及三入口集成测试 | 正式 0609 导出从 Canonical 取数据；已有坐标、权限、筛选冻结、客户安全文本、长文本完整保留测试。三种格式与 latest/详情的最终候选一致性仍需重跑 |
| 重试、取消与重启 | `custom_qc_workspace_service.py:4349`、`:4466`、`:4682`、`:4748`；`test_qc_sichuan_batch_cancel.py`、`test_luxian_0609_attempt_boundary_audit.py`、`test_luxian_0609_task_restart_persistence.py`；隔离 PG 竞态测试已存在 | 0609 claim/retry 带冻结代次，旧 worker 不能写新任务；父子重试与回读有保护。本轮选中的同步用例通过；跨进程恢复/续租和真实行锁竞态未执行，不能由 SQLite 通过替代 |
| 历史兼容与访问控制 | `qc_sichuan.py:550`、`qc_workspace/canonical_result_store.py`；`test_qc_sichuan_saved_result_access.py`、`test_luxian_0609_read_side_projection_boundary.py`及三入口集成测试 | 旧文件 detail/history/latest 共用安全读取边界；旧任务缺合法快照不得继续正式执行；读取合同非法时受控拒绝，不能从展示文案重判历史结果。本轮只核对覆盖，未重新执行历史文件/API 用例 |

上表的 backend 路径前缀均为 `apps/medqc-web/backend/`；测试除显式 integration 外均在 `tests/unit/`。

## 本轮实际执行

1. 交付局部组：**31 passed in 33.39s**。文件为 `test_customer_agent_runtime_package.py`、`test_verify_release_source.py`、`test_release_baseline_inventory.py`、`test_customer_release_db_preflight_contract.py`。
   - 使用 `python -B -m pytest --noconftest -p no:cacheprovider -o addopts= -q ... --basetemp=.tmp/engine-audit-20261008/pipeline-release/pytest-release`，未载入共享 conftest。
   - 经源码核对，PowerShell 子进程只运行合成目录的复制/构建门禁片段、合成启动器及语法解析，不执行真实构建、迁移、激活或服务启动。
   - 日志：`.tmp/engine-audit-20261008/pipeline-release/release-tests.log`。
2. 公共合同同步组：**36 passed, 30 deselected, 69 warnings in 12.30s**。
   - 用独占 `run_safe_existing.py` 执行上述快照、运行身份、read model、持久化合同、attempt boundary 五个已有测试文件中的同步选择集；另明确排除 15 个异步用例。
   - 导入前移除真实配置环境，阻断 `.env` 文件读取和网络访问；提供隔离 SQLite 连接模块，沿已有隔离测试的边界跳过 PG 初始化 DDL。没有加载应用启动生命周期或调用真实模型。
   - 日志：`.tmp/engine-audit-20261008/pipeline-release/pipeline-sync-final.log`。告警包括未加载异步插件后的未知 async 标记和既有依赖告警，不是通过异步用例的证据。

安全运行器建立期间还有两轮受扰日志：第一轮 16 failed/28 passed，原因是选择器误选异步测试及硬拒绝默认连接；第二轮 8 failed/28 passed，原因是 PG 初始化 DDL 在 SQLite 上无法执行。两轮均保留在 `pipeline-tests.log`、`pipeline-sync-tests.log`，归类为运行器适配失败，不作为生产缺陷或正式回归结果。最终仅采用 `pipeline-sync-final.log`；没有修改共享测试来消除失败。

## 交付前置审查及候选 SHA 仍缺门禁

已核对 `scripts/package-customer-release.ps1`、`scripts/customer-db-preflight.ps1`、`backend/start_dev_backend.ps1`、`backend/app/services/llm_config_loader.py`及脱敏交付文档。

| 门禁 | 已有代码/文档证据 | 最终候选仍需的证据 |
| --- | --- | --- |
| 固定源码与构建身份 | dirty source 拒绝；失败构建和 stale dist 拒绝；包内 build identity 有合同测试 | 冻结最终完整 SHA，在干净来源构建，核对 frontend/backend/API 同一 build_id 与 SHA，输出包文件清单和 SHA256；本轮未实际打包 |
| 文件白名单及离线依赖 | 助手 runtime 六文件白名单、锁文件和父级 package.json；密钥/会话排除 | 实际客户 OS/架构、Python/Node、离线 npm/Python 依赖及持久化目录安装/重启复验；源码 ZIP 不能当成开箱即用离线安装包 |
| PG 迁移与结构 | 只读 preflight 合同、Alembic current/heads 文档和 acceptance 启动结构检查测试存在 | 客户备份、升级步骤、权限和迁移后的结构/索引证据；本轮未连接 PG、未执行迁移。SQLite 不证明 PG 行锁竞态或升级通过 |
| 产品授权 | required activation、签发私钥排除、一次 bootstrap 安装及保留既有状态有测试 | 客户有效授权、到期/篡改/重启保护及授权文件路径验证；本轮未签发或使用真实授权 |
| 模型配置与行为边界 | provider/model 参数与敏感 endpoint/key 来源区分；0609 runtime identity 不落密钥且拒绝漂移有测试 | 获授权后在实际客户模型配置验证可达性、超时、失败回退与使用量；本轮零真实模型调用，不评价准确率 |
| 0609 正式链完整候选复验 | 正式三入口、保存→latest/详情→三种导出、重试取消、历史兼容及重启测试已存在 | 最终 SHA 在经核对的隔离运行器中重跑这些清单，记录完整命令、配置边界及结果；不能直接从普通 pytest 导入真实 `.env` 或启动真实恢复任务 |
| 前端与角色操作 | 根 AGENTS 编码/lint/type-check/unit 门禁及既有角色验收记录 | 最终 SHA 的规定工程检查及目标包角色业务操作；本代理没有浏览器或前端工程执行证据 |

历史脱敏记录 `docs/plans/2026-10-06-customer-package-preflight.md` 和 `2026-10-06-customer-preflight-closeout.md` 在应用目录下，描述的是旧固定 SHA 的有限试包/工程收尾。其授权、模型、PG、临床与客户部署限制必须保留，不能用其旧结果替代 `6930540f27e9c279241d35ac05d1c1c6e9134f82` 或后续最终候选的产物门禁。

## 问题与索引

- 本范围新增确认生产缺陷：**0**；本代理修复 SHA：**无**；独立复审：**未执行，不宣称已有独立复审通过**。
- 剩余项是上述候选产物/完整链/客户环境门禁，状态 `pending_final_candidate_gates`；不将客户链缺失表述为未审，不将局部通过表述为整套引擎或部署已通过。
- 机器索引：`docs/acceptance/engine-audit-20261008/pipeline-release.json`。
- 本代理只写上述两份报告和独占 `.tmp/engine-audit-20261008/pipeline-release/`，保留其他代理及用户修改。
