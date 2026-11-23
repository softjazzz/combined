# 逐记录生命周期只读适配交付

> 当前源码固定的同步候选为 `913421639fe3cfb5459909973503f87e14b4802d`。该候选的源码复核关闭了下文旧候选的两项 P1，业务只读逻辑及合同字段保持一致。功能仍默认关闭，现场批准、发布与联验待完成。复核记录可从归档读取（`git show archive/docs-pre-cleanup-202611:apps/medqc-web/docs/clinical-record-lifecycle-business-20261116/CLOSEOUT-913421639.md`）。

以下为早期适配及合成验证记录。业务基线为 `946f9d21f7ff1ce6e92a8b7736344b17e5dd0f3d`，当时的同步候选为 `7a8c4bb424189a10e97f49e2df7d4b5c1a8abafe`。

**早期同步候选存在两项 P1，当时不满足启用条件。** 清理前的本地交付提交通过 `git log -1 --format=%H archive/docs-pre-cleanup-202611 -- apps/medqc-web/docs/clinical-record-lifecycle-business-20261116/IMPLEMENTATION-AND-REVIEW.md` 定位；未推送、合并或部署。

## 旧候选包核验和同步复审

指定 ZIP 为466706字节、165个唯一条目。外部 SHA256 与给定值一致，ZIP CRC通过；`CHECKSUMS.txt` 覆盖164个文件，逐文件重算且集合严格相等，无缺失、重复或越界路径。根 `package-manifest.json` 提交为指定7a8c4bb42；未用参考目录内旧版本代替。实际映射保持36/55/59/49列，共199列；草案开关关闭、policies与生命周期批准为空。

已阅读指定六份根文档及真实运行路径。同步侧70项（61离线＋9合成PG16）及解包后20项仅复用原证据，后者重叠，不累计为90项，也不写成本轮实跑。

两项新增发现均用固定包实际函数和纯内存 SQL 游标反例确认，未修改同步源码：

1. **P1：恢复捕获尚未发布即清除HOLD。** `runtime/medqc_ingest/primary_store.py:509–514` 从已知HOLD中减去本次观察到的文书，未等恢复版本发布。g1可用clinical与同号Caché已固定；g2 HOLD捕获未发布；g3恢复捕获但receipt仍为g1。此时coverage被写为COMPLETE、HOLD为空，publication health虽BLOCKED，旧同号Caché仍重新被选为CACHE_FALLBACK。需保留按版本的HOLD，直到恢复版本完成发布及选择确认，不能扩大阻断独立Caché。
2. **P1：提交中断后的漏返会提前完成PENDING。** g2 HOLD已在ingest提交、coverage证据未同步；之后g3完整空捕获漏返该文书。`primary_store.py:501–508,526–530` 虽已识别`clinical_previous_record_not_in_latest_capture`，仍把未消解PENDING写为COMPLETE，旧同号Caché复活。需补齐已提交HOLD证据或保留相关PENDING，不能因下一batch成功解除保护。

共同下游为`clinical_primary.py:295–341`：总publication health只拒绝clinical，失去逐记录证据后不足以阻止同号Caché。正常已同步HOLD、已知HOLD漏返、PENDING立即读取和恢复后立即发布的既有用例，不覆盖上述两个中间时序。

完整报告和两个最小反例保存在本机交接目录 `C:/Users/Coldplay/.codex/local-qc-acceptance/record-lifecycle-business-7a8c4bb42/` 的 `SYNC-CANDIDATE-REVIEW.md` 与 `repro_recovery_before_publication.py`。默认关闭是运行边界，不表示两项缺陷已修。

## 本次业务改动

- `build_primary_readonly_closure.py` 按固定包实际依赖重新提取，更新固定提交、源及运行指纹。运行闭包为11个源模块、37个定义、27个类方法和19个常量；四个输入JSON含原三合同及SOURCE_FINGERPRINTS。生成指纹另列来源hash、裁剪或改名适配及运行hash。
- 新增`RecordLifecycleContract`、`record_contracts()`、`contracts_for_mode()`、必要`denormalize/material_metadata`依赖；候选selector、`_health`逐字更新，`read_in_transaction`仍为固定源定义。合并命名空间时只将生命周期REVISION重命名，旧real-fields-v2 REVISION和strict摘要不变。
- `load_read_plan()` 一次读取受保护批准文件并绑定病例policy、source binding、mode及生命周期批准，避免两次读文件混配。`load_policy()`保留兼容入口。每项仍需精确policy_hash及当前独立CDM source_binding。
- 缺少`lifecycle_mode`继续旧strict；显式`record-hold-v1`才启用新合同。显式null、空字符串或未知mode受控拒绝。`lifecycle_approvals`仅接受固定四kind的四元组列表，语义交由原合同校验；未提供不产生批准。固定199列和正文映射不由批准文件重写。
- manifest、coverage、回执和正文继续同一个CDM只读REPEATABLE READ事务读取。只借SQLAlchemy现有driver_connection，仅读显式列，cursor自有；不commit、rollback或close调用者连接，不另连最新正文。
- Provider、Bundle、目录、全文仍复用原唯一owner及selector实际选择。原始HOLD版本完整留在manifest及材料副本，可按权限展示待核原因，不能成为规则事实。传递`source_lifecycle_revision`及完整coverage；`OBSERVED_WITH_HELD_UNPUBLISHED`明确说明有HOLD未投递，不能解释为全部发布或覆盖完整。

审批文件新增字段形状（仅结构说明，**不是可执行批准文件**）：

