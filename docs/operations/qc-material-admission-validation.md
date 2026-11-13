# 取材前置预检与失败展示：开发侧交付

> 2026-11-13 后续修订：正常新任务已改为自动一致性读取，不再要求人工 `QC_CDM_CAPTURE_WINDOW_UNTIL`。下文保留为前一版验证/交接记录；当前方案以 [自动取材交付说明](qc-automatic-cdm-material.md) 为准。任务级技术失败和历史保护仍保留。

基线：7ac3b0f3a；独立分支 codex/qc-material-preflight-20261113。

## 变更

- create_batch_job 在服务端冻结来源后、任务 insert 前复用发布窗口校验。普通独立CDM任务缺窗口或过期时拒绝；两个创建路由返回409及白名单中文根因。
- 捕获执行时再次校验，避免排队过期；旧快照 obtain 优先读取与原补跑缺快照保护不变，1026材料入口不改。
- 捕获/投影失败直接结束该病历准备阶段，不进入规则循环；一份病例对应一次准备失败。
- 混合批次保留其他病例已返回的结果；补跑材料失败不进入规则级合并，不覆盖原成功和原pending。
- 客户DTO重建安全错误消息，不透传异常原文。页面优先显示材料根因；材料失败时计数展示“已返回规则结果”，不把计划规则数当已执行数。没有重试字段时只说明未返回计划。
- 不重写历史任务、快照、冻结或历史结果；旧任务原有计数不批量重算。

## 定向验证

禁 dotenv、禁网络、禁非合成SQLite的 runner：
`python apps/medqc-web/backend/scripts/run_pr8_offline_tests.py tests/unit/test_qc_material_admission.py tests/unit/test_custom_qc_workspace_batch_record_refs.py tests/unit/test_failed_rule_retry.py tests/unit/test_case_material_snapshot.py tests/unit/test_daily_material_projection.py`

115项通过。包含窗口非法/缺失/过期、拒绝任务写入、正式LX0609首次执行与缺原快照补跑（真实冻结配置合同）、成功结果保留、真实SQLite进度保存/失败收尾/客户DTO读回，历史行保持不变。

前端三个文件54项通过：batchJobStatus.spec.ts、RecordPoolQcTaskStatusBar.spec.ts、batchJobPresentation.spec.ts。新增实际组件断言：根因可见，0/76而非76已执行。
复用本机node_modules；临时Vitest配置仅指定这三个文件、关闭PostCSS，并将缺失的图标包解析到本机已有lucide-vue-next。未安装依赖，临时配置不提交。

先观察新增红灯再实现。已有前端两处旧文案断言按新“未返回计划”改写，重试状态和成功结果保护断言保留；旧worker测试替身补齐真实进度保存接口的items/failed_records参数。

较宽的throughput+daily两文件组合：候选90通过、28失败。导出7ac3b0f3a到独立临时目录同命令得到90通过、28失败，失败项集合完全相同；涉及旧测试未提供当前任务冻结配置等，不算本次全绿。未改这些失败断言。

独立复审先发现补跑合并误接收无rule_id材料失败、预初始化rule_stats误计数；均已修复，复核未确认新P1/P2。复审只读代码，测试由实现方运行。

## 尚未成立的现场条件

同步侧尚需确认目标病例身份/发布批次与领域范围/供给缺口/稳定性及窗口。指令见同目录 qc-single-case-material-sync-handoff.md，已直接发送到“🐮🐮🐮数据对接”。当前配置是全局截止时间，不能把单病例回执当作全库验收或自动范围锁。本次没有新增机器发布回执协议，没有伪造窗口。

代码与隔离验证通过不等于现场可取材。没有部署、业务库连接、真实模型调用、质控运行或27份重跑；没有合并或推送。
