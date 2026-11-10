# 东华CDM业务接入差量修复与现场交接

## 基线及范围

独立工作树D:/MedQC-worktrees/donghua-cdm-readiness-20261110，分支codex/donghua-cdm-readiness-20261110，BASE=5d3e8d39609a3d1982cebfbfc69425cf104214cd。本机候选供复审，不部署。063及现有064定时计划迁移保留，无新增迁移、共存表或同步运行代码改动。CDM仍默认停用，不改变调度、RabbitMQ、模型及窗口配置。

复用2026-11-10结构证据ZIP SHA256 9dadb31ad069d91ae5903eb204a66cc797a63e25e4577850a0f0a2852287e091及原60对象CSV：45个A存在、B存在5缺10，50表必需列及8个ORM明确列匹配。本轮不再查服务器结构。它不证明SQL类型、实际角色权限、字段供给及临床完整性。

## 修复

- clinical_case_catalog.workstation默认汇总loader绑定业务SessionLocal，不再漏传必需参数；临床目录查询仍独立源，摘要只属业务结果。
- 实际frontpage-sheet路由保留医生范围并接收机构参数；独立模式先唯一解析完整机构/患者/就诊身份，再用clinical engine。明确机构不匹配或同号歧义拒绝，不first借另一机构。兼容模式和历史入口保持原连接。
- 独立模式首页诊断和病理说明从现有diagnosis对象读取，不在空诊断时向缺失mr_diagnosis/discharge_record_diagnosis发裸SQL。没有返回值标not_observed，不声称临床未写；不重建子表或从旧库借值。
- assembly.source_projection_columns由实际读查询和权限预检共用。SELECT *检查所有物理列，ORM检查全部映射列，动态字段按真实选择逻辑与实际列求交集，并包含谓词和排序列。has_column_privilege允许足够的列级SELECT，不强制升级整表授权；拒绝表级/列级写权及SET ROLE可达管理/DDL/写入能力。缺权列可列出，缺列、缺表和零行分开，publication_ready继续None。

## 10个条件缺表的实际处理

以下均不建空表/视图、不授额外权限、不回查业务旧CDM。测试test_donghua_readiness_pg16在同一合成布局删去全部10表，并验证反射读取空、正式snapshot读取为派生资料或显式SourceEvidenceUnavailable；不接受裸UndefinedTable或吞QueryError。可选缺表仅是门禁条件，不意味着所有相关规则可交付确定结论。

| 缺失对象 | 影响及已有路径 | 不足时行为 |
|---|---|---|
| admission_record_diagnosis | 入院诊断关联；source_evidence_reader._read_cache_diagnosis_source / cache_document_source_adapter，读同三键admission_record及diagnosis，绑定原文栏目/document_id | 无可靠关联或父资料则来源不可用，不以空子表判未写 |
| first_course_record_diagnosis | 首程诊断关联；同上，父first_course_record及diagnosis | 同上；不按诊断序号跨文书借值 |
| discharge_record_diagnosis | 出院诊断关联；同上，父discharge_record及diagnosis；首页导出独立模式直接diagnosis | 无资料则明确not_observed/来源不可用 |
| mr_diagnosis | 首页诊断；已有homepage_diagnoses从同三键diagnosis受控投影；current frontpage_view独立模式已映射diagnosis | 无可识别首页诊断则来源不可用；导出不查询旧子表 |
| exam_master | 检查主单/关注事项来源之一；exam_item_report与批准的非药物检查医嘱仍分别可读 | 不伪造主单或关联；需要该来源的证据未决，不自动认定未检查 |
| exam_item | 检查明细/条件读取；其缺失不关闭已有exam_item_report | 没有正式同义替代声明，跳过缺表或显式不可用 |
| inpat_prescription | 处方来源 | 无批准替代映射，所需事件不可用，不能用药品医嘱冒充处方 |
| inpat_prescription_item | 处方明细及关联 | 同上，不将缺少供给解释成未开药 |
| medical_order | source_registry已声明由inpat_nondrug_order/inpat_drug_order派生的逻辑来源 | 只用既有派生合同；不能拼一张新物理medical_order，派生不充分则未决 |
| physician_change_event | 医师变更/交接班；执行器保留既有文书签名推导路径，三键、时间和身份需可靠 | 不凭空补事件或把无表认定无变更；缺可靠资料仍未决 |

