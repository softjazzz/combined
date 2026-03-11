# CDM 已对接接口清单

> 泸县人民医院 HIS（东华医为 iMedical V8.4）CDM V1.0 视图接口对接状态

## 数据库连接信息

| 项目 | 值 |
|------|-----|
| 地址 | 192.168.140.4 |
| 数据库 | dhc-app |
| 账户 | Baidu |
| 密码 | Baidu |

---

## 第一批接口（20 个）

| # | 存储过程 | 中文名 | CDM 表名 | 备注 |
|---|---------|--------|----------|------|
| 1 | `web.discharge_record("2022-01-01")` | 出院记录 | discharge_record | |
| 2 | `web.mr("2023-02-02")` | 病案首页 | mr | ✅ ok |
| 3 | `web.mr_surgery("2023-02-02")` | 病案首页手术记录明细 | mr_surgery | ✅ ok |
| 4 | `web.mr_cost("2023-02-02")` | 病案首页费用明细 | mr_cost | ✅ ok |
| 5 | `web.labtest_master("2023-02-02")` | 检验申请 | labtest_master | |
| 6 | `web.labtest_item_report("2023-02-02")` | 检验报告 | labtest_item_report | |
| 7 | `web.labtest_item("2023-02-02")` | 检验项目 | labtest_item | |
| 8 | `web.medical_insurance_settlement_cost("2023-02-02","2023-02-02")` | 医保结算清单费用明细 | medical_insurance_settlement_cost | 增加4字段：甲类/乙类/自费/其他金额 |
| 9 | `web.mr_bloodtrans("2023-02-02")` | 病案首页输血记录明细 | mr_bloodtrans | 首页无相关数据，取发血记录 |
| 10 | `web.mr_icu("2023-02-02","2023-02-02")` | 病案首页重症监护记录明细 | mr_icu | |
| 11 | `web.medical_insurance_settlement("2023-02-02","2023-02-02")` | **医保结算清单** | medical_insurance_settlement | |
| 12 | `web.inpat_drug_order("2023-02-02","2023-02-02")` | 住院药品医嘱 | inpat_drug_order | ✅ ok |
| 13 | `web.inpat_nondrug_order("2023-02-02","2023-02-02")` | 住院非药品医嘱 | inpat_nondrug_order | ✅ ok |
| 14 | `web.inpat_bill_item("2023-02-02","2023-02-02")` | 住院费用明细 | inpat_bill_item | ✅ ok，医保费用明细与本表一致 |
| 15 | `web.exam_item_report("2023-02-02","2023-02-02")` | 检查报告 | exam_item_report | ✅ ok |
| 16 | `web.pathology_exam_master("2023-02-02","2023-02-02")` | 病理检查申请单 | pathology_exam_master | ✅ ok |
| 17 | `web.pathology_exam_report("2023-02-02","2023-02-02")` | 病理检查报告 | pathology_exam_report | ✅ ok，增加病理诊断Diagnosis字段 |
| 18 | `web.mr_customize("2023-02-02")` | 病案首页医院自定义明细 | mr_customize | |
| 19 | `web.diagnosis("2023-02-02")` | 诊断表 | diagnosis | ✅ ok |
| 20 | `web.epidemic_record("2023-02-02")` | 传染病报告记录 | epidemic_record | 传染病已更换易欧，HIS只有到年初数据 |

---

## 第二批接口（37 个）

