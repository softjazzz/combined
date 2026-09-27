# MedQC V3.6 长程任务交接（2026-09-27）

> 接手更新：下文保留Claude暂停时的历史交接快照。Codex已接续P2-R1补齐报表代码，当前状态以滚动计划§87为准；终末归档未核实保持阻塞。未写库或清理种子，隔离库只读确认revision62，非空病例及登录后浏览器验收仍待完成。业务库若仍为revision44，完整部署迁移链为45–62。

> 本文面向接手的下一个 Agent。先读本文，再读以下三份：
> - `docs/PRD-内涵质控V3.6总需求与差距矩阵.md`
> - `docs/plans/2026-09-22-v36-manual-capability-rolling-plan.md` 最新几节（§72–§86）
> - `apps/medqc-web/AGENTS.md`

## 1. 任务与授权（用户原话口径）

**目标**：用户要求以长程 goal 方式完成 PRD 矩阵全部 80 项，顺序为 P0→P1→P2→P3。全部完成后由用户统一测试验收。

**范围**：不包括质控引擎整改或重写。

**授权**（对整个长程任务有效）：

- 隔离库 `medqc_v36_validation_20260924` 可以：
  - 按序执行新迁移；
  - 写入和清理 `SYN-` 前缀的合成数据。
- 业务库 `medqc` 始终只读。
- 不推送。

**外部阻塞的处理方式**：做成可配置接口，失败关闭，用合成数据验证；矩阵标“阻塞：缺 X”后跳过；最后统一列清单。

**汇报**：进度按“代码完成 / 非生产验证 / 业务库部署 / 真实病例与浏览器验收”四栏分列。未经验收不提升 PRD 覆盖状态。

**提交**：

