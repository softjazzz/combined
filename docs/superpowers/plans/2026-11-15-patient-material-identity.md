# 患者级材料身份合同 Implementation Plan

**Goal:** 修复patient_information两键表不能捕获/读取的问题，不放宽就诊文书三键或来源绑定。

**Architecture:** 仅patient_information允许机构+患者两键；若存在visit_id仍使用三键。预检、实际SQL、PDF捕获与新快照回放复用同一身份列函数。可信登记仍在同一只读事务绑定完整就诊身份，禁止伪造visit_id或回查当前来源补造历史。

**Tech Stack:** Python、SQLAlchemy、合成SQLite及受控事务替身。

## 授权与边界

用户已明确选定修复方案。基线9f48b3435，独立分支codex/patient-material-identity-20261115；原API工作树不修改/重启。无首页取材、手术输血暂停及历史结果不改；不连真实库、模型、运行质控、合并或部署。

## 实施

- [x] 新增红例：两键患者表实际查询/捕获/冻结读回；跨机构、患者、来源、schema及就诊上下文拒绝；临床表缺visit/患者/机构仍拒绝；患者表带visit时不得跨就诊读取。
- [x] clinical_source_contract共用身份列函数，并让两键患者表预检覆盖实际读取字段权限。
- [x] assembly实际查询使用明确的患者键，不添visit；新PDF捕获保存逐表身份列合同并校验行身份。
- [x] frozen_rows仅对带新合同的快照校验逐表身份；无新合同的历史保持旧读取行为，不回填。
- [x] 最小定向验证、未参与实现的独立复审、diff/编码检查后统一本地提交；不推送。

## 实现与验证

- 共用material_identity_columns只为patient_information提供两键合同；有真实visit列时仍要求三键。实际SQL及PDF捕获同时校验返回行，拒绝缺键、跨机构/患者/就诊，不添加或改写行字段。
- PDF新快照read_contract.table_identity_columns记录真实身份范围，frozen_rows校验预期合同、列和行；完整任务三坐标与来源binding仍先校验。旧快照没有该字段时沿旧路径，未写入或补造。
- 两键患者表此前预检仅检查键列，现复用真实字段投影，姓名/联系方式等实际读取列也必须获准；不扩大可用来源或权限。
- 先红：10 failed/5 passed，复现患者表读空、捕获三键拒绝、权限投影遗漏及新合同行校验缺失。首轮补修15通过。
- 最终最小集合：test_patient_material_identity.py、test_pdf_case_material_snapshot.py、test_case_material_snapshot.py、test_validation_material_snapshot_aux.py，共83通过，3项既有警告。包含实际内存SQLite精确过滤、真实画像冻结读取、可信登记同只读事务的受控替身和旧快照保护；无真实模型或真实质控。
- 独立复审无可确认P1/P2；审查机构/患者/来源边界、未知表缺键拒绝、旧历史及暂停保护，复用定向结果未重复测试。
- diff、Python语法、UTF-8无BOM/LF通过。原工作树、API、配置、运行冻结目录未修改或读取。

## 验证限制

只运行合成数据测试，不读取真实病例、配置、旧快照或运行冻结目录。不把SQLite/事务替身当作真实PG并发验证。

本轮未实测真实PostgreSQL列级权限、RR并发和真实1026端到端；未重新验收本地病例，先前失败任务保持原状。