| # | 存储过程 | 中文名 | CDM 表名 | 备注 |
|---|---------|--------|----------|------|
| 1 | `web.outpat_record("2023-01-08")` | 门诊病历 | outpat_record | 按就诊时间 |
| 2 | `web.daily_course_record("2022-01-01")` | 日常病程记录 | daily_course_record | |
| 3 | `web.surgery_application("2023-01-08")` | 手术申请 | surgery_application | |
| 4 | `web.surgery_record("2023-01-08")` | 手术记录 | surgery_record | |
| 5 | `web.surgery_risk_assessment("2023-01-08")` | 手术风险评估 | surgery_risk_assessment | |
| 6 | `web.postsurg_firstcourse_record("2022-01-08")` | 术后首次病程记录 | postsurg_firstcourse_record | |
| 7 | `web.docpat_commu_record("2022-01-08")` | 医患沟通记录 | docpat_commu_record | |
| 8 | `web.handoff_record("2023-01-08")` | 交班记录 | handoff_record | |
| 9 | `web.handover_record("2023-01-08")` | 接班记录 | handover_record | |
| 10 | `web.consultation_record("2023-01-08")` | 会诊记录 | consultation_record | |
| 11 | `web.senior_course_record("2023-01-08")` | 上级医师查房记录 | senior_course_record | |
| 12 | `web.first_course_record("2023-01-08")` | 首次病程记录 | first_course_record | |
| 13 | `web.diffcase_discussion_record("2023-01-08")` | 疑难病例讨论记录 | diffcase_discussion_record | |
| 14 | `web.admission_record("2023-01-08")` | 入院记录 | admission_record | |
| 15 | `web.death_discussion("2023-01-01")` | 死亡病例讨论记录 | death_discussion | |
| 16 | `web.death_record("2023-01-08")` | 死亡记录 | death_record | |
| 17 | `web.daily_admission_record("2023-01-08")` | 24小时入出院记录 | daily_admission_record | |
| 18 | `web.daily_death_record("2023-01-08")` | 24小时入院死亡记录 | daily_death_record | |
| 19 | `web.presurg_discussion("2023-01-08")` | 术前讨论 | presurg_discussion | |
| 20 | `web.summary_record("2022-01-08")` | 阶段小结 | summary_record | |
| 21 | `web.rescue_record("2022-01-06")` | 抢救记录 | rescue_record | |
| 22 | `web.presurg_summary("2022-01-08")` | 术前小结 | presurg_summary | |
| 23 | `web.preane_surveil_record("2022-01-08")` | 麻醉术前访视记录 | preane_surveil_record | |
| 24 | `web.postane_surveil_record("2022-01-08")` | 麻醉术后访视记录 | postane_surveil_record | |
| 25 | `web.surgery_inform_consent("2022-01-08")` | 手术知情同意书 | surgery_inform_consent | |
| 26 | `web.nursing_record("2022-01-08")` | 护理记录 | nursing_record | |
| 27 | `web.crisis_value_record("2023-02-02")` | 危机值记录 | crisis_value_record | |
| 28 | `web.newborn_record("2023-01-30")` | 新生儿记录 | newborn_record | ✅ ok |
| 29 | `web.blood_application("2023-02-02")` | 输血申请单 | blood_application | ✅ ok |
| 30 | `web.bloodtrans_record("2023-02-02")` | 输血记录 | bloodtrans_record | 取病程记录的输血记录 |
| 31 | `web.anesthesia_record("2023-02-02")` | 麻醉记录 | anesthesia_record | |
| 32 | `web.surgery_safecheck_record("2023-02-02")` | 手术安全核查记录 | surgery_safecheck_record | |
| 33 | `web.surgery_inventory_record("2023-02-02")` | 手术清点记录 | surgery_inventory_record | |
| 34 | `web.transfer_out_record("2023-01-08")` | 转出记录 | transfer_out_record | |
| 35 | `web.transfer_in_record("2023-01-08")` | 转入记录 | transfer_in_record | |
| 36 | — | 医保费用明细 | medinsur_bill_item | 同住院费用明细一致 |
| 37 | — | 病理会诊申请 | pathology_consultation_master | 同病理检查申请单 |

---

## 接口等价关系

| 实际使用 | 等价于 |
|---------|--------|
| `inpat_bill_item`（住院费用明细） | `medinsur_bill_item`（医保费用明细） |
| `pathology_exam_master`（病理检查申请单） | `pathology_consultation_master`（病理会诊申请） |

---

## 未对接的 CDM 表（对比目录）

以下表在 CDM V1.0 标准中有定义，但**尚未对接**：

- 机构主索引 (institute_master_index)
- 患者信息 (patient_information) — CDM 模型有，但无独立存储过程
- 患者交叉主索引 (patient_master_index) — CDM 模型有，但无独立存储过程
- 入院登记 (inpat_registration) — CDM 模型有，但无独立存储过程
- 门诊挂号/处方/费用等门诊系列
- 住院处方/处方明细
- 住院费用结算 (inpat_receipt)
- 中医病案首页系列
- 病案首页（病案科）系列
- 健康档案/慢病随访等公卫系列
- 生命体征记录 (vital_sign_record)
- 麻醉知情同意书 (anethesia_inform_consent)
- 特殊治疗知情同意书 (special_treat_inform_consent)
- 其他知情同意书 (extent_inform_consent)
- 重大特殊手术审批单 (special_surgery_approval)
- 有创诊疗操作记录 (operation_record)

---

## 与医保结算清单生成相关的关键接口

生成**医保结算清单**所需的数据，已对接的核心接口：

