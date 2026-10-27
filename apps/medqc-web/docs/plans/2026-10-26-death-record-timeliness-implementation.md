# 09659死亡记录24小时接入计划

**Goal:** 将客户09659作为独立规则接入现有extended_document族，用1026-PDF补全的只读材料验证。

**Architecture:** 新规则LX0609-04-02-09复用已冻结证据、正文死亡时刻抽取及权威文书时间合同，纯程序按精确时差判定。独立小模块在原值精度丢失前核查死亡时刻，既有规则、默认选择范围和历史结果不变；先登记acceptance_only，不新增执行族。

**Tech Stack:** Python、现有RuleDecision/Canonical、离线pytest与内存SQLite；真实PG只读提取当前材料，不在PG保存新结果。

## 整批范围

25项时效要求作为一批维护：复核发现00715原有覆盖，当前为18项已有映射、4项真实新增、3项合同差异。09659、09299、00717/00718已分批接入并验证；00694/00696/09613沿用户确认的既有合同。其余旧映射继续核实际断点，不以同名规则存在作为验收完成。

| 客户ID | 要求                   | 对应规则/本批状态                                                                       |
| ------ | ---------------------- | --------------------------------------------------------------------------------------- |
| 09792  | 入院记录24小时         | 01-01-01，已有映射，未逐例重验                                                          |
| 09923  | 首次病程8小时          | 01-02-01，已有映射，未逐例重验                                                          |
| 00364  | 稳定患者每3天病程      | 02-01-03，已有映射，未逐例重验                                                          |
| 09797  | 病危患者每日病程       | 02-01-05，已有映射，未逐例重验                                                          |
| 09701  | 主治首次查房48小时     | 02-01-01，已有映射，未逐例重验                                                          |
| 09814  | 高级职称首次查房72小时 | 02-01-02，已有映射，未逐例重验                                                          |
| 00715  | 第一术者术前一天查看   | 已复核04-05-01原有术前分项；10项纵向及27例真实材料链通过，撤回完全未实现判断            |
| 09815  | 术后连续3天病程        | 04-05-01，已有映射，未逐例重验                                                          |
| 09298  | 术后3天术者查看        | 04-05-01同规则的术者覆盖，保留独立客户细项                                              |
| 09297  | 术后3天上级查看        | 04-05-02，已有映射，未逐例重验                                                          |
| 00717  | 住院超过48小时血常规   | 已接06-03-05，27例离线链中12真实完整报告正例，保留资料缺口，见血尿常规交付记录          |
| 00718  | 住院超过48小时尿常规   | 已接06-03-06，27例离线链中6真实完整报告正例，与血常规独立判定，见血尿常规交付记录       |
| 09563  | 抢救结束6小时记录      | 09-01-01，已有映射，未逐例重验                                                          |
| 09697  | 死亡一周内讨论         | 09-02-01，已有映射，未逐例重验                                                          |
| 00694  | 有创操作记录时限       | 冲突：附件24小时/即刻与现有3天；保持10-03-01                                            |
| 00696  | 交班24小时             | 冲突：现有交班前完成；保持10-01-01                                                      |
| 00697  | 接班后24小时           | 10-01-01，已有映射，未逐例重验                                                          |
| 00693  | 转入24小时             | 10-02-01，已有映射，未逐例重验                                                          |
| 00692  | 转出24小时             | 10-02-01，已有映射，未逐例重验                                                          |
| 09299  | 超过30天阶段小结       | 已接10-04-01，按确认合同完成代码及27例离线链；6例缺批准的出院终点，详见阶段小结交付记录 |
| 09613  | 普通会诊48小时         | 冲突：客户既有24小时；保持04-02-07                                                      |
| 09832  | 术后24小时手术记录     | 04-02-01，已有映射，未逐例重验                                                          |
| 09710  | 出院前一日/当天批准    | 08-02-02，已有映射，未逐例重验                                                          |
| 09589  | 出院记录24小时         | 08-01-01，已有映射，未逐例重验                                                          |
| 09659  | 死亡记录24小时         | 本批新增04-02-09；代码及5例只读材料离线链验收，未默认发布                               |

以上编号统一带LX0609前缀。17个客户条目不等于17条独立LX规则，也不计作本轮新增完成。09299的数据来源已经具备，未确认周期不生成临床结论；其余来源可用的旧规则验证可以继续，不因单点待定暂停整批。

## 判定合同

- 用户确认死亡记录承担死亡病例的出院记录职责，按真实有效文书标题识别；死亡病例不另要求出院记录。
- 死亡时刻与完成时刻分别读取，文书时间按record_time、record_datetime、submit_time、submit_datetime既有优先级。缺失、日期精度或无效值不以当前时间、同步时间或签名兜底。
- 沿用出院规则当前的最后一条权威完成时间选择方式；相同时间用稳定文书ID排序。有可能影响选版但无时间的有效记录保留资料不足。
- 24小时整合规，超1秒超时；早于死亡为时间冲突。存在性缺陷由04-02-06负责，新规则缺记录时资料不足，不重复报临床缺失。
- 明确出院标题时不适用；死亡讨论、出院前查房和待核对PDF不冒充终末记录。两类真实终末文书并存保留来源冲突。
- 登记来源不可用也阻断临床结论；死亡时刻原值必须具备具体时刻。跨表同ID按真实来源定位，同来源同ID不同内容因公共坐标无法区分版本而保留来源冲突。