缺权限、查询超时、断连不是缺表，不新增统一吞异常处理。原诊断adapter对特定兼容子表错误有既定受控父源路径，仍只读同一独立库且保留真实故障；本轮未扩大其允许范围。新增PG测试覆盖10表元数据/取材接口；各医学规则最终判定及真实模型质量未逐条重验。

## 12个A类无accepted40直接映射对象：请同步侧确认供给

“无直接映射”不等于无其他供给；下表只说明功能影响，不能通过改名或建空表补齐。规则关联为源码registry依赖，不代表每条规则必然阻断。

| 对象 | 功能影响与需确认信息 |
|---|---|
| blood_application | 输血申请/适应性及申请与输血记录关联（07-01-01/02、07-04-02）；确认申请事件键、时间、正文、状态及与输血记录的关联 |
| diffcase_discussion_record | 疑难讨论领域及正式规则病程候选；确认文书正文/状态/时刻与所属住院期；不能用普通病程自动冒充讨论 |
| handoff_record | 交接班/病程候选及医师变更核对；确认交班、接班方向与时间语义 |
| handover_record | 同属交接班领域但独立对象；需证明与handoff的差异/关联，不能按名称合并 |
| inpat_bill_item | 输血费用/住院收费关联（07-04-02）；确认项目键、计费/撤销状态、金额和时间，费用不能证明已输血 |
| mr_cost | 首页费用展示及frontpage Bundle/capture预读；需确认首页费用来源，不额外抽取真实费用或据空值判医学缺陷 |
| postane_surveil_record | 麻醉后访视、麻醉相关文书核对（04-04-01/02）；确认实际访视时刻及正文 |
| preane_surveil_record | 麻醉前访视（04-04-01/02）；不能用麻醉后记录代替，确认状态和有效时间 |
| summary_record | 阶段小结领域及10-04-01；确认小结类型、形成时间、正文及住院期关联 |
| surgery_application | 手术申请与计划（04-02-01/02、04-03-01）；计划不是已实施，确认计划时刻、取消/停止等状态 |
| surgery_inform_consent | 手术知情同意及签署内容核对（04-04-02/03及11族）；确认文书/签名/提交时间各自语义，不混为执行时间 |
| surgery_record | 手术正文、台次实施与时间、术式及多个正式规则的候选；确认开始/结束时刻、组件/修订关系、状态及与mr_surgery关联 |

全部对象当前即使存在且结构匹配，仍需分别标来源未启用/未发布/失败/已发布零样本/字段无供给/已有材料。不得只用成功批次或pending全表数量证明完整。没有确认的供给和窗口，不启用真实取材。

## 验证与边界

实际运行命令（backend目录）：

```text
python -B scripts/run_donghua_readiness_pg16.py --data-directory <独立工作树>/.tmp/cdm-pg16/data
python -B scripts/run_qc_scheduler_tests.py --profile offline tests/unit/test_clinical_sources.py::test_registered_pdf_read_survives_disabled_legacy tests/unit/test_single_donghua_source.py::test_historical_results_kept_without_recomputing
```

PG16.15使用现有本机二进制，仅新建本分支owned集群，127.0.0.1:62997，专属data_directory及cluster_name经joint_pg_support验证。禁网、禁模型、禁止非owned数据库/角色；两个物理合成库，同键不同资料；fixture核对源数据/序列指纹不变及错源/写入尝试为0。6项PG16定向通过（内含10缺表读取与派生边界），4项PDF/历史保护通过。目录默认loader传真实业务factory参数；首页导出在业务engine设None时仍读独立CDM，机构错误拒绝。

首轮PR8入口直接跑两个旧单元文件曾有4项夹具初始化错误（未配置业务存储），不宣称该集合通过；最终改用现有scheduler隔离入口，仅跑本任务相关4项历史/PDF保护。开发过程中投影抽取遗留局部变量错误已由PG测试捕获并修复，不计作基线问题。未跑全量、前端、真实服务器、模型或27份。