| 清单章节 | 数据来源接口 | 状态 |
|---------|------------|------|
| 基本信息 | `mr`（病案首页）→ 含姓名/性别/年龄/证件/地址/联系人等 | ✅ 已对接 |
| 住院诊疗信息 | `mr` + `diagnosis` + `mr_surgery` | ✅ 已对接 |
| 手术记录明细 | `mr_surgery` | ✅ 已对接 |
| 费用信息 | `mr_cost` + `medical_insurance_settlement_cost` | ✅ 已对接 |
| 医保结算清单主表 | `medical_insurance_settlement` | ✅ **已对接** |
| 医保结算清单费用明细 | `medical_insurance_settlement_cost` | ✅ **已对接** |

> [!IMPORTANT]
> `medical_insurance_settlement`（医保结算清单）和 `medical_insurance_settlement_cost`（医保结算清单费用明细）均已在第一批接口中对接，可以直接从 HIS 拉取完整的医保结算清单数据！

---

## 本地 PG 数据库说明

### 连接信息

| 项目 | 值 |
|------|------|
| 主机 | `localhost` |
| 端口 | `5432` |
| 用户名 | `postgres` |
| 密码 | `lxry888` |
| 数据库名 | `medqc` |
| 连接字符串 | `postgresql://postgres:lxry888@localhost:5432/medqc` |

### 数据库状态概览

- **总表数**：59 张（从初始 34 张扩充而来）
- **有数据**：30 张（共 1211+ 行 mock 数据）
- **空表**：29 张（含未覆盖的文书类型和系统表）
- **数据标记**：所有 mock 数据 `institute_id = 'LX001'`

### 全部 59 张表及数据行数

| # | 表名 | 中文 | 行数 | 来源批次 |
|---|------|------|------|---------|
| 1 | `admission_record` | 入院记录 | 36 | 第二批 |
| 2 | `anesthesia_record` | 麻醉记录 | 9 | 第二批 |
| 3 | `blood_application` | 输血申请单 | 1 | 第二批 |
| 4 | `bloodtrans_record` | 输血记录 | 0 | 第二批 |
| 5 | `consultation_record` | 会诊记录 | 0 | 第二批 |
| 6 | `crisis_value_record` | 危急值记录 | 0 | 第二批（新建） |
| 7 | `daily_admission_record` | 24小时入出院记录 | 0 | 第二批（新建） |
| 8 | `daily_course_record` | 日常病程记录 | 72 | 第二批 |
| 9 | `daily_death_record` | 24小时入院死亡记录 | 0 | 第二批（新建） |
| 10 | `death_discussion` | 死亡病例讨论记录 | 0 | 第二批 |
| 11 | `death_record` | 死亡记录 | 0 | 第二批 |
| 12 | `diagnosis` | 诊断表 | 37 | 第一批 |
| 13 | `diffcase_discussion_record` | 疑难病例讨论记录 | 0 | 第二批 |
| 14 | `discharge_record` | 出院记录 | 36 | 第一批 |
| 15 | `docpat_commu_record` | 医患沟通记录 | 0 | 第二批（新建） |
| 16 | `epidemic_record` | 传染病报告记录 | 0 | 第一批（新建） |
| 17 | `exam_item_report` | 检查报告 | 0 | 第一批 |
| 18 | `first_course_record` | 首次病程记录 | 36 | 第二批 |
| 19 | `handoff_record` | 交班记录 | 0 | 第二批 |
| 20 | `handover_record` | 接班记录 | 0 | 第二批 |
| 21 | `inpat_bill_item` | 住院费用明细 | 202 | 第一批（新建） |
| 22 | `inpat_drug_order` | 住院药品医嘱 | 105 | 第一批（新建） |
| 23 | `inpat_nondrug_order` | 住院非药品医嘱 | 70 | 第一批（新建） |
| 24 | `inpat_registration` | 入院登记 | 0 | 系统表 |
| 25 | `labtest_item` | 检验项目 | 140 | 第一批（新建） |
| 26 | `labtest_item_report` | 检验报告 | 2 | 第一批 |
| 27 | `labtest_master` | 检验申请 | 70 | 第一批（新建） |
| 28 | `medical_insurance_settlement` | **医保结算清单** | 33 | 第一批（新建） |
| 29 | `medical_insurance_settlement_cost` | 医保结算清单费用明细 | 165 | 第一批（新建） |
| 30 | `medinsur_receipt` | 医保费用结算 | 33 | 第一批（新建） |
| 31 | `mr` | 病案首页 | 35 | 第一批 |
| 32 | `mr_bloodtrans` | 病案首页输血明细 | 1 | 第一批（新建） |
| 33 | `mr_cost` | 病案首页费用明细 | 35 | 第一批 |
| 34 | `mr_customize` | 病案首页自定义明细 | 35 | 第一批（新建） |
| 35 | `mr_icu` | 病案首页重症监护明细 | 3 | 第一批（新建） |
| 36 | `mr_surgery` | 病案首页手术明细 | 9 | 第一批 |
| 37 | `newborn_record` | 新生儿记录 | 0 | 第二批 |
| 38 | `nursing_record` | 护理记录 | 35 | 第二批 |
| 39 | `outpat_record` | 门急诊病历 | 0 | 第二批（新建） |
| 40 | `pathology_exam_master` | 病理检查申请单 | 0 | 第一批（新建） |
| 41 | `pathology_exam_report` | 病理检查报告 | 0 | 第一批（新建） |
| 42 | `patient_information` | 患者信息 | 0 | 系统表 |
| 43 | `postane_surveil_record` | 麻醉术后访视 | 9 | 第二批（新建） |
| 44 | `postsurg_firstcourse_record` | 术后首次病程记录 | 9 | 第二批 |
| 45 | `preane_surveil_record` | 麻醉术前访视 | 9 | 第二批（新建） |
| 46 | `presurg_discussion` | 术前讨论 | 9 | 第二批 |
| 47 | `presurg_summary` | 术前小结 | 9 | 第二批 |
| 48 | `qc_result` | 质控结果 | 0 | 系统表 |
| 49 | `rescue_record` | 抢救记录 | 0 | 第二批 |
| 50 | `senior_course_record` | 上级医师查房记录 | 35 | 第二批 |
| 51 | `summary_record` | 阶段小结 | 0 | 第二批 |
| 52 | `surgery_application` | 手术申请 | 9 | 第二批（新建） |
| 53 | `surgery_inform_consent` | 手术知情同意书 | 9 | 第二批（新建） |
| 54 | `surgery_inventory_record` | 手术清点记录 | 9 | 第二批（新建） |
| 55 | `surgery_record` | 手术记录 | 9 | 第二批 |
| 56 | `surgery_risk_assessment` | 手术风险评估 | 0 | 第二批 |
| 57 | `surgery_safecheck_record` | 手术安全核查记录 | 9 | 第二批 |
| 58 | `transfer_in_record` | 转入记录 | 0 | 第二批 |
| 59 | `transfer_out_record` | 转出记录 | 0 | 第二批 |

