# DHC 系统数据接口对接清单

> **远端数据库**: `192.168.140.4` | **数据库**: `dhc-app` | **协议**: PostgreSQL  
> **数据访问方式**: 存储过程 `CALL web.xxx(date)`  
> **更新时间**: 2026-03-05

---

## 一、接口总览

| 批次 | 数量 | 类别 | 状态 |
|------|------|------|------|
| 第一批 | 20 个 | 病案首页、诊断、费用、检验检查、医保等 | 已对接 |
| 第二批 | 37 个 | 病程记录、手术、护理、知情同意等 | 已对接 |
| **合计** | **57 个** | | |

---

## 二、第一批接口（20 个）

### 核心表

| # | 存储过程 | 中文名称 | 参数 | CDM 对应表 | 工作台使用 |
|---|---------|---------|------|-----------|-----------|
| 1 | `web.mr(date)` | 病案首页 | 日期 | `mr` (MedicalRecordFrontpage) | ✅ 主数据源 |
| 2 | `web.diagnosis(date)` | 诊断表 | 日期 | `diagnosis` (Diagnosis) | ✅ 主诊断 |
| 3 | `web.discharge_record(date)` | 出院记录 | 日期 | `discharge_record` (DischargeRecord) | |
| 4 | `web.mr_surgery(date)` | 病案首页手术记录明细 | 日期 | `mr_surgery` (MrSurgery) | |
| 5 | `web.mr_cost(date)` | 病案首页费用明细 | 日期 | `mr_cost` (MrCost) | |

### 检验检查

| # | 存储过程 | 中文名称 | 参数 | CDM 对应表 |
|---|---------|---------|------|-----------|
| 6 | `web.labtest_master(date)` | 检验申请 | 日期 | — |
| 7 | `web.labtest_item_report(date)` | 检验报告 | 日期 | — |
| 8 | `web.labtest_item(date)` | 检验项目 | 日期 | — |
| 9 | `web.exam_item_report(date, date)` | 检查报告 | 起止日期 | — |
| 10 | `web.pathology_exam_master(date, date)` | 病理检查申请单 | 起止日期 | — |
| 11 | `web.pathology_exam_report(date, date)` | 病理检查报告 | 起止日期 | — |

### 费用与医保

| # | 存储过程 | 中文名称 | 参数 | CDM 对应表 |
|---|---------|---------|------|-----------|
| 12 | `web.inpat_bill_item(date, date)` | 住院费用明细 | 起止日期 | — |
| 13 | `web.medical_insurance_settlement(date, date)` | 医保结算清单 | 起止日期 | — |
| 14 | `web.medical_insurance_settlement_cost(date, date)` | 医保结算清单费用明细 | 起止日期 | — |

> 医保费用明细与住院费用明细一致  
> 增加了 4 个字段: ITEMCLAAAMT(甲类金额), ITEMCLABAMT(乙类金额), ITEMOWNPAYAMT(自费金额), ITEMOTHAMT(其他金额)

### 医嘱

| # | 存储过程 | 中文名称 | 参数 | CDM 对应表 |
|---|---------|---------|------|-----------|
| 15 | `web.inpat_drug_order(date, date)` | 住院药品医嘱 | 起止日期 | — |
| 16 | `web.inpat_nondrug_order(date, date)` | 住院非药品医嘱 | 起止日期 | — |

### 其他

| # | 存储过程 | 中文名称 | 参数 | CDM 对应表 |
|---|---------|---------|------|-----------|
| 17 | `web.mr_bloodtrans(date)` | 病案首页输血记录明细 | 日期 | — |
| 18 | `web.mr_icu(date, date)` | 病案首页重症监护记录明细 | 起止日期 | — |
| 19 | `web.mr_customize(date)` | 病案首页医院自定义明细 | 日期 | — |
| 20 | `web.epidemic_record(date)` | 传染病报告记录 | 日期 | — |

> ⚠️ 传染病已更换易欧系统，HIS 只有到年初的数据

---

## 三、第二批接口（37 个）

### 病程记录类（13 个）

| # | 存储过程 | 中文名称 | 参数 |
|---|---------|---------|------|
| 1 | `web.first_course_record(date)` | 首次病程记录 | 日期 |
| 2 | `web.daily_course_record(date)` | 日常病程记录 | 日期 |
| 3 | `web.senior_course_record(date)` | 上级医师查房记录 | 日期 |
| 4 | `web.postsurg_firstcourse_record(date)` | 术后首次病程记录 | 日期 |
| 5 | `web.rescue_record(date)` | 抢救记录 | 日期 |
| 6 | `web.summary_record(date)` | 阶段小结 | 日期 |
| 7 | `web.handoff_record(date)` | 交班记录 | 日期 |
| 8 | `web.handover_record(date)` | 接班记录 | 日期 |
| 9 | `web.consultation_record(date)` | 会诊记录 | 日期 |
| 10 | `web.diffcase_discussion_record(date)` | 疑难病例讨论记录 | 日期 |
| 11 | `web.transfer_out_record(date)` | 转出记录 | 日期 |
| 12 | `web.transfer_in_record(date)` | 转入记录 | 日期 |
| 13 | `web.docpat_commu_record(date)` | 医患沟通记录 | 日期 |