本机候选可交独立复审；现场仍BLOCKED：批准角色/凭据、类型与字段实际供给、失败后继及受控窗口未确认。CHECKSUMS列名证据继续有效，不新增服务器结构普查。本轮没有新增CDM对象或字段读取需求；只是共用现有投影、加强已读取ORM字段的预检。


## 账号增量授权交接及patient_information预检补修

复用同步Agent/DSH结果包cache-cdm-column-grant-delta-result.zip，SHA256 ba1be322d9cb8e5f57103f49ccbf9b5dd0af72c4ee5900c288ac30578891b483，本机实核外层及内部CHECKSUMS 8/8通过。现场19条列级GRANT单事务提交，348项由0变为348/348，19对象以medqc_cdm_ro执行LIMIT 0均PASS。表级SELECT仍30，patient_information原2键权限不变。这是DSH现场证据，本机未连接服务器；19个已确认投影权限缺口可关闭，不重复授权或普查结构。

本机在49f9891e8之上补修read_columns：patient_information无visit_id时，真实三键取材在SQL前返回空，现有消费者只有身份键/EXISTS；预检仅检查institute_id/patient_id，不再为过预检要求额外8列。缺必要键仍报columns_missing，缺键SELECT仍报select_denied；若未来增加visit_id则恢复通用真实投影检查，不永久豁免正文权限。没有修改其他对象投影和现有权限拒绝策略。

隔离PG16.15定向实际3项通过：patient最小两键授权通过、缺patient_id权限明确拒绝（两项都验证未来三键形态仍检查record_content），加既有newborn_record列权案例证明其他对象正常。沿本分支owned集群运行，禁网禁模型及业务库连接护栏不变；未重复前轮6项、4项或全量。Ruff F及diff检查通过。未执行新的DSH预检、没有推送、部署或修改现场权限/凭据/配置；不能把3项合成测试当作新版本现场验收。

状态更新：ACCOUNT_TCP_READY；19对象投影权限已验证；本机预检误报已修，待独立复审。整体现场业务接入仍未READY：新业务预检未执行、字段实际供给/类型/语义及受控发布窗口未确认。早期正文的账号/凭据UNCONFIRMED属于49f9891e8时点记录，不再代表当前账号状态。


## Astra复审两项P2补修（基于72786986c）

- 所有权：账号层检查当前角色及SET ROLE可达角色是否拥有目标数据库、cdm schema、cdm关系或函数，不能用撤销ACL后的“无写权”冒充无DDL/自授权能力。对象层增加owns_object并返回object_ownership_forbidden。普通列级SELECT准入、列写权限拒绝、缺表及publication未知语义不变。这里修复的是预检边界，未发现或声称现场medqc_cdm_ro实际拥有对象。
- HTTP：medical_records公共错误owner原样传播HTTPException（status/detail/headers），防止首页导出机构冲突403被改写成503；未知源异常继续脱敏503，未扩大读取范围。

必要验证：owned原生PG16两项所有权反例通过，分别当前角色所有者及NOINHERIT但可SET的角色所有者；先撤全部ACL写权，只保留SELECT，预检仍应拒绝且account_read_only=false。两项patient最小列权/真实缺权保护通过，未重复其他PG集合。首次所有权测试夹具因移交owner导致指纹观察账号失去SELECT而失败；补回该合成观察账号的SELECT后反例通过，不作为产品失败/通过数混计。HTTP禁网5项通过，实际调用首页导出冲突入口且禁止其读取材料，另核对403/404/409对象原样传播与未知异常503脱敏。Ruff F、AST、UTF-8无BOM/LF和diff检查通过。

两项反例具备工程修后依据，仍待Astra在固定新提交复审；未自动解决GitHub审查意见、推送、合并或部署。所有PG授权/owner变化仅属于本分支owned合成库，未触碰现场、本机既有业务库、同步服务或任何凭据。没有调用模型、重跑27份或修改医学判定。现场字段供给及受控发布窗口仍未验收。
