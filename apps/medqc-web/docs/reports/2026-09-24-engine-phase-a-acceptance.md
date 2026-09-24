# LX0609 引擎阶段 A：两试点证据与验收边界

审计日期：2026-09-24。代码基线为 `a832ebdb2b5d4c4c74dccc060f9ab3b2a5970dde`（2026-09-23 15:01 +08:00），其祖先 `7cbadaf39f2eca7a6bb56f8895eb30a54b699568` 已修复两试点的事实重复投影故障。阶段 A 发布边界提交为 `a163a910c794ae862339c800f7c7a760a5d65cac`（2026-09-23 15:45 +08:00）；本轮测试的集成树 HEAD 为 `31109f8bd8ff45211882c7ebb85c76ad6398ecb1`（2026-09-23 22:49 +08:00）。这不是临床零回退的签收报告。

## 保护集合现状

试点：抢救记录内容完整性 `LX0609-09-01-02`、病理报告完整性 `LX0609-06-02-01`。当前可重复执行的保护集合是代码级固定事实与合同断言，分别覆盖两试点的状态、原因、非空事实、非法公开结构拒绝、Canonical 往返。合并执行下述聚焦命令有 124 项通过；该计数包含其他同文件测试，不能解释为 124 份真实病例。

不能将现有历史材料宣称为已签收医学保护集：

- `docs/0602/泸县0609质控点-golden-cases.json` 的 49 条规则均有 `cases` 容器，但三类病例数组均为空。
- `docs/acceptance/lx0609-golden/shadow45-review-v1.csv` 有 900 行，`accepted_at`、`review_status`、`expected_state` 均为空；`review20-v1.csv` 为空。
- `docs/0602/luxian_0609_auto_candidate_review_queue.csv` 97 行、`luxian_0609_golden_review_queue.csv` 81 行、`luxian_0609_golden_review_queue_merged.csv` 178 行，`review_status` 均为 `pending`。`泸县0609真实样本GoldenSet标注表.csv` 28 行，其中 25 行 `pending`、3 行 `sample_gap`。这些是候选及待审台账，不是签收结论。
- 集成工作树 `.tmp/0910-full-audit/` 只有 CT 规则的当前固定输入/响应。主工作区同目录存在旧抢救、病理探查脚本及 019 病理提示词脚本，但未找到当前两条四段式规则在上述代码 SHA 下可直接重放的真实病例材料与固定模型响应。未读取或复制患者原文；CT 的 30 份回放未计入阶段 A。

因此，全 79 条已验收记录和台账中全部 `compliant/non_compliant` 记录的按 SHA、产物时点划定保护集合尚未建立。需在真实材料和独立业务答案齐备后另行冻结，不能以代码级断言代替。

## 已核对的交付链

内部事实由两试点所属执行器生成；`canonical_result_finalizer.py` 验证并生成公开事实；`CanonicalResultStore.replace_for_job` 校验/写入 Envelope，`load_selected` 校验公开事实后读取；`CustomQCWorkspaceService` 的任务与 latest-result 入口投影客户安全结果；`ResultFeedbackDemoStore` 按 root job、record_ref、rule_id 从 Canonical 绑定当前状态及事实摘要；批量 CSV/XLSX/HTML 共用客户结果安全投影。源代码中反馈 Store 读取 Canonical，仅写反馈表。

本轮新增 `test_two_published_pilots_keep_identity_through_sqlite_feedback_and_exports`：使用不含患者资料的两条公开结果，在隔离 SQLite 真实执行 Canonical INSERT/SELECT 与反馈表 INSERT/SELECT，验证同一 root job、记录引用、规则身份、原状态及结果 digest；再逐一核对任务安全投影、CSV/XLSX/HTML 的规则编号和结论。已有 `test_rescue_non_compliant_safe_facts_survive_canonical_write_and_task_projection`、`test_pathology_published_facts_commit_and_read_without_reprojection` 覆盖不合规/资料不足的独立 SQLite 读回。执行器→Finalizer 的既有测试与本轮新测试是两段证据，不能合称一份真实病例贯通所有入口。

验证命令（在 `backend/`；设置测试用 `JWT_SECRET` 和 `DATABASE_URL=postgresql://test:test@127.0.0.1:5432/test`）：

```powershell
python -X utf8 -m pytest -q -o addopts='' --tb=short --no-showlocals --disable-warnings `
  tests/unit/test_luxian_0609_pathology_report_completeness.py `
  tests/unit/test_luxian_0609_rescue_record_completeness.py `
  tests/unit/test_luxian_0609_basic_timeliness_customer_projection.py `
  tests/unit/test_luxian_0609_canonical_result_delivery.py::test_rescue_non_compliant_safe_facts_survive_canonical_write_and_task_projection `
  tests/unit/test_luxian_0609_canonical_result_delivery.py::test_pathology_published_facts_commit_and_read_without_reprojection `
  tests/unit/test_luxian_0609_canonical_result_delivery.py::test_two_published_pilots_keep_identity_through_sqlite_feedback_and_exports
```

结果：退出码 0，124 passed；新增 SQLite 反馈/导出测试单独执行 1 passed，退出码 0。`ruff check` 修改的测试文件通过，`git diff --check` 通过。纯投影、持久化和导出测试没有调用 LLM，新增调用 0、Token 0；未改变生产判定、模型输入或并发配置。

扩展执行整个 `test_luxian_0609_canonical_result_delivery.py` 时，首个失败为 `CustomQCWorkspaceService.__init__` 经 `_drafts_table().metadata.create_all` 尝试连接测试环境 PostgreSQL，出现 `psycopg2.OperationalError`；之前 15 项通过。故未将中断的广域运行计为业务回归，也未声称这组测试完全脱库。

## 未关闭的验收

1. 固定当前 SHA 的真实非空抢救、病理事件材料、模型原响应、规则版本、评价时点和独立业务答案，建立保护集合并重放；按病例逐项比较状态、原因、事实、证据、调用/Token 与耗时。
2. 真实 PostgreSQL 事务/权限、批量任务详情与 latest-result API、反馈 API、客户页面和下载文件的联合验收。本轮 SQLite 与内存渲染不证明部署环境可用。
3. A4 独立复核及客户医学验收。阶段 A 暂不关闭；不得据此启动 B/C/D 或默认启用新增 CT 规则。

## 主协调独立复核

2026-09-24：审查新增测试实际调用Canonical与反馈Store，不mock待验证合同。按上列命令独立复跑124 passed（4.01秒，退出码0），Ruff和diff检查通过。独立读取shadow45/review20/merged台账验证900行空状态、0行、178行pending。此次仅新增测试及文档，无生产代码、Prompt、模型配置或前端变化；前端检查沿用31109f8bd的结果，不宣称本轮重跑。已重新派发有界只读PG源材料准备任务；候选不等于医学金标准。
