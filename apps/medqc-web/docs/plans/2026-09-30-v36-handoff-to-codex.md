# MedQC V3.6 长程任务交接给 Codex（2026-09-30）

> 接手者先读本文，再读：`apps/medqc-web/AGENTS.md`、`docs/PRD-内涵质控V3.6总需求与差距矩阵.md`、`docs/plans/2026-09-27-v36-prd-80-code-completion-audit.md`（80 项代码账本，**唯一进度入口**）、`docs/plans/2026-09-22-v36-manual-capability-rolling-plan.md` 第 118–122 节。上一份交接：`docs/plans/2026-09-27-v36-handoff-to-next-agent.md`（其中“进行中”部分已完成，以本文为准）。

## 1. 目标、授权与约束（用户原话口径）

- 长程目标：完成 PRD 矩阵 80 项，顺序 P0→P3；完成后由用户统一测试验收。范围**不含**质控引擎整改或重写。
- 进度按“代码完成 / 非生产验证 / 业务库部署 / 真实病例与浏览器验收”四栏分列；未达验收不提升 PRD 矩阵覆盖状态（账本只评代码）。
- 数据库：业务库 `medqc` 只读；隔离库 `medqc_v36_validation_20260924` 可执行新迁移、写入/清理 `SYN-` 前缀合成数据（整个长程任务有效）。**不推送**。
- 提交：中文信息，末尾 `Co-Authored-By` 行；按路径暂存，先看 `git diff --cached --name-only`；**不用 `--no-verify`**。删除、强推、全局安装、数据库写入需用户明确授权（隔离库合成数据除外）。
- 一个事实一个 owner；未知显示未知，不伪造 0/通过；三坐标（institute/patient/visit）为病例身份。
- 已决口径：
  - 病历初审/复审 owner 绑定已保存质控结果；评分“配置默认不启用”，未配置显示“未配置评分标准”。
  - **终末口径 B（2026-09-30）**：归档来源 archive_sign 未接入前，终末 = 已出院（未核验归档），运行 = 当前在院；已推广到报表、列表、批量质控、导出、抽查任务；统一策略在 `backend/app/core/final_scope_policy.py`，归档来源接入后在此收窄。
  - 申诉口径（见未提交文档 `docs/plans/2026-09-28-v36-appeal-next-batch.md` 末节，属另一会话）：医生可申诉本科室病例的已确认自动缺陷与审核通过的人工缺陷；医生科室以管理员维护为准。

## 2. 当前进度

- 主工作树：`C:\Users\Coldplay\.codex\worktrees\3fa6\LX888`，分支 `codex/v36-manual-gap-drilldown-20260922`，HEAD `3e6587da4`（本文提交后前进一个提交）。
- 账本：**42 完整 / 24 部分 / 14 未实现（52.5%）**；长程 Goal 目标 64/80，差 22 项。
- 本会话（2026-09-30）已提交：`38fedb088` 断言同步摘入、`6e4ae21f2` 编码门禁钩子修复、`2b952ddec` 测试外呼隔离与过期断言、`b1f2cb02a` 注册密码下限、`db102b57c` 真实 LLM 用例默认跳过与测试基线、`eea48b7c0` 终末报表口径 B、`e505a65ca` 病案首页统计（47）、`5fb371860` 终末口径 B 推广（30/31/32/34）、`3808fdd77` 终末抽查任务按已出院抽样（38）、`3e6587da4` 今日在院用例时区修复。
- 测试基线：前端 Vitest 2316/2316；后端全量约 12.6k 项，约 311 项既存失败（清单见第 6 节），无新增。

## 3. 并行工作树（本会话新建，均基于 `3e6587da4`，因额度暂停）

