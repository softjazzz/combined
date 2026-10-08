# RR-SCOPE01 固定提交只读独审：接受，可串行集成

固定提交 `36a3175b4c2ec2a4cc574b15405638ef44c0361a`，父提交 `59b3d7cbc83ee5d3de946f08409d04fc9357dc57`，工作树 `F:/MedQC-worktrees/qc-fix-chemo-v2-20261008`。本轮仅git show/diff及原始JSON/CSV静态解析，没有执行pytest、Node、PG、模型、生产导入或医学规则复审。结论不引用开发50 passed为独立测试通过；root接受后另行串行集成运行。

## 独立预期与身份合同

三个测试的新预期直接解析 `backend/app/data/luxian_0609_rule_master_v1.json`，没有通过被测load/compile/phase/catalog函数生成预期。迁移预期来自批准 `docs/plans/lx0609-four-part-rule-code-mapping-v1.csv`，检查非空、mapping_status=frozen_identity_migration、旧新身份各自唯一，再按legacy_rule_id排序；不是调用加载器复制实际结果。

master测试检查raw与实际逐身份有序相同、唯一性；按迁移身份成员筛选后保留CSV完整顺序。追加身份及顺序明确冻结七项：LX0609-06-01-01、06-01-03、06-03-01、06-03-02、06-02-01、09-01-02、08-01-05。迁移与追加互斥并集全覆盖，私有或未批准候选不能仅因raw JSON多一行就无条件通过。停止前79切片符合批准方案，允许raw总表负责跨组的总体声明顺序，迁移/追加内部顺序另受固定合同约束。

phase测试对每项phase、注册状态、active/pending criteria、pending reason逐行核对，注册IDs按raw active顺序同时与catalog精确一致。三阶段各自有序、互斥且并集完整；保留具体十一pending身份、暂停原因、空事实not_executed文案及partial fail-closed测试。

客户五排除仍为独立literal集合：LX0609-11-01-01、11-02-01、11-02-02、11-03-01、11-03-02；要求生产常量精确相等，delivery按raw active顺序减此集合，executable/withheld按raw phase精确有序分割并检查互斥并集。culture pending身份不入delivery且选择拒绝等原守卫保留。

五acceptance_only身份显式冻结：LX0609-06-01-03、06-03-02、06-02-01、09-01-02、08-01-05；raw与加载器精确一致，均active/phase target、与客户排除互斥并存在客户可选列表。本测试只是目录/选项元数据合同，不声称普通业务复检可发布；生产business_actions入口未修改。

contract测试以raw active身份有序对照contract/catalog，逐项核对phase、criteria、reason、definition version。未注册06-03-01不入合同、每项允许not_executed、来源依赖及调用预算原守卫仍保留。typed_shadow增加08-01-05有固定原始扩展JSON source_contract_state=typed_shadow_v1依据，不是只因开发失败而机械放宽集合。

## 未被删掉的约束

master_version与definition_version继续同时对raw元数据和已有literal：2026-09-22-identity-v1 / lx0609-defined-scope-2026-09-22-identity-v1。12-01-02 contract_version=v7原断言未改；executor_key=unexpected_executor及definition_version=stale的ValueError漂移拒绝测试未改。

重复、畸形、零身份、错误前缀、空目录共8个非法身份参数；非法policy metadata六个参数；完整policy_sources/policy_summary、customer_confirmed迁移条目按CSV成员验证均保留。新测试没有xfail/skip/deselect，没有删除原非法输入守卫。旧目录数字改为逐身份、顺序、分区和来源元数据合同，约束未退化为“仅与实现自己比较”。

## 生产不变证据与验证边界

提交完整diff只有三个测试文件和一份说明文档；五份生产JSON的父/固定Git blob ID逐份完全相等：

| 文件 | 父与固定共同blob |
| --- | --- |
| luxian_0609_rule_master_v1.json | 31fd1e9fe49ce4b68c58367ed25bd57e89e1bff4 |
| luxian_0609_rules_v1.json | cfea6bd12240de9fd20a90ce6cfc0eea73982d2f |
| luxian_0609_phase1_rules_extension_v1.json | 280d7c664fb45fa09c4be4cf2aab6fa03277b392 |
| luxian_0609_rule_contracts_v1.json | ea97ca01bdf24e28cd75ecba45280889fcd15786 |
| luxian_0609_phase1_rule_contracts_extension_v1.json | 1a88ccd88e77866561c163d135ab72cb305037eb |

原始JSON静态记录为86总身份、85active、1pending implementation；75条未显式phase字段按既定default phase_1_target、11pending；CSV79身份、批准追加7身份、acceptance_only5身份。这些计数用于审阅事实，未新增为测试目录魔数。

本轮独立执行测试数为0。开发原6failed/43pass到50pass及Ruff结果只作为开发声明记录，不作为本报告独立结果。未发现合入阻断；建议root依既定流程串行集成，再完整运行三文件50项，以执行门禁证据补足本次静态接受。