> 标注「新建」的表为本次新建的 25 张表，其余为原有的 34 张表。

### Mock 数据分布

基于 **35 条模拟病历**（P001~P035），覆盖心血管内科、呼吸内科、骨科、神经内科、消化内科、普外科、妇产科、内分泌科、儿科共 9 个科室。

| 类别 | 涉及表 | 数据量 | 说明 |
|------|--------|--------|------|
| **基础文书** | discharge_record / first_course_record / daily_course_record / senior_course_record / nursing_record | 各35条（日常病程72条） | 每位患者全覆盖 |
| **费用类** | inpat_bill_item / inpat_drug_order / inpat_nondrug_order / mr_cost | 202 / 105 / 70 / 35 | 每患者5~8项费用明细、3个药品医嘱、2个非药品医嘱 |
| **医保类** | medical_insurance_settlement / medical_insurance_settlement_cost / medinsur_receipt | 33 / 165 / 33 | 非自费的 33 个患者，每人 5 项费用明细 |
| **检验类** | labtest_master / labtest_item | 70 / 140 | 每患者 2 个检验申请（血常规/肝功能），每申请 2 个子项 |
| **手术全链条** | surgery_record / mr_surgery / surgery_application / surgery_inform_consent / presurg_summary / presurg_discussion / postsurg_firstcourse_record / surgery_safecheck_record / anesthesia_record / surgery_inventory_record / preane_surveil_record / postane_surveil_record | 各 9 条 | 9 个手术患者（骨科4 + 普外科4 + 妇产科1） |
| **ICU** | mr_icu | 3 | P002急性心梗 / P016脑梗 / P017脑出血 |
| **输血** | blood_application / mr_bloodtrans | 各 1 | P021 上消化道出血 |
| **自定义明细** | mr_customize | 35 | 每位患者全覆盖 |

### 数据隔离策略

| 策略 | 详情 |
|------|------|
| **测试数据标识** | 所有 mock 数据 `institute_id = 'LX001'` |
| **正式数据来源** | HIS 推送时使用真实 `institute_id`（由医院 HIS 提供），不会冲突 |
| **清理方式** | `DELETE FROM <表名> WHERE institute_id = 'LX001'` |
| **ORM 模型文件** | `backend/app/database/models/cdm.py` |
| **Seed 脚本** | `backend/scripts/seed_full_testdata.py`（可重复运行，自动跳过已有数据） |

