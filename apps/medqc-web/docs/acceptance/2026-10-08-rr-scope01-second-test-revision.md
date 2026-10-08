# RR-SCOPE01 第二批目录测试修订

工作树 `F:/MedQC-worktrees/qc-fix-chemo-v2-20261008`，原测试固定基线 `36a3175b4c2ec2a4cc574b15405638ef44c0361a`。本批准备修改 native_package、evidence_snapshot_provider、golden_gate 三个测试文件及本说明。没有修改生产目录 JSON、发布政策、Prompt、化疗、pytest.ini 或 0916。

## 已执行的六节点原始红测

root 授予独占测试槽后，前两个文件字节与固定基线精确相等，采用既有隔离 runner 和真实 pytest.ini（strict-markers），仅关闭外部 conftest；audit guard 拒绝环境凭据文件、网络和真实数据库。收集 6 项，实际 6 项失败，2.20 秒，无过滤/skip/xfail。

| 原节点                               | 实际失败                       |
| ------------------------------------ | ------------------------------ |
| inventory covers all 84              | 实际 inventory85，旧84         |
| inventory native boundary            | async 仅 extra LX0609-08-01-05 |
| stage one consultation compatibility | native8+66，旧73               |
| all enabled with 029 exception       | native8+66，旧73               |
| all79 registered bounded source once | selected85，旧79               |
| bloodtrans identity version          | 全局registry实际v34，旧v33     |

证据 `.tmp/rr-scope01/round2-six-red.xml`。原两个文件 SHA256：native `c5aac9141b35c269d041c59d2dd61e035fe5041e097a749429f90b8bf6aac418`；provider `1fd03590025174516893767c6f5ecf56840f3a66982d815fa08e3cd943fae931`。旧125映射总数、局部血液v2与后续source断言因前面失败尚未执行，不把静态确认冒充实际通过。

## 修订合同

- raw master JSON 决定注册身份与顺序；inventory/catalog/contract 的有序身份精确对照 raw active，不改成85魔数。每条 inventory 的依赖、适用来源、版本和元数据对照独立 raw wrapper。
- 原84项兼容映射从固定 `d897689ca^` 的 master有序身份和两个原wrapper JSON冻结完整 `(rule_id, mapped_rule_ids)` 元组。原84逐项身份/依赖/顺序精确相等且保留累计125；其后新增唯一08-01-05映射必须是自身。历史比较已静态确认没有删除或改变原84任何映射。不以新总数126替代逐项保护。
- family八边界保留；每条规则恰属一族、族成员Counter与raw identity覆盖一致。async显式边界仅补08-01-05，sync/兼容集合不扩大。
- 两个完整门控计划按raw阶段派生有序selected/executable/pending/native集合，并检查同步/异步互斥、完整覆盖。023兼容例外与CL-248/250/071、029兼容例外与CL-181/SC-081保持原样。
- 全注册snapshot测试对照raw active有序ID，保留精确来源调用集合、每source仅一次、无legacy、observations覆盖及query-state合同，未扩大source调用预期。
- 全局registry冻结与血液局部查询版本分开：`ea5ed2b047` 的真实diff已将全局v33升级v34并新增手册来源；血液条目的query_version仍 `snapshot-provider-bloodtrans_record-v2`，source_keys仍 `bloodtrans_record/mr_bloodtrans`，局部不能升v3。全局v34保留literal门禁，不用导出常量与自身比较。

## Golden 候选验收矩阵的语义边界

root 批准第七节点仅按既有运行工件/候选账本合同维护。Golden脚本声明其为正式发布质量门；默认规则从客户可选集合按phase target投影，候选验收矩阵包含五个acceptance_only。这里检查的是待验候选账本/运行清单，不创建普通复检任务。普通业务预览的 `business_actions.py:118–120` 独立拒绝acceptance_only；69/65等默认业务集合冻结不在本批改动范围，不能从Golden候选70推导业务默认启用70。