| 线  | 目录                                      | 分支                                      | 状态                                                                                                  | 任务（PRD 行）                          |
| --- | ----------------------------------------- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------- | --------------------------------------- |
| A   | `C:\Users\Coldplay\.codex\worktrees\v36a` | `codex/v36-a-score-filter-20260930`       | WIP `1c8e2efcf`（仅 `scoring_service.py` 半改）                                                       | 21：V5 列表按计分状态/等级/分数区间筛选 |
| B   | `C:\Users\Coldplay\.codex\worktrees\v36b` | `codex/v36-b-defect-partitions-20260930`  | WIP `f00548ac5`（新建 `case_defect_partition_service.py`，改 `qc_sichuan.py`）                        | 28：详情五类缺陷分区                    |
| C   | `C:\Users\Coldplay\.codex\worktrees\v36c` | `codex/v36-c-task-case-rerun-20260930`    | WIP `40e611e36`（改 `qc_sichuan.py`、`sichuan_workspace_batch_prepare.py`、`task_qc_run_service.py`） | 36：任务内病例级重新质控闭环            |
| 53  | `C:\Users\Coldplay\.codex\worktrees\v36i` | `codex/v36-53-record-indicators-20260930` | 无改动                                                                                                | 53：病案管理 27 项指标                  |

- WIP 提交**未写合同、未补测试、未跑检查**，接手时先 `git show` 审阅，可在其上继续或 `git reset --soft HEAD~1` 重来（在各自工作树内，不影响主分支）。
- 各工作树已建 `node_modules` 目录链接：根目录 → `D:\LLM\LX888\node_modules`（husky/lint-staged 需要），`apps/medqc-web` → 主工作树的 `apps/medqc-web/node_modules`。
- 完成后合并回 `codex/v36-manual-gap-drilldown-20260922`，合并后跑全量回归，再更新账本与滚动计划（新增第 123 节起）。账本/滚动计划/PRD 矩阵只在主工作树统一改，分支内不改，避免冲突。
- 迁移编号预留：申诉线 72；A 73、B 74、C 75、53 76（各线预计不需要迁移；使用前核对实际 head，当前最新 `20260928_000071_qr_login_sessions`）。

### 各线合同要点（接手按此执行）

- **A（21）**：参照 `query_service.get_workstation_data` 中 `review_state` 的“完整集合先过滤再分页、total/qc_summary 按过滤后集合”模式；得分只来自 `scoring_service`（场景默认标准），不重判；参数 `score_status`（scored/no_standard/unavailable）、`grade`、`score_min`/`score_max`；未配置标准时的语义写清（不伪造），标准不可用 503 脱敏，完整集合上限（如 >5000 例 422 `range_too_large`）；前端 V5 筛选区、URL 同步、重置、筛选模板白名单覆盖新字段。合同文档 `docs/plans/2026-09-30-v36-record-score-filter-design.md`。
- **B（28）**：五分区 owner——全部/确认缺陷=LX0609 Canonical 投影 `is_confirmed_issue`；单否=计分 deductions 的 `is_veto`（未配置标准显示“未配置评分标准”）；人工=`list_case_manual_defects`；编码=现代编码质控 `coding_qc` 本次结果缺陷（无结果“未做编码质控”）；核心=“未接入（缺核心制度归类）”。“精确命中片段定位”属引擎范围不做。合同 `docs/plans/2026-09-30-v36-case-defect-partitions-design.md`。
- **C（36）**：先写清现状缺口（文件:行号）；病例行/多选重跑；受领人只能重跑本人获分配病例，创建人/管理员按现有 run_scope；同病例运行中 job 的并发策略；远端范围任务（运行 active / 终末 discharged）须有覆盖所选病例的成功资料同步回执；进度与结果按 run/job 回读，不伪装完整；job 完成≠任务病历处理完成。合同 `docs/plans/2026-09-30-v36-task-case-rerun-design.md`。
- **53**：先从仓库资料找 27 项定义（以原文为准，不凭记忆），合同逐项写公式/口径/数据来源/可计算性（可计算/部分/阻塞：缺 X）；“2 日归档率/归档完整率”阻塞：缺归档来源；可计算项做 `/api/v1/quality-reports/medical-record-indicators`（汇总/breakdown/cases/export），前端 `/dashboard/qc/reports/medical-record-indicators` 挂“统计分析”子菜单，复用 `src/views/qc/reports/reportPage.css`。合同 `docs/plans/2026-09-30-v36-medical-record-27-indicators-design.md`。

## 4. 待用户决定

