# RR-SCOPE01 第二批固定提交静态独审：接受，可串行集成

固定提交 `a55d27612b77743442a7a7a4c37b543193d39b80`，父提交 `36a3175b4c2ec2a4cc574b15405638ef44c0361a`，工作树 `F:/MedQC-worktrees/qc-fix-chemo-v2-20261008`。完整diff仅native_package、evidence_snapshot_provider、golden_gate三个测试和一份说明；本轮只读固定git blob和历史原始JSON，并以stdlib AST解析literal/比较函数，不导入或执行生产/测试函数，没有pytest、Node、PG、.env或模型。静态审阅无合入阻断；root可串行集成后运行201项。

## 历史映射独立证据

独立从 `d897689ca^` 解析出的完整固定提交为 `6e796ba1dccebe47950183f50bdf9819b274884f`。按该提交原始master active声明顺序及两份原始wrapper JSON，静态派生84项 `(rule_id, mapped_rule_ids)`；新测试 `_PRE_DISCHARGE_COMPATIBILITY_DEPENDENCIES` AST literal与其逐身份、逐依赖、逐顺序完全相等。当前固定raw wrapper按历史ID筛选后的有序映射也完全相等，原累计125依赖保持。

唯一新增映射为 `LX0609-08-01-05 → (LX0609-08-01-05,)`；不是将旧125简单改成126，也没有因当前加载结果更新历史预期。静态原始证据和函数AST变更索引保存于 `second-static-evidence.json`。

## 身份与分区保护

inventory/catalog有序IDs对照独立raw master active身份；wrapper身份唯一、全集与active覆盖一致。逐条依赖映射、规则版本、适用来源、数据依赖、dependency_type和executor_type直接比对原始wrapper。family成员Counter精确覆盖，每条恰属一族且family key/name一致，八family literal仍保留。原native sync/async显式边界只向async追加08-01-05；兼容集合、未注册culture身份拒绝保持。

两个完整计划的selected、executable、pending来自raw master身份/phase，native sync/async互斥、按声明顺序、合并覆盖正确；兼容例外仍分别为03-01-04及04-01-01，原CL-248/CL-250/CL-071与CL-181/SC-081依赖列表不改。旧未知executor、旧执行ID拒绝、族门控等其余函数AST相对父提交不变。

provider的全注册测试以raw active有序IDs核对selected和catalog；原精确sources调用集合、每来源一次、无legacy调用、observations覆盖及query-state断言没有放松。仅补Path/raw JSON来源、改名和身份预期。文书ref数量、limit、时间/私有材料等非目录业务保护未改。

## 版本和导入边界

独立解析历史 `ea5ed2b047^`/`ea5ed2b047`/当前固定source_registry版本，分别为v33/v34/v34；因此测试全局literal改为lx0609-source-registry-v34有历史事实依据。血液局部仍断言query_version=snapshot-provider-bloodtrans_record-v2与source_keys=(bloodtrans_record,mr_bloodtrans)，没有机械升为v3。全局与局部版本现在分开命名测试，均受独立literal约束。

executor_registry import仅从两个039测试函数定义后移到已有顶部导入组；没有改生产、path bootstrap、fixture、默认参数或添加noqa。开发移动导入后的provider107绿测是开发证据，本轮没有复跑或把它计为独立通过。

## Golden 工件验收合同

新测试名称和docstring明确为candidate acceptance matrix。独立raw active减五个明确客户排除identity，再按raw phase得到候选有序delivery/executable/pending；目前80/70/10仅是这些身份集合的派生数值，不是业务默认执行策略。五acceptance_only身份explicit literal仍为06-01-03、06-03-02、06-02-01、09-01-02、08-01-05（均LX0609四段ID），在候选目标矩阵中且与排除互斥。这证明待验候选账本/运行工件覆盖，并不证明普通业务默认启用、待验规则已发布或医学验收通过。business_actions及发布策略不在提交diff。

contracts、manifest rule_set IDs及rules IDs有序覆盖raw active；逐项phase与definition_version比对raw。summary计数从身份集合长度派生。其余Golden函数AST相对父提交全部不变：同数pending替换、旧49身份、缺项/重复/未知、manifest顺序/contract_version/phase/definition漂移、窄集合权威顺序、v1不获正式发布、ledger schema/selector/candidate identity/三次稳定/预算等负向守卫全部保留，不能靠数量相同全绿。

## 生产不变与验证边界

五份生产JSON父/固定Git blob逐份相同：master 31fd1e9fe49ce4b68c58367ed25bd57e89e1bff4；rules cfea6bd12240de9fd20a90ce6cfc0eea73982d2f；rules extension 280d7c664fb45fa09c4be4cf2aab6fa03277b392；contracts ea97ca01bdf24e28cd75ecba45280889fcd15786；contracts extension 1a88ccd88e77866561c163d135ab72cb305037eb。提交四路径无生产发布或默认启用变更。

本轮独立执行测试数0。开发原native33/provider107/Golden61共201通过、仅移动导入后最终provider107通过，作为开发声明记录；不能冒充本次独立运行。接受仅指本批工程测试合同维护，root后续串行集成完整201仍是执行门禁，也不等同RR-SCOPE所有历史合同问题关闭。