第七测试改名明确candidate acceptance matrix，预期由raw active减批准五客户排除，再按raw phase拆分。五项acceptance_only身份独立冻结，明确属于候选目标矩阵且与排除项互斥；contracts和runtime manifest有序身份均覆盖raw active，原runtime contract_version/definition/phase漂移拒绝保持。计数只从上述明确身份集合派生，不直接改成80/70/85。

第七原节点已在固定36a3175文件实际执行，1项失败：首断言delivery80与旧72不符；后续原62/77等断言因首失败未执行，不冒称各自另有红测。只备份/恢复自有Golden准备稿，try/finally前后SHA256相等 `631f0ceb84093c8a9fc4f414b702142e1b6d2c38df03c1206de8fe744859bf79`。证据 `.tmp/rr-scope01/round2-golden-red.xml`、`round2-golden-restore-hashes.json`。

修订后三个文件完整运行 **201项全部通过**（native33、provider107、Golden61），没有deselect、skip或xfail；原84映射累计125及逐项依赖、新增自ID、血液局部v2/全局v34、每source查询一次/原source集合、Golden版本及身份拒绝均已实际执行通过。证据 `.tmp/rr-scope01/round2-three-green.xml`，测试源哈希冻结在 `round2-green-source-hashes.json`。

Ruff初次发现既有E402：provider的executor_registry导入位于原两项039测试定义之后；固定36a3175原文件同样位置（原line55，修订line57），本批未造成这一结构。root明确批准后仅将这一导入移回现有顶部导入组，未移动其他代码、路径引导或添加noqa。静态AST证明原导入前只有imports及两项无decorator/默认参数的函数定义；registry不依赖这些测试函数，也不读取数据库。三文件Ruff重跑全部通过。

201项完整绿证据保留。导入移动后的最终provider源已完整重跑 **107项全部通过**，1.91秒，无过滤/skip/xfail；三文件Ruff最终检查全部通过。native33和Golden61的文件哈希与此前201绿源相等，不无故重复全套。证据 `.tmp/rr-scope01/round2-provider-final-green.xml`、`round2-final-source-hashes.json`。测试槽已立即释放；root已授权限定四路径真实Husky中文提交，不额外运行Node全量。

## 保留的保护

native具体族选择/门控、未知executor、旧执行ID拒绝、兼容依赖和未执行规则均保持。provider固定fixture文书refs8/6、source次数1/3、limit50/51、row_ref64、limit2以及来源时间/私有材料保护非目录计数，不改。Golden fixture schema/selector/candidate/accepted版本、policy_version 2026-06-09、expected_rule_count49/68负向、同数pending替换、缺项/重复/未知、runtime顺序/contract_version拒绝、旧v1不获发布通过，全部不改。

本批仅工程目录合同维护，不宣称RR-SCOPE01全部旧合同问题关闭，不称待验规则已发布或医学验收完成。提交/Husky另等root串行授权。

## 生产 JSON 不变保护

提交前以下五份权威 JSON 字节与 HEAD 相等；提交后再次核对原始字节 SHA256。不改变可选范围或普通业务启用策略。

| 文件（backend/app/data/）                           | SHA256                                                             |
| --------------------------------------------------- | ------------------------------------------------------------------ |
| luxian_0609_rule_master_v1.json                     | `9e20f4d79d11563f6c36c06a875665479c948103fe12c95f0169f8ffebc21e93` |
| luxian_0609_rules_v1.json                           | `7063efdc96de07c91ea58c80612427db8b9031b9546a99b8ab736784fc5db22c` |
| luxian_0609_phase1_rules_extension_v1.json          | `ca4dd781014946202711a71f389c7fd60dda223a4479e20e1a356f2c37e54d14` |
| luxian_0609_rule_contracts_v1.json                  | `85fd30b0a0c424557085540784607d9fe2615c8f731f3646692316b8ff4fbec7` |
| luxian_0609_phase1_rule_contracts_extension_v1.json | `b311ffefca209dd100f8578bc54bb4d23157737256e01d04315ae1752b06e5de` |

提交前后证据 `.tmp/rr-scope01/round2-production-json-hashes.json`。
