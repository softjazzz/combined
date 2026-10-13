# 060 当前定向证据绑定结果

固定当前提交 `21f4a93e103a34002a1f9d36f9d895f226c0122f` 的定向合成工程回放通过，未确认本次绑定阻断。首轮 run-01 为 4 native + 1 Finalizer + 6 published，共 11 项；原输入与预期、manifest未改，首日志保留。结论仅将既有实质审查/合成保护绑定到当前责任源码，不把当前SHA补成历史SHA，也不批准临床、HTTP或保存验收。

身份已独立核对：当前master版本2026-09-22-identity-v1的/rules/59唯一条目为 `LX0609-04-02-06`，source_document=死亡记录、qc_point=死亡患者无死亡记录、active；实际unit与执行器均使用该canonical ID。master没有legacy字段，旧060来自当前组surgery-anesthesia.json/rules/10及根已确认目录映射，来源分列于manifest，不伪造master字段。

| 继承节点/边界 | 当前实际证据 | 判定 |
|---|---|---|
| test_death_rules_treat_complete_discharge_record_as_non_death | 原出院登记及出院记录行保留，只取原060分量；native/reduced/public均NA/trigger_absent_complete，finding“本次住院结局不是死亡”，无death facts | 通过 |
| test_060_active_inpatient_with_complete_empty_death_source_is_not_applicable | 原在院登记、完整查空死亡来源；NA/trigger_absent_complete及原finding一致，0call/0Token | 通过 |
| test_060_death_patient_without_death_record_is_non_compliant | 原明确死亡登记2026-07-01 12:00:00，不增改输入；实际NC/required_document_missing，death_confirmed=true、death_record_count=0、death_time=2026-07-01 12:00:00 | 通过 |
| test_death_case_skips_ordinary_discharge_rules | 原登记、death_record及death_discussion行保留，仅回放原060分量；C/requirement_satisfied，count=1、death_time=2026-07-15 21:22:22。只验证存在性，不声称正文充分性或其他规则通过 | 通过 |
| test_060_finalizer_rejects_presence_status_conflict | count=1却传NC的原矛盾输入，handled=true；退technical_error/model_invalid_output并移除错误finding | 通过 |
| published既有6参数 | None/空facts保持缺失；count0和count1+time合法形式read exactly；私有document字段与bool计数拒绝，污染输入保持未改 | 通过格式合同 |

两个共享多规则节点保留全部合成rows，但本次只验证原assert里的060状态/原因分量，不将其余规则顺带记为通过。

责任定位与指纹：native _death_context:789、共享death来源/触发gate:3224、060presence分支:3311；death_document_result_mapping；decision_binding/reducer；canonical_result_finalizer；customer_renderer:3064；source registry/manifest、snapshot/material/reader与静态family定义；权威master。manifest-v1.json记录13责任源码/身份文件及3原测试文件的当前SHA256/Git blob，运行前后均与固定Git字节一致。原生fact_refs与公开结果保存在observed-v1.json；本次没有另造精确文书ID或声称原始无ID合成行具有额外定位能力。

实际执行层级与替身：仅既有_session AST构造的合成snapshot/material → native → Binding/Reducer → Finalizer，以及单项Finalizer/公开事实读取。三个系统模块替身明确为app.database.connection(engine=None)、app.services.bundles.assembly(engine=None)、app.core.settings(get_settings阻断)。两个父namespace仅提供包路径；customer_rule_package仅AST literal提取同一固定源码的RULE_FAMILY_DEFINITIONS；dotenv额外guard阻断load_dotenv/dotenv_values。没有调用生产源获取、HTTP、API或保存层。same_safe_facts沿原published测试只检验既有格式一致性，由sanitizer形成预期，不能当独立医学oracle。

防护：首轮前与结束后固定HEAD、13source/3test字节hash、输入预期hash、manifest与runner hash；.env*路径、private/0910-full-audit读取、外部写入、socket网络、database connect、真实模型均阻断。guard计数env/private/network/database/model/foreign_write全部0。drive finally关闭协程；首轮没有异常/意外yield，没有覆盖首错或重跑伪称首过。未导入pytest/conftest、不写bytecode/cache、不改生产或共享测试。

历史缺口继续保留：旧round2公开报告写基线c3a87a4f820259bca37a01764522ea1f3f485a3c，但责任源码historical SHA缺失，本次字段仍null。旧六真实来源只覆盖无死亡触发NA，原私有获取/冻结/回放产物未打开；旧四合成反例属于037，没有移作060。当前死亡阳性合成NC/C不替代真实死亡阳性临床金标。真实来源覆盖、HTTP、保存、浏览器及临床语义仍未补。

产物同目录：inherited-inputs-expected-v1.json、manifest-v1.json、prepared-runner-v1.py、run-01.log、run-01.meta.json、observed-v1.json。run-01 exit0；日志SHA256 `4552620e7e5d3438824b4f71cd3b59d78d5c622accf2575c56b80f20259b2ce8`。原输入/预期hash `9b9ddb3fbf272948d7b0d81b6bd6fcbec4daaa6011d4f955827a5e36fc8b2cb5`、manifest `93a9f7c343ba068d715500f21d5deffadc1579c269dbd07c2531650e6ae57905`、runner `8f73d823de9f824e140a901b0c0c21716a8486ef94087289aa1be8eb22532fff`。测试槽已释放，无运行进程。
