# RR-SCOPE01 第一批测试合同修订准备

工作树 `F:/MedQC-worktrees/qc-fix-chemo-v2-20261008`，准备基线 `59b3d7cbc83ee5d3de946f08409d04fc9357dc57`。依据根批准的 `F:/MedQC-worktrees/review-artifacts/rr-scope-pub-design.md`，本批仅修改三个测试文件和本说明；没有修改生产 JSON、发布入口、Prompt、化疗模块、pytest.ini 或 0916 范围。根审批准后已串行完成固定原测试红测与三个文件完整绿测，未运行 Node 或提交。

## 权威预期与精确改动

- `backend/app/data/luxian_0609_rule_master_v1.json` 由测试直接解析，禁止通过被测加载器生成预期。raw 当前 86 条、active 85、pending implementation 1；phase target 75、phase pending 11。上述数值仅记录静态证据，不成为新的测试魔数。
- `docs/plans/lx0609-four-part-rule-code-mapping-v1.csv` 只由测试读取；检查批准 `frozen_identity_migration`、旧新身份各自唯一，按已有旧身份排序提取迁移有序元组。按 CSV 身份成员筛选 raw/loaded master，保留完整迁移顺序，不再切前 79 项。
- 批准追加有序元组明确为 `06-01-01、06-01-03、06-03-01、06-03-02、06-02-01、09-01-02、08-01-05`（均 LX0609 四段 ID）。断言追加身份及顺序、迁移/追加互斥与并集覆盖，并检查 raw 与加载结果逐身份有序相等。implementation summary 仅由 raw Counter 派生，不以计数代替身份。
- `test_luxian_0609_phase_scope.py` 首项改为每条 raw master 的有序 phase 投影合同：注册、phase、active/pending criteria、pending reason、definition version 逐条核对；phase 三集合各自有序、互斥、并集完整。保留既有 master→phase 投影和具体暂停原因/文案测试。
- 客户选项独立冻结五排除 ID：`11-01-01、11-02-01、11-02-02、11-03-01、11-03-02`。生产排除常量必须逐身份相等。预期 delivery 按 raw active 顺序减该集合，executable/withheld 由 raw phase 拆分，精确有序元组相等、互斥并集完整；不把 acceptance_only 当作客户排除。
- 新增 acceptance_only 元数据边界，冻结 `06-01-03、06-03-02、06-02-01、09-01-02、08-01-05`，raw 与 master 加载结果精确一致，均 active/phase target、与客户排除互斥、存在于客户可选列表。此测试不声称普通业务复检可启用，不修改 business_actions 的发布拒绝。
- `test_luxian_0609_rule_contracts.py` 首项以 raw active 身份顺序对照 contract/catalog，逐条核对 phase 与判据/原因/definition version，并验证 phase 三集合互斥并集。保留未注册 `06-03-01` 不入 contract、allowed_final_states/not_executed 门禁。
- 完整 policy metadata 测试以 raw 有序身份覆盖；`customer_confirmed` 按 CSV 身份筛选，不按位置识别迁移规则。所有规则 policy_sources/policy_summary 完整性保持。

## 实际红绿结果

固定 `59b3d7cbc83ee5d3de946f08409d04fc9357dc57` 原三个测试文件完整运行：49 项，6 失败、43 通过。下表五项已实际失败；其中旧追加元组失败使其后 summary 断言未执行，不能把后续断言静态推导也计作额外红测：

| 原节点                            | 实际失败点                                                               |
| --------------------------------- | ------------------------------------------------------------------------ |
| phase freezes all 85              | raw/投影当前 86，与旧 len85 不符                                         |
| customer delivery                 | 当前 delivery80，与旧 len79 不符；随后旧 executable 断言因首个失败未执行 |
| master 79 migrated / six handbook | 第七追加 08-01-05 与旧六项元组不符                                       |
| policy metadata all rules         | 当前86与旧 len85 不符                                                    |
| contracts phase1 registered       | active85与旧 len84 不符；随后旧 target 断言因首个失败未执行              |

第六个实际红测是同一个 contract 测试文件的 `test_rule_contracts_make_current_authority_and_evidence_maturity_explicit`：显式 typed_shadow 集合遗漏 `LX0609-08-01-05`，raw 扩展 contract 已声明其 typed_shadow_v1。根审批准后仅追加这个身份，未扩大其他 authority/source-state 集合。

修订后三个文件完整运行 **50 项全部通过**（phase 12、master 23、contract 15），没有 deselect、xfail 或 skip。既有原重复/非法/空身份 8 例、policy invalid 6 例、partial fail-closed、未注册 ID 拒绝、v7、executor registry drift 和 authority version drift 均包含在这次完整绿测中，不通过修改它们的预期消除失败。三文件 Ruff 检查全部通过。

隔离 runner 使用真实 `backend/pytest.ini`（包含 strict-markers），只关闭 conftest 外部 fixture；安装 audit guard 拒绝 `.env*` 读取、网络解析/连接及真实 DB session/init。只读取权威本地 JSON/CSV，没有 PG、模型调用或生产写入。红测过程仅备份/恢复本 owner 三个测试，try/finally 前后 SHA256 全部相等，没有 stash/reset 或回退其他路径。

证据均在工作树 `.tmp/rr-scope01/`：`red.xml`、`green.xml`、`red-restore-hashes.json`，以及原始和准备稿各三个冻结副本。

## 版本与集成边界

master_version `2026-09-22-identity-v1`、definition_version `lx0609-defined-scope-2026-09-22-identity-v1` 的已有字面值未被证明失效，继续保留，同时与 raw 元数据相等。`LX0609-12-01-02` contract v7、executor registry drift 与 authority version drift 拒绝测试保持原样。074 单规则版本/Prompt 留痕保护不在本批改动范围，未改写其他测试或生产定义。

化疗集成新增问题另记：临时 runner 的 CLI marker 注册未覆盖标准 strict-markers 入口，root 已独占 pytest.ini 注册 business_oracle，未默认过滤或跳过；六条化疗原业务 oracle 未达保持开放。本批不并发修改 pytest.ini。

测试槽在完成实际红绿和 Ruff 后已释放给 root。尚未提交，提交/Husky 必须另等根串行授权。本报告仅证明目录测试合同与权威身份一致，不表示全部医学规则或 acceptance_only 规则已经验收发布。

## 生产 JSON 不变保护

提交前逐文件原始字节与 HEAD 相等，SHA256 如下；提交后再复核，日志保存在 `.tmp/rr-scope01/production-json-hashes.json`。

| 文件（backend/app/data/）                           | SHA256                                                             |
| --------------------------------------------------- | ------------------------------------------------------------------ |
| luxian_0609_rule_master_v1.json                     | `9e20f4d79d11563f6c36c06a875665479c948103fe12c95f0169f8ffebc21e93` |
| luxian_0609_rules_v1.json                           | `7063efdc96de07c91ea58c80612427db8b9031b9546a99b8ab736784fc5db22c` |
| luxian_0609_phase1_rules_extension_v1.json          | `ca4dd781014946202711a71f389c7fd60dda223a4479e20e1a356f2c37e54d14` |
| luxian_0609_rule_contracts_v1.json                  | `85fd30b0a0c424557085540784607d9fe2615c8f731f3646692316b8ff4fbec7` |
| luxian_0609_phase1_rule_contracts_extension_v1.json | `b311ffefca209dd100f8578bc54bb4d23157737256e01d04315ae1752b06e5de` |