## 实施与验证

1. 新增tests/unit/test_luxian_0609_death_record_timeliness.py，先验证期限、时区、来源缺口、标题分流、选版与乱序反例。
2. 新增services/luxian_0609/extended_document/death_record_timeliness.py；在native_extended_document_execution.py新增局部分派，保护旧规则路径。
3. 补唯一总表、扩展目录与合同、customer_rule_package、source_registry、判定说明、客户文案与公开事实合同；只新增身份，旧条目不重写。
4. 离线正式执行入口→绑定→Finalizer→Canonical内存保存读取；补相邻死亡/出院和注册目录保护用例。通过backend/scripts/run_pr8_offline_tests.py运行，禁止读取dotenv、网络和非SQLite连接。
5. 用原生PG只读事务提取1026-PDF补全已登记三坐标的必要文书，退出连接后禁网，离线运行本规则及内存保存读取。患者原文和逐例事实只留.tmp/0910-full-audit/\*-private；公开文档只保留匿名数量和证据界限。

## 隔离基底

工作树C:/medqc-death-timeliness，分支codex/lx0609-death-record-timeliness-20261026，从PDF材料读取线已提交418e865d2开始。没有合并其他分支，不改正在使用的PDF线工作区。仅本地开发，不推送、不合并、不写业务库，不启动模型或历史任务恢复。

## 交付证据及边界

- 1026-PDF补全的5例当前有效死亡记录已由独立原生PG只读事务提取。只读连接已关闭，随后使用禁网、禁dotenv和禁止非SQLite连接的启动器执行本规则，经实际Snapshot→Native→Binding→Finalizer→Canonical内存保存读取，逐例与独立SQL时差参考值一致。原临床时刻、正文及PDF候选状态均未改动。
- 源材料所在库名为medqc，本轮只读；没有将新结果写入PG。不能据此声称隔离后端已部署、HTTP/浏览器验收完成或业务库已启用。
- 原生执行模型调用为0；新规则只登记acceptance_only，旧任务、默认选择及历史读取保持原样。未触碰V7.1、前端、账号消息或迁移文件；80项gap口径不因新增本规则改数。
- 双轴独立审阅已复核：登记源错误、日期精度提升、跨表同ID证据串指、公共映射阈值重判均修复。旧JSON条目逐键一致，除新增登记和分派之外原执行器AST与基线一致。
- 患者材料及提取/复现脚本仅在`.tmp/0910-full-audit/death-09659-20261026-private/`，不暂存、不提交；公开文档不包含患者身份、正文和原始时刻。
- 最终一次禁网离线回归：1386通过、2个API测试因本启动器不提供client fixture而显式排除；其中新规则聚焦39项、真实材料5项，不把前轮重跑累计为新增数量。覆盖死亡/出院、秒精度、公开合同、目录、来源读取、执行器及历史读取保护。仅既有Pydantic弃用警告。
- 修改的Python文件Ruff通过；全src只读ESLint退出0（0错误、3435个原有警告），未自动修复。未修改前端，本轮没有重跑全量类型检查或Vitest，不能声称新增浏览器验收。

最终回归在backend目录通过`python scripts/run_pr8_offline_tests.py`执行，显式选择以下文件，并加`-m "not api"`：

```text
tests/unit/test_luxian_0609_death_record_timeliness.py
tests/unit/test_luxian_0609_death_discharge_delivery_boundary.py
tests/unit/test_luxian_0609_death_document_result_mapping.py
tests/unit/test_luxian_0609_death_published_boundary.py
tests/unit/test_luxian_0609_death_discussion_closure.py
tests/unit/test_luxian_0609_death_diagnosis_scope_closure.py
tests/unit/test_luxian_0609_discharge_published_boundary.py
tests/unit/test_luxian_0609_discharge_result_mapping.py
tests/unit/test_luxian_0609_second_precision_timeliness.py
tests/unit/test_luxian_0609_rule_master.py
tests/unit/test_luxian_0609_rule_catalog.py
tests/unit/test_luxian_0609_rule_contracts.py
tests/unit/test_luxian_0609_native_package.py
tests/unit/test_luxian_0609_customer_renderer.py
tests/unit/test_luxian_0609_read_side_projection_boundary.py
tests/unit/test_luxian_0609_phase_scope.py
tests/unit/test_luxian_0609_evidence_snapshot_provider.py
tests/unit/test_luxian_0609_source_evidence_reader.py
tests/unit/test_luxian_0609_native_extended_document_execution.py
../.tmp/0910-full-audit/death-09659-20261026-private/test_pg_fixture_private.py
```
