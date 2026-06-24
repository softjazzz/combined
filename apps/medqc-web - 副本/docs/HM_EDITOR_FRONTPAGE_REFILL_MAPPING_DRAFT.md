# MedQC `FrontPageDraft` -> HM Editor 住院病案首页回填映射表（草案）

目标：把 MedQC 一键生成得到的 `FrontPageDraft`（结构化 JSON）回填到 `hm_editor` 的住院病案首页模板控件中，用于“可编辑/可打印”的真实演示效果。

## 范围与约定

- **HM 模板**：`hm_editor/hmEditor/demo/file/inpatient_record.html`
- **回填定位方式**：优先按 `data-hm-code="DE..."` 定位控件，其次按 `data-hm-name`
- **字段路径口径**：本文以后端 `apps/medqc-web/backend/app/schemas/frontpage.py` 的 **snake_case** 为准（前端 TS 类型可能是 camelCase，但实际 API 响应字段以 snake_case 为主）
- **未覆盖字段**：HM 模板缺失或只提供 label（无输入控件）的字段，在“备注”里标记为“模板需补字段”

## 映射表（推荐优先做的核心字段）

| MedQC 字段路径 | HM `data-hm-name` | HM `data-hm-code` | HM 控件类型 | 回填备注/转换 |
|---|---|---:|---|---|
| `hospitalization.hospital_name` | 医疗机构名称 | `DE08.10.013.00.012` | `newtextbox` | 直接填文本 |
| `hospitalization.medical_record_no` | 病案号 | `DE01.00.004.00` | `newtextbox` | 直接填文本 |
| `hospitalization.admission_times_in_hospital` | 住院次数 | `DE02.10.090.00` | `newtextbox` | 数字；空时可默认 `1` |
| `hospitalization.payment_method` | 医疗付费方式代码 | `DE07.00.007.00` | `newtextbox` | 期望“编码”；若仅有 `payment_method_text`，可先临时回填文本并标记“待编码映射” |
| `hospitalization.admission_way` | 入院途径代码 | `DE06.00.339.00` | `newtextbox` | 同上：优先编码，缺失时可临时填 `admission_way_text` |
| `hospitalization.admission_dept` | 入院科别 | `DE08.10.026.00.022` | `newtextbox` | 直接填文本 |
| `hospitalization.admission_ward` | 入院病房 | `DE01.00.019.00.003` | `newtextbox` | 直接填文本 |
| `hospitalization.admission_datetime` | 入院时间 | `DE06.00.092.00` | `timebox` | 建议格式 `YYYY-MM-DD HH:mm:ss` |
| `hospitalization.discharge_dept` | 出院科别 | `DE08.10.026.00.024` | `newtextbox` | 直接填文本 |
| `hospitalization.discharge_ward` | 出院病房 | `DE01.00.019.00.004` | `newtextbox` | 直接填文本 |
| `hospitalization.discharge_datetime` | 预出院时间 | `DE06.00.017.00` | `timebox` | HM 模板缺“出院时间”，先回填到“预出院时间”（或需要扩展模板） |
| `hospitalization.actual_hospital_days` | 住院天数 | `DE06.00.310.00` | `newtextbox` | 数字 |
| `basic_info.patient_name` | 姓名 | `DE02.01.039.00` | `newtextbox` | 直接填文本 |
| `basic_info.gender` | 首页_性别 | `DE99.09.001.79` | `newtextbox` | 建议填 `1/2`（男/女）；若只有 `gender_text`，需映射为编码 |
| `basic_info.birth_date` | 出生日期 | `DE02.01.005.01` | `timebox` | 建议格式 `YYYY-MM-DD` |
| `basic_info.age_years` | 年龄 | `DE02.01.026.00` | `newtextbox` | 年龄（岁）；HM 还有 `年龄_月/年龄_日` 可选扩展 |
| `basic_info.nationality` | 国籍代码 | `DE02.01.015.00` | `newtextbox` | HM 字段名是“代码”，但 MedQC 当前多为文本；建议后续引入国籍编码表 |
| `basic_info.ethnicity` | 民族 | `DE02.01.025.00` | `newtextbox` | 直接填文本或民族代码（视模板约定） |
| `basic_info.marital_status` | 婚姻状况代码 | `DE02.01.018.00` | `newtextbox` | 期望编码；缺失时可映射 `marital_status_text -> code` |
| `basic_info.id_number` | 身份证号码 | `DE02.01.030.00` | `newtextbox` | 直接填文本 |
| `basic_info.occupation` | 职业类别代码 | `DE02.01.052.00` | `newtextbox` | 期望编码；MedQC 当前为文本，需要后续映射表 |
| `basic_info.current_address` | 住址_门牌号码 | `DE02.01.009.06.005` | `newtextbox` | MedQC 是整段地址，先整体回填到门牌号字段（或拆分扩展） |
| `basic_info.contact_name` | 联系人姓名 | `DE02.01.039.00.144` | `newtextbox` | 直接填文本 |
| `basic_info.contact_relation` | 联系人与患者的关系代码 | `DE02.10.024.00.005` | `newtextbox` | 期望编码；可先填文本并标“待映射” |
| `basic_info.contact_phone` | 联系人电话 | `DE02.01.010.00.017` | `newtextbox` | 直接填文本 |
| `diagnoses.ed_diagnosis_texts[0]` | 门急诊诊断名称 | `DE05.01.025.00.016` | `searchbox` | 先回填第一条；更多条需扩展模板/多行控件 |
| `diagnoses.ed_diagnosis_codes[0]` | 门急诊诊断疾病编码 | `DE05.01.024.00.046` | `searchbox` | 当前阶段 MedQC 不填；待 ICD 编码系统接入 |
| `diagnoses.discharge_main_diagnosis_text` | 出院西医诊断_名称 | `DE05.01.025.00.009` | `searchbox` | 直接回填文本 |
| `diagnoses.discharge_main_icd` | 出院西医诊断_编码 | `DE05.01.024.00.044` | `searchbox` | 当前阶段 MedQC 不填；待 ICD 编码系统接入 |
| `diagnoses.admission_condition` | 出院西医诊断_主要诊断_入院病情代码 | `DE09.00.104.00.002` | `newtextbox` | 期望编码：1 有 2 临床未确定 3 情况不明 4 无 |
| `procedures.main_procedure_text` | 手术及操作名称_1 | `DE99.02.002.001` | `searchbox` | 直接回填文本（编码见下） |
| `procedures.main_procedure_code` | 手术及操作编码_1 | `DE99.02.001.001` | `searchbox` | 当前阶段 MedQC 不填；待编码系统接入 |
| `procedures.main_procedure_date` | 手术及操作日期_1 | `DE99.02.003.001` | `timebox` | 建议格式 `YYYY-MM-DD` |
| `procedures.main_procedure_level` | 手术级别代码_1 | `DE99.02.004.001` | `newtextbox` | 期望编码/级别；若为文本先直填并标“待规范” |
| `procedures.anesthesia_method` | 麻醉方式代码_1 | `DE99.02.010.001` | `newtextbox` | 模板按“代码”定义；MedQC 为文本时需映射 |
| `procedures.incision_healing_grade` | 手术切口愈合等级代码_1 | `DE99.02.009.001` | `newtextbox` | 同上：优先编码；缺失可先填文本 |
| `other_medical_info.pathology_no` | 病理号 | `DE01.00.005.00` | `newtextbox` | 直接填文本 |
| `other_medical_info.pathology_text` | 病理诊断名称 | `DE05.01.025.00.019` | `newtextbox` | 直接填文本 |
| `other_medical_info.abo_blood_type` | ABO血型代码 | `DE04.50.001.00` | `newtextbox` | 模板字段存在；值建议 A/B/O/AB/不详/未查 |
| `other_medical_info.rh_blood_type` | Rh血型代码 | `DE04.50.010.00` | `newtextbox` | 期望编码：1 阴 2 阳 3 不详 4 未查 |
| `other_medical_info.drug_allergy_flag` | 药物过敏标志 | `DE02.10.023.00` | `newtextbox` | 期望编码：1 无 2 有 |
| `other_medical_info.drug_allergy_drugs.join('，')` | 过敏药物 | `DE02.10.022.00` | `newtextbox` | 多值合并为字符串 |
| `costs.total_cost` | 住院总费用 | `DE07.00.010.00` | `newtextbox` | 数字 |
| `costs.self_paid` | 住院自付金额 | `DE07.00.001.00` | `newtextbox` | 数字 |
| `staff.dept_director` | 科主任签名 | `DE02.01.039.00.119` | `newtextbox` | 模板是“签名”，可先回填姓名（演示用）；严格口径需要签名/签章 |
| `staff.attending_physician` | 主治医师签名 | `DE02.01.039.00.172` | `newtextbox` | 同上 |
| `staff.resident_physician` | 住院医师签名 | `DE02.01.039.00.171` | `newtextbox` | 同上 |
| `staff.responsible_nurse` | 责任护士签名 | `DE02.01.039.00.145` | `newtextbox` | 同上 |
| `staff.coder` | 编码员签名 | `DE02.01.039.00.126` | `newtextbox` | 同上 |