- 中文提交信息，末尾附 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`。
- 按路径暂存，提交前检查 `git diff --cached --name-only`。
- 不用 `--no-verify`。

**回复**：一律用中文。

**已决事项**：

- 病历初审/复审 owner 绑定到“一次已保存、含来源与三坐标的质控结果”。
- 规则管理按“规则集版本发布”实现。
- 评分做“评分标准配置，默认不启用”：未配置时显示“未配置评分标准”，不伪造分数。
- 浏览器验收用纯合成数据，由用户本人登录。

## 2. 环境要点

- 仓库：`C:\Users\Coldplay\.codex\worktrees\3fa6\LX888`。应用目录：`apps/medqc-web`。分支：`codex/v36-manual-gap-drilldown-20260922`。最新提交为 `8e1af54e9`。
- lint 只读命令（`npm run lint` 会带 `--fix` 改写文件，不要用）：
  `npx eslint src --ext .vue,.js,.jsx,.cjs,.mjs,.ts,.tsx,.cts,.mts --quiet`
- 其他前端检查：`npm run check:encoding`、`npm run type-check`（vue-tsc）、`npm run test:unit`。
  - Vitest 已在 `vitest.config.ts` 固定 `TZ=Asia/Shanghai`。本机系统时区现为 America/Chicago。
- 隔离库冒烟：**必须在 import app 之前**把 `DATABASE_URL` 设为隔离库，并断言 `current_database()`。曾因默认会话误读业务库，见滚动计划 §84。凭据只从 `backend/.env` 读取。
  - 隔离库当前 revision 为 `20260927_000062`。
  - 业务库记录仍在 revision 44。部署前先实测 revision；若仍为44，须按序执行完整迁移45–62，不能从52开始。
- 后端既存失败：
  - `test_prd_acceptance.py` 有 8 条失败，已对照 HEAD 确认是既存问题；
  - 另有一批其他范围的既存失败，与本任务无关。
- 隔离库中的合成种子**尚未清理**，浏览器验收结束后按授权清理：
  - `syn_remote` schema；
  - 用户 `syn_v36_manager` / `syn_v36_staff`；
  - `qc.sync_config_registry` 中 sync/pg_source_config 那一行。
  - 种子脚本：`.tmp/0910-full-audit/v36-syn-browser-seed.py`。

## 3. 已完成（代码完成 + 隔离库验证；均未做业务库部署和浏览器验收）

| 阶段 | 内容 | 设计文档 |
|---|---|---|
| P0 | 病历初审/复审（`qc_record_reviews`）、人工缺陷审核、首页待办计数、列表审核状态筛选、详情联审与前后翻、病例人工缺陷、操作记录 | `2026-09-26-v36-record-review-and-manual-defect-review-design.md`、`2026-09-27-v36-case-operation-timeline-design.md` |
| P1 | 筛选模板、工作表现排名、导出对齐、分配策略、角色分流、规则集版本发布全链、质控点管理 UI、测试病历真实化 | `2026-09-27-v36-*-design.md`（filter-templates / performance-ranking / task-assignment-strategies / rule-set-version-publish / test-records） |
| P2-S | 评分标准配置与计分服务（前后端）、V5 列表得分列、结果抽屉计分面板 | `2026-09-27-v36-scoring-standards-design.md` |

## 4. 进行中（未提交）：P2-R1 病历质量分析报表

合同文档（已写，未提交）：`docs/plans/2026-09-27-v36-record-quality-report-design.md`。它覆盖以下四项：

- 运行病历质量分析
- 终末病历质量分析
- 全院各科室病历质量详情
- 缺陷详情分析（规则、文书、缺陷等级维度）

**已写的代码**（未提交，也未测试）：

1. `backend/app/services/manual_defect_review_service.py`
   - 新增 `list_manual_defects_for_cases(identities)`：按 visit_id 分块，按三坐标精确过滤，只返回三坐标、rule_code、审核状态。
2. `backend/app/services/record_quality_report_service.py`（新文件，语法检查通过）
   - `build_report_context(...)`：各读取器可注入；按范围取病例，再读结果、计分、审核状态、人工缺陷。
   - `summarize(ctx)`：计算 KPI、等级/得分分布、缺陷等级/文书分布、四维 top20、科室与医生明细、不可用维度。
   - 事实来源：
     - 范围复用 `workstation/luxian_0609_result_analysis_service._load_current_workstation_records`；
     - 结果用读取器的 `include_items=True`，并经 `project_customer_items` 投影；
     - 计分直接调用纯函数 `score_result` 和场景默认标准；
     - 审核状态用 `batch_review_states`，锚点来自 `build_review_anchors`；
     - 规则名称和文书来自 `luxian_0609_rule_master`，缺陷等级来自目录的 `defect_level`。
   - **提交前请复审**：最后一次批量编辑后，文件在磁盘上又被改动过，需要先 Read 当前内容再确认。

**剩余步骤**：

1. 在服务中补 `records_page(ctx, department/doctor/rule_id/document/grade/has_defect, page, page_size)`，用于病例下钻；再补 `export_csv(ctx, sheet)`（UTF-8 BOM）。
2. 新建路由 `backend/app/routers/quality_reports.py`，前缀 `/api/v1/quality-reports`：
   - 角色为 admin 和 qc_manager（`require_role`）；
   - 数据范围用 `resolve_workstation_data_scope`；
   - 端点为 `GET /record-quality`、`/record-quality/records`、`/record-quality/export`（导出写 `audit_event`）；
   - 错误映射：参数非法 → 422；范围过大（`RecordQualityReportTooLarge`）→ 422 `range_too_large`；读取故障 → 脱敏 503。
   - 在 `main.py` 注册路由；照现有新路由的做法补路由权限对齐测试。
3. 编写 pytest，全部注入读取器，不连库。至少覆盖：
   - 未配置标准时得分类指标为 null；
   - 否决计数；
   - 人工缺陷驳回不计入；
   - `defect_source` 筛选；
   - 审核或人工缺陷读取失败时只降级对应指标；
   - 时间窗口过滤；
   - 超过上限；
   - 投影异常计入不可用。
   - 随后跑 Ruff。
4. 前端：
   - 新增 `src/api/qualityReports.ts`、视图 `src/views/qc/reports/RecordQualityReportView.vue`，路由 `/dashboard/qc/reports/record-quality?scene=running|final`；
   - `MainLayout.vue` 中“统计分析”改为子菜单：统计概览 / 运行病历质量 / 终末病历质量；
   - 页面分区为总览 / 筛选 / 分布 / 明细 / 导出。未配置标准时显示“未配置评分标准”；整改状态和核心制度显示“未接入”；
   - 明细表列选择存 localStorage，读写包 try/catch；
   - 补 Vitest。
5. 隔离库冒烟：用合成病例跑一次端点，核对库名。然后完成四项检查，更新滚动计划（新增 §87）和 PRD 矩阵日期注记，最后提交。

## 5. 之后的待办（按顺序）

- **P2-R2 质控员分析**（运行和终末）与人工质控报表。
  - 数据来源：
    - `qc_record_reviews`，按审核人、阶段统计；
    - 人工缺陷创建、通过、驳回；
    - 申诉通过、驳回。
  - 可复用 `performance_ranking_service.py` 的窗口口径。
- **P2 其他项**：
  - 病案首页统计：首页质控结果的 owner 不同，需先调查。
  - 病案管理 27 项指标：逐项确认公式与数据源，缺数据的标阻塞。
  - 自定义列：服务端用户级列配置持久化，可参考 `qc_user_filter_templates` 的做法。
  - 定时任务：调度、启停、执行记录。
  - 编码质控点管理。
  - 测试病历导出、复制、删除（删除须权限、确认和审计）。
  - 零数量反馈。
  - 评分“重新设为默认”端点。
- **P3**：
  - 特殊病历报表：阻塞，缺定义。
  - 运行及时率：阻塞，缺指标合同。
  - 文书列表、导入、搜索。
- **Backlog**：
  - CI 安全门禁 `test_security_hardening::test_password_reset_token_is_one_time` 失败。
  - V5 工作列表与首页助手的医生数据范围要改用 `resolve_workstation_data_scope`。
  - 样本验证派生副本存在假人口学信息和 8 小时偏移。

## 6. 外部阻塞清单（最后统一交用户）

- 归档来源 `archive_sign`：影响终末列表和批量处理。
- 门急诊身份与规则集。
- 医生映射与通知通道：影响催办和通知。
- 短信/扫码登录。
- 核心制度归类。
- 整改状态 owner 与“七类整改状态”口径。
- 命中片段精确定位：属于引擎范围。
- 金标答案。
- 测试病历 Excel 模板。
- “其他”文书映射。
- 新建质控点需要执行器实现。

**部署前提**：

- 业务库先实测 revision；若仍为44，按序执行迁移45–62。
- 医生 `sys_users.department` 与病例科室名须完全一致。