```text
policies[]:
  policy: 原病例映射及批准
  policy_hash: 精确原policy摘要
  source_binding: 当前独立CDM绑定
  lifecycle_mode: record-hold-v1  # 缺省沿旧strict；显式空值拒绝
  lifecycle_approvals:           # 未获批准必须为空；不示例真实0/1语义
    daily_course_record: []
    presurg_summary: []
    surgery_record: []
    postsurg_firstcourse_record: []
```

## 只读权限、历史和兼容

仍只读14个对象，无新增授权：`sync_material.primary_policy(case_id,policy_hash)`、`primary_head(case_id,selection_id)`、`primary_manifest(selection_id,result_json)`、`primary_coverage(case_id,source_namespace,coverage_json)`；`sync_delivery.contract`的接口/epoch/mapping/activation；`receipt`的接口/key/epoch/generation/mapping/activation/target_key；四个clinical_current及四个Caché基础表的固定target_columns。精确列草案沿用相邻旧交付目录的`READONLY-PERMISSIONS-PROPOSAL.sql`，本次重新核对列集合不变。

不新增primary_attempt、binding、policy_version、raw、ingest、源库或控制库读取。闭包没有迁移、extract、publish、poll、连接工厂或写入口；生命周期写侧只在包外纯内存反例中用于确认同步缺陷，未携入业务运行时。没有执行GRANT。

旧MetadataContract未加mode字段，固定strict四类摘要及spec hash保持不变。旧全文快照缺新增字段仍按既有协议读取，不回查当前CDM；新mode及当前HOLD不能回写旧manifest、任务或结果。重试仍用原不可变材料；新发布需新执行/材料副本。1026/PDF绑定、无首页取材、C03待确认及现有暂停项均未修改。

## 必要验证与独立复审

本轮仅运行直接受影响合成路径，模型及医学规则执行为0，未读取真实患者材料。

- 闭包离线27项通过：严格摘要、源码及JSON指纹、依赖解析、生命周期合同/形状拒绝、选择及连接所有权；在临时目录重建与交付模块/JSON逐字节一致。
- 原owner/capture直接相关17项通过：统一输入、冻结及重试、身份绑定、未部署与权限边界、旧PDF分流。
- 新mode批准/覆盖及历史兼容9项通过。
- 专属PG16.15的3个新增场景通过：29准入＋1HOLD贯通目录/Bundle/规则输入和全文副本；消费已保留的HOLD/PENDING/失败证据并在明确发布新版本后恢复、旧副本不变；RR并发回执更新不混版、新读取显式stale及权限42501。首轮1过2败因新增验收helper使用Bundle默认limit=3；显式改为100后只复跑失败两项，均通过。首轮已过的第三项每类最多1行，复用其证据、不重复执行。两次专属集群均停止。
- 独立业务Spec轴与Standards轴均未发现新增P1/P2。独立核对基线strict摘要、spec摘要和固定候选关键定义逐字内容、源/运行/JSON指纹；未重复运行上述测试。主协调核对最终源码差异和PG报告，复审后仅补交付文档。

PG验证消费的是合成CDM内已保留的逐记录证据，不验证同步producer在中断或漏返后能否正确保留证据；两项 P1 反例针对早期 7a8 候选。没有以手工构造正确coverage掩盖上游缺陷。旧strict及快照兼容已有本轮定向证据，未重复旧PG矩阵或232项。

外部交接目录保留 `CLOSURE-VALIDATION.md`、`BUSINESS-SPEC-REVIEW.md`、`BUSINESS-STANDARDS-REVIEW.md`、`business-lifecycle-tests.json` 及两次PG的原始结果。未验证真实机构/类型/生命周期语义、现场角色及并发负载、真实发布和页面联验；未调用模型、医学规则或质控。

复现命令仅供需要时使用，不要求重复已通过集合：

```text
# backend；不加载父级应用conftest，无真实连接/模型
python -B -m pytest -c pytest.ini --confcutdir=tests/unit -p no:cacheprovider -o "addopts=-q --tb=short --strict-markers" tests/unit/test_primary_material_readonly.py
python -B -m pytest -c pytest.ini --confcutdir=tests/unit -p no:cacheprovider -o "addopts=-q --tb=short --strict-markers" tests/unit/test_primary_material_lifecycle.py
```

## 现场联验条件

1. 联验前核对现场同步版本与固定候选、来源指纹及只读权限。
2. 院方分别确认P01/P02机构、四类文书类型、同号关联与生命周期语义；is_deleted的0/1、NULL、record_status原值不由业务猜测，不填伪批准。
3. 同步方提供同事务可核对policy_hash、selection_id、版本、回执、正文及coverage证据；运维批准上述精确只读对象/列。保持`QC_PRIMARY_FOUR_MATERIAL_ENABLED`关闭，另获授权才考虑现场联验。
4. 执行前逐单元声明EXPECTED_AVAILABLE／EXPECTED_HELD／EXPECTED_NO_SUPPLY、批准依据与适用数量/版本断言。预期HOLD或无供给不要求selected_version非空、不读取未发布正文、不计可用链通过，也不阻断其他可靠材料。全部待核只报告“状态核对完成，无可验收的可用材料”。
5. 意外HOLD、独立权限/版本/回执/完整性异常停止受影响单元及依赖；共享manifest、身份、连接或事务失去可信依据时停止相关病例/全部受影响范围。不得在失败事务内继续，或另开连接补最新正文。无法确定影响范围时不得擅自缩小。
6. 既有`verify_primary_material_trial.py`是旧strict、整例停止工具；逐单元停止条件修订尚保留在原工作树的独立未提交任务中。不能直接用旧工具验收新mode或现场补改；本轮不执行其`--execute`，不混入该未完成修改。

真实clinical未批准或未发布仍待核；合成通过不等于真实材料已发布、现场启用或生产上线。