## 目前“模板缺字段/需扩展模板”的关键点

以下字段在 MedQC `FrontPageDraft` 里有，但在 HM 模板中目前只有 label 或缺少对应输入控件（无法回填）：

- `procedures.surgeon_name`、`procedures.assistant1_name`、`procedures.assistant2_name`、`procedures.anesthetist_name`（模板只见到 label：术者/I助/II助/麻醉医师）
- `other_medical_info.icu_type`、`icu_enter_time`、`icu_leave_time`、`ventilation_hours`（模板无对应字段）
- `diagnoses.discharge_other_diagnoses_texts[]`：模板目前只发现一个 `出院西医诊断_其他诊断名称_11`（缺少多条“其他诊断名称/编码”的完整行）

建议做法：在不破坏现有排版的情况下，为上述字段补充 `newtextbox/searchbox/timebox` 控件，并给出稳定的 `data-hm-code`（或至少 `data-hm-name`）。

## 回填实现建议（非代码）

- 生成一个“映射表对象”：`data-hm-code -> value`，优先按 `data-hm-code` 查找 DOM 控件并写入 `new-textbox-content`/`searchbox`/`timebox` 的值。
- 对“编码字段”（字段名带“代码”）建立基础字典（性别/婚姻/付费方式/入院途径/Rh/麻醉方式等），缺失时回填文本并打上“待规范”标识（演示阶段可接受）。
