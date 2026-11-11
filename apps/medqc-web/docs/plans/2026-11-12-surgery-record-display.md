# 手术记录业务读取与展示补齐

基线：d65d8148d；独立分支codex/cdm-record-view-20261110。同步接入由同步Agent负责。

## 修改

- 保留surgery_process完整内容和内部换行，直接以字段渲染，避免标签解析把冒号或换行误拆。
- surgery_begin/end_time与源surgery_begin/end_datetime均可选择、展示和定位；同时有值时分别保留，不任取一个掩盖差异。未修改数据库类型、同步映射或质控时间合同。
- 原始document_status从Bundle传到文书渲染和前端，不把Save等未知状态解释为签署完成。既有明确无效状态过滤不改。
- 身份/提交时间/模板标签不能单独生成临床正文；源正文和有意义临床字段均无值时显示空文书。
- 正文记录时间不再借用提交/修改时间；这些时间各自单列。前端依据现有时间来源标记显示“提交时间”或“显示时间（回退）”。
- 三坐标和document_id定位不改。不会按同日术式合并不同文书。

## 验证

禁网入口：python scripts/run_pr8_offline_tests.py tests/unit/test_surgery_record_current_display.py tests/unit/test_document_assembly_surgery_record.py tests/unit/test_bundle_emr_view.py
结果41通过。新增5项修复前4失败、1对照通过；修复后全部通过。链路到文书装配/Bundle文书标准化/渲染，不是现场HTTP或数据库验收。
前端：node node_modules/vitest/vitest.mjs run tests/unit/components/EMRViewer.spec.ts --config vitest.config.ts --maxWorkers=1 --minWorkers=1 --reporter=dot
结果7通过；固定响应挂载验证源状态、提交时间标签、完整多行手术经过。
不连接业务库、不调用模型、不跑质控、不重跑27份、不改同步服务、不涉及0916。不修改历史结果或旧冻结，不打包部署。

## 同步侧交接与剩余限制

正文直接发布到surgery_process，record_content保持原值。不得为显示而覆盖record_content。
时间映射须保留字段语义和精度，不能以提交时间代替手术时间；两套时间冲突时本轮分别展示，不替同步方裁决。
需要同步侧确认稳定且非空的四坐标、同文书修订和状态字典。不同日期可取数、目标病例确有记录、现场发布及实际浏览器显示尚未验收。
本轮不证明49个源字段全部已展示；当前专门补齐手术经过、时间、状态、文书定位。未新增存储迁移或冻结版本。