1. **39 终末定时计划**：每次运行抽哪段出院窗口？建议“按计划周期抽上一周期出院病例，窗口 ≤31 天”。
2. **40/41**：验收分别为“可通过自定义筛选或指定病历创建任务”“支持全部、总数、比例、科室维度等主要抽样方式”，按验收已满足，但差距栏写“复杂筛选”“手册 10 种方式”。按验收升级，还是补齐手册（需用户提供手册原文）？
3. **42 病历类型分配**：需先查清“病历类型”在数据中的定义与来源。
4. **D:\LLM\LX888\.claude\worktrees 下 4 个 agent-\* 工作树**（`agent-a4e30fc3…`、`agent-acf45cbd…`、`agent-adfffadf…`、`agent-afac9619…`，均基于 `f0d46cc6e`，其一为分支 `agent/v36-modern-appeal-create`）：**每个都有 10–16 个未提交改动**（models/qc.py、scoring、task_sampling、appeals 等），属于另一会话的在途并行工作，**不是**本会话失败留下的空工作树（那 4 个已被自动清理）。用户曾要求删除，但因含未提交工作本会话**未删除**，需用户确认归属后再处理。
5. 已完成工作的清理：临时工作树 `v36a/b/c/i` 在合并后是否删除（需授权）。

## 5. 外部阻塞（最终统一交用户）

归档来源 archive_sign（33、终末收窄）、门急诊身份与规则集（05、44、38 门急诊部分）、医生映射与通知通道（23/29 催办通知）、整改状态 owner 与七类口径（23/27/46）、核心制度归类（28 核心分区、54）、及时率指标合同（56）、特殊病历定义（52）、命中片段精确定位（引擎范围）、金标答案、测试病历 Excel 模板、“其他”文书映射。部署前提：业务库按序执行迁移 52–71（含扫码登录 71），医生 `sys_users.department` 与病例科室名一致。

## 6. 环境与测试要点（踩过的坑）

- **后端测试不要设置 `DATABASE_URL`**：conftest 只在未设置时把 `psycopg2.connect` 替换为立即拒连；设置了会让每次连库在 Windows 上空等约 2 秒，全量跑不完。
- 真实 LLM：`*_real_llm.py` 默认跳过（`MEDQC_ALLOW_REAL_LLM=1` 才运行）；`TestEvaluation` 已阻断外呼。仍建议跑全量时把 LLM 密钥置无效值。
- 离线全量包装脚本（只注入子进程环境、不落盘凭据）：`C:\Users\Coldplay\AppData\Local\Temp\claude\C--Users-Coldplay--codex-worktrees-3fa6-LX888-apps-medqc-web\0d9c46a0-7cfb-4aab-887d-e7e23bc2a73e\scratchpad\run_offline_pytest.py <backend目录> <输出文件> [pytest参数]`；既存失败清单同目录 `fails-all.txt`；隔离库辅助 `vdb.py`（默认只读事务，`--write` 才写）。scratchpad 为临时目录，若已清空按本节自行重建。
- 本机时区为 America/Chicago，医院为 Asia/Shanghai：测试里的“今天”须用医院时区（Vitest 已固定 `TZ=Asia/Shanghai`）。
- 提交钩子：工作树根目录必须有 `node_modules`（链接到 `D:\LLM\LX888\node_modules`）；`check-encoding.mjs` 已修复钩子环境下 `GIT_DIR` 误算仓库根。lint-staged 会对 md/vue/ts 跑 prettier，文档表格可能被重排（仅格式）。
- `npm run lint` 带 `--fix`，用只读 `npx eslint src --ext .vue,.js,.jsx,.cjs,.mjs,.ts,.tsx,.cts,.mts --quiet`。
- 隔离库合成数据未清理项（上一轮浏览器验收种子）：`syn_remote` schema、用户 `syn_v36_manager`/`syn_v36_staff`、`qc.sync_config_registry` 中 sync/pg_source_config 一行；浏览器验收结束后按授权清理。
- 已知限制：编辑草稿接口不允许“指定病历+日期范围”混用，已有“终末+指定病历”任务编辑保存会被拒（第 122 节）。