### 入院/出院/死亡记录（5 个）

| # | 存储过程 | 中文名称 | 参数 | CDM 对应表 | 工作台使用 |
|---|---------|---------|------|-----------|-----------|
| 14 | `web.admission_record(date)` | 入院记录 | 日期 | `admission_record` (AdmissionRecord) | ✅ 床位号 |
| 15 | `web.daily_admission_record(date)` | 24小时入出院记录 | 日期 | — | |
| 16 | `web.death_record(date)` | 死亡记录 | 日期 | — | |
| 17 | `web.daily_death_record(date)` | 24小时入院死亡记录 | 日期 | — | |
| 18 | `web.death_discussion(date)` | 死亡病例讨论记录 | 日期 | — | |

### 手术相关（8 个）

| # | 存储过程 | 中文名称 | 参数 |
|---|---------|---------|------|
| 19 | `web.surgery_application(date)` | 手术申请 | 日期 |
| 20 | `web.surgery_record(date)` | 手术记录 | 日期 |
| 21 | `web.surgery_risk_assessment(date)` | 手术风险评估 | 日期 |
| 22 | `web.presurg_discussion(date)` | 术前讨论 | 日期 |
| 23 | `web.presurg_summary(date)` | 术前小结 | 日期 |
| 24 | `web.surgery_inform_consent(date)` | 手术知情同意书 | 日期 |
| 25 | `web.surgery_safecheck_record(date)` | 手术安全核查记录 | 日期 |
| 26 | `web.surgery_inventory_record(date)` | 手术清点记录 | 日期 |

### 麻醉相关（2 个）

| # | 存储过程 | 中文名称 | 参数 |
|---|---------|---------|------|
| 27 | `web.preane_surveil_record(date)` | 麻醉术前访视记录 | 日期 |
| 28 | `web.postane_surveil_record(date)` | 麻醉术后访视记录 | 日期 |
| 29 | `web.anesthesia_record(date)` | 麻醉记录 | 日期 |

### 输血相关（2 个）

| # | 存储过程 | 中文名称 | 参数 |
|---|---------|---------|------|
| 30 | `web.blood_application(date)` | 输血申请单 | 日期 |
| 31 | `web.bloodtrans_record(date)` | 输血记录 | 日期 |

### 护理与其他（5 个）

| # | 存储过程 | 中文名称 | 参数 |
|---|---------|---------|------|
| 32 | `web.nursing_record(date)` | 护理记录 | 日期 |
| 33 | `web.crisis_value_record(date)` | 危急值记录 | 日期 |
| 34 | `web.newborn_record(date)` | 新生儿记录 | 日期 |
| 35 | `web.outpat_record(date)` | 门诊病历 | 日期 |

> 病理会诊申请 → 同病理检查申请单

---

## 四、V4 工作台卡片字段来源

V4 工作台卡片所需的 **全部 13 个字段** 均来自已对接的存储过程：

| 卡片字段 | CDM 字段名 | 数据来源 | 存储过程 |
|---------|-----------|---------|---------|
| 床位号 | `bed_no` | `admission_record` | `web.admission_record()` |
| 姓名 | `name` | `mr` | `web.mr()` |
| 性别 | `sex` | `mr` | `web.mr()` |
| 年龄 | `age_year` | `mr` | `web.mr()` |
| 科室 | `discharge_dept_name` | `mr` | `web.mr()` |
| 医保类型 | `insurance_type` | `mr` | `web.mr()` |
| 入院日期 | `admission_datetime` | `mr` | `web.mr()` |
| 出院日期 | `discharge_datetime` | `mr` | `web.mr()` |
| 住院天数 | `hospital_duration` | `mr` | `web.mr()` |
| 主管医生 | `attending_physician_sign` | `mr` | `web.mr()` |
| 病案号 | `mr_no` | `mr` | `web.mr()` |
| 主诊断名 | `diagnosis_name` | `diagnosis` | `web.diagnosis()` |
| ICD 编码 | `diagnosis_code` | `diagnosis` | `web.diagnosis()` |

---

## 五、未对接的 CDM 表

以下 CDM 表在远端 **没有对应存储过程**，不纳入 ETL 同步范围：

| CDM 表 | 说明 | 影响 |
|--------|------|------|
| `patient_information` | 患者基本信息表 | 无影响 — 患者信息已包含在 `mr` 中 |
| `inpat_registration` | 入院登记表 | 无影响 — 入院信息已包含在 `mr` 和 `admission_record` 中 |

---

## 六、待确认事项

1. **字段名映射** — 存储过程返回的列名可能和 CDM 字段名不一致（如大小写、下划线等），需实际调用一次确认
2. **参数含义** — 日期参数是出院日期、入院日期、还是数据更新时间？需确认
3. **数据编码** — 性别是返回"男/女"还是"1/2"？医保类型的编码规则？
