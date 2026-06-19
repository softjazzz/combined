import type {
  SyntheticCaseGoldenAnswer,
  SyntheticCaseRuleFamily,
  TestRecordDocumentForm,
} from './types'
import {
  createGoldenAnswer,
  createSyntheticDocument,
  toDateTimeLocal,
} from './syntheticCaseBuilder'

export type SyntheticCaseTemplate = {
  key: string
  name: string
  family: string
  description: string
  suggestedRuleIds: string[]
  basic: {
    caseTitle: string
    patientName: string
    sex: string
    age: number
    department: string
    mainDiagnosis?: string
    otherDiagnosesText?: string
  }
  documents: TestRecordDocumentForm[]
  goldenAnswers: SyntheticCaseGoldenAnswer[]
}

function at(base: Date, hours: number): string {
  return toDateTimeLocal(new Date(base.getTime() + hours * 60 * 60 * 1000))
}

const base = new Date('2026-06-01T08:00:00')

export const syntheticCaseTemplates: SyntheticCaseTemplate[] = [
  {
    key: 'basic-timeliness-defect',
    name: '基础时限缺陷样本',
    family: '基础时限',
    description: '用于验证入院记录、首次病程、上级医师查房等时限规则。',
    suggestedRuleIds: ['LX0609-001', 'LX0609-002', 'LX0609-005'],
    basic: {
      caseTitle: '基础时限缺陷测试',
      patientName: '测试患者甲',
      sex: '男',
      age: 62,
      department: '神经内科',
      mainDiagnosis: '脑梗死',
      otherDiagnosesText: '高血压\n2型糖尿病',
    },
    documents: [
      createSyntheticDocument('admission_record', {
        record_time: at(base, 26),
        submit_time: at(base, 27),
        title: '2026-06-02 入院记录',
        content:
          '入院记录\n患者因“言语不清伴右侧肢体乏力6小时”入院。查体：神志清楚，右侧肢体肌力4级。初步诊断：脑梗死；高血压病。入院后予完善头颅CT、凝血功能、心电图等检查，给予改善循环及控制血压治疗。',
      }),
      createSyntheticDocument('first_course_record', {
        record_time: at(base, 11),
        submit_time: at(base, 11.5),
        title: '2026-06-01 首次病程记录',
        content:
          '首次病程记录\n病例特点：老年男性，急性起病，以言语不清、右侧肢体乏力为主要表现。诊断依据：神经系统定位体征阳性，既往高血压病史。诊疗计划：完善头颅MRI及血管评估，严密观察神经功能变化。',
      }),
      createSyntheticDocument('senior_course_record', {
        record_time: at(base, 80),
        submit_time: at(base, 80.5),
        title: '2026-06-04 上级医师查房记录',
        content:
          '上级医师查房记录\n副主任医师查房后认为患者目前脑梗死诊断明确，继续抗血小板、稳定斑块及康复治疗，注意观察吞咽功能和肺部感染风险。',
      }),
    ],
    goldenAnswers: [
      createGoldenAnswer({
        qc_point_id: 'LX0609-001',
        expected_status: 'non_compliant',
        trigger_facts: ['入院时间为2026-06-01 08:00', '入院记录记录时间为2026-06-02 10:00'],
        evidence_keywords: ['入院记录', '2026-06-02', '超过24小时'],
        human_reason: '入院记录完成时间晚于入院后24小时。',
      }),
      createGoldenAnswer({
        qc_point_id: 'LX0609-002',
        expected_status: 'non_compliant',
        trigger_facts: ['入院时间为2026-06-01 08:00', '首次病程记录时间为2026-06-01 19:00'],
        evidence_keywords: ['首次病程记录', '8小时', '11小时'],
        human_reason: '首次病程记录晚于入院后8小时。',
      }),
      createGoldenAnswer({
        qc_point_id: 'LX0609-005',
        expected_status: 'non_compliant',
        trigger_facts: ['入院48小时内未见主治医师首次查房记录'],
        evidence_keywords: ['上级医师查房记录', '2026-06-04', '48小时内未见'],
        human_reason: '入院后48小时内缺少主治医师首次查房记录。',
      }),
    ],
  },
  {
    key: 'ct-mri-culture-defect',
    name: '检查检验阳性结果未分析',
    family: '检查检验',
    description: '用于验证 CT/MRI 阳性结果和细菌培养阳性结果在病程中的分析要求。',
    suggestedRuleIds: ['LX0609-012', 'LX0609-014'],
    basic: {
      caseTitle: 'CT MRI 与细菌培养测试',
      patientName: '测试患者乙',
      sex: '女',
      age: 64,
      department: '骨科',
      mainDiagnosis: '腰椎间盘突出症',
    },
    documents: [
      createSyntheticDocument('admission_record', {
        record_time: at(base, 1),
        submit_time: at(base, 1.2),
        title: '2026-06-01 入院记录',
        content:
          '入院记录\n患者因腰痛伴右下肢麻木半月入院。查体：腰椎活动受限，右下肢直腿抬高试验阳性。初步诊断：腰椎间盘突出症。',
      }),
      createSyntheticDocument('exam_report', {
        record_time: at(base, 6),
        submit_time: at(base, 6),
        title: '腰椎MRI检查报告',
        content:
          '影像检查报告\n检查类型：腰椎MRI。检查所见：L4/5椎间盘向右后方突出，压迫右侧神经根；椎管轻度狭窄。报告结论：L4/5椎间盘突出并右侧神经根受压。',
      }),
      createSyntheticDocument('lab_report', {
        record_time: at(base, 30),
        submit_time: at(base, 30),
        title: '尿培养报告',
        content:
          '检验报告\n标本：尿液。培养结果：大肠埃希菌阳性。药敏提示：对头孢曲松敏感，对左氧氟沙星耐药。',
      }),
      createSyntheticDocument('daily_course_record', {
        record_time: at(base, 10),
        submit_time: at(base, 10.2),
        title: '2026-06-01 日常病程记录',
        content:
          '日常病程记录\n患者仍诉腰痛，右下肢麻木同前。已完善腰椎MRI检查，继续予止痛、营养神经治疗。',
      }),
      createSyntheticDocument('daily_course_record', {
        record_time: at(base, 52),
        submit_time: at(base, 52.2),
        title: '2026-06-03 日常病程记录',
        content:
          '日常病程记录\n患者腰痛较前稍缓解，体温正常，继续对症治疗，嘱患者卧床休息并观察病情变化。',
      }),
    ],
    goldenAnswers: [
      createGoldenAnswer({
        qc_point_id: 'LX0609-012',
        expected_status: 'non_compliant',
        trigger_facts: [
          '2026-06-01 14:00 腰椎MRI报告阳性',
          '24小时内病程未分析神经根受压与诊疗方案关系',
        ],
        evidence_keywords: ['腰椎MRI', '神经根受压', '继续予止痛、营养神经治疗'],
        human_reason:
          'MRI阳性结果后24小时内仅记录治疗延续，未分析影像阳性结果与症状、诊断或治疗方案的关系。',
      }),
      createGoldenAnswer({
        qc_point_id: 'LX0609-014',
        expected_status: 'non_compliant',
        trigger_facts: ['尿培养大肠埃希菌阳性', '报告后24小时内病程未分析阳性菌和药敏结果'],
        evidence_keywords: ['尿培养报告', '大肠埃希菌阳性', '药敏'],
        human_reason: '培养阳性结果未在病程中及时分析并形成治疗调整依据。',
      }),
    ],
  },
  {
    key: 'consultation-quality-defect',
    name: '会诊质量缺陷样本',
    family: '会诊质量',
    description: '用于验证会诊目的、会诊意见和会诊执行记录是否清楚。',
    suggestedRuleIds: ['LX0609-020', 'LX0609-021', 'LX0609-022'],
    basic: {
      caseTitle: '会诊质量测试',
      patientName: '测试患者丙',
      sex: '男',
      age: 59,
      department: '消化内科',
      mainDiagnosis: '上消化道出血',
    },
    documents: [
      createSyntheticDocument('consultation_record', {
        record_time: at(base, 8),
        submit_time: at(base, 8.1),
        title: '会诊申请单',
        content:
          '会诊申请单\n申请科室：消化内科。申请目的：请会诊。病情摘要：患者黑便2天，伴头晕乏力，血红蛋白下降，已给予抑酸、补液治疗。申请医师：测试医师。',
      }),
      createSyntheticDocument('consultation_record', {
        record_time: at(base, 13),
        submit_time: at(base, 13.2),
        title: '会诊记录单',
        content:
          '会诊记录单\n会诊科室：普外科。会诊意见：建议完善相关检查，继续目前治疗，必要时调整用药。会诊医师：会诊医师A。',
      }),
      createSyntheticDocument('daily_course_record', {
        record_time: at(base, 36),
        submit_time: at(base, 36.1),
        title: '2026-06-02 日常病程记录',
        content:
          '日常病程记录\n患者黑便较前减少，诉乏力，继续抑酸、补液、止血治疗，密切观察生命体征及大便颜色。',
      }),
    ],
    goldenAnswers: [
      createGoldenAnswer({
        qc_point_id: 'LX0609-021',
        expected_status: 'non_compliant',
        trigger_facts: ['会诊申请目的仅写请会诊'],
        evidence_keywords: ['会诊申请单', '申请目的：请会诊', '目的不明确'],
        human_reason: '会诊目的未说明具体需要解决的问题。',
      }),
      createGoldenAnswer({
        qc_point_id: 'LX0609-022',
        expected_status: 'non_compliant',
        trigger_facts: ['会诊意见使用必要时调整用药等泛化表述'],
        evidence_keywords: ['会诊记录单', '必要时调整用药', '不具备可执行性'],
        human_reason: '会诊意见缺少明确处理方案或可执行措施。',
      }),
      createGoldenAnswer({
        qc_point_id: 'LX0609-020',
        expected_status: 'non_compliant',
        trigger_facts: ['后续病程未记录会诊意见执行情况'],
        evidence_keywords: ['日常病程记录', '继续抑酸、补液、止血治疗', '未记录执行情况'],
        human_reason: '病程未说明会诊意见是否采纳及执行结果。',
      }),
    ],
  },
  {
    key: 'surgery-anesthesia-defect',
    name: '手术麻醉缺陷样本',
    family: '手术麻醉',
    description: '用于验证术后记录、手术安全核查和麻醉记录关键字段。',
    suggestedRuleIds: ['LX0609-003', 'LX0609-038'],
    basic: {
      caseTitle: '手术麻醉测试',
      patientName: '测试患者丁',
      sex: '女',
      age: 47,
      department: '普通外科',
      mainDiagnosis: '胆囊结石伴胆囊炎',
    },
    documents: [
      createSyntheticDocument('presurg_discussion', {
        record_time: at(base, 6),
        submit_time: at(base, 6.2),
        title: '术前讨论',
        content:
          '术前讨论\n患者诊断胆囊结石伴胆囊炎，有手术指征。拟行腹腔镜胆囊切除术，已讨论手术风险、替代方案及围手术期处理。',
      }),
      createSyntheticDocument('surgery_record', {
        record_time: at(base, 52),
        submit_time: at(base, 52.1),
        title: '腹腔镜胆囊切除术手术记录',
        content:
          '手术记录\n手术开始时间：2026-06-01 10:00。手术结束时间：2026-06-01 11:30。手术名称：腹腔镜胆囊切除术。术中见胆囊充血水肿，与周围组织轻度粘连，顺利切除胆囊。',
      }),
      createSyntheticDocument('anesthesia_record', {
        record_time: at(base, 53),
        submit_time: at(base, 53.1),
        title: '麻醉记录',
        content:
          '麻醉记录\n患者入室后建立静脉通路，监测生命体征。麻醉方式：。麻醉医师：王某。麻醉医师代码：。术中用药：按麻醉医嘱执行。麻醉经过平稳，术毕安返病房。',
      }),
    ],
    goldenAnswers: [
      createGoldenAnswer({
        qc_point_id: 'LX0609-003',
        expected_status: 'non_compliant',
        trigger_facts: ['手术结束时间为2026-06-01 11:30', '手术记录记录时间为2026-06-03 12:00'],
        evidence_keywords: ['手术结束时间', '记录时间', '超过术后24小时'],
        human_reason: '手术记录完成时间超过术后24小时。',
      }),
      createGoldenAnswer({
        qc_point_id: 'LX0609-038',
        expected_status: 'non_compliant',
        trigger_facts: ['存在麻醉记录', '麻醉方式、麻醉医师代码和关键用药剂量填写不完整'],
        evidence_keywords: ['麻醉记录', '麻醉方式', '填写不完整'],
        human_reason: '麻醉记录关键字段不完整。',
      }),
    ],
  },
  {
    key: 'critical-round-defect',
    name: '病重病危查房缺陷样本',
    family: '查房病程',
    description: '用于验证病重、病危医嘱期间的查房和病程记录频次。',
    suggestedRuleIds: ['LX0609-008', 'LX0609-009'],
    basic: {
      caseTitle: '病重病危查房测试',
      patientName: '测试患者戊',
      sex: '男',
      age: 78,
      department: '呼吸与危重症医学科',
      mainDiagnosis: '重症肺炎',
      otherDiagnosesText: '呼吸衰竭\n低氧血症',
    },
    documents: [
      createSyntheticDocument('medical_order', {
        record_time: at(base, 1),
        submit_time: at(base, 1),
        title: '病重病危医嘱',
        content:
          '医嘱记录\n2026-06-01 09:00 下达病重医嘱，持续执行。2026-06-02 09:00 因氧合下降下达病危医嘱，持续执行。予吸氧、抗感染、化痰、监测生命体征。允许根据病情变化调整抗菌药物。',
      }),
      createSyntheticDocument('first_course_record', {
        record_time: at(base, 2),
        submit_time: at(base, 2.1),
        title: '2026-06-01 首次病程记录',
        content:
          '首次病程记录\n患者因发热、咳嗽咳痰伴气促入院，诊断重症肺炎。入院后予抗感染、化痰、氧疗，密切观察体温、血氧饱和度和呼吸频率。',
      }),
      createSyntheticDocument('daily_course_record', {
        record_time: at(base, 73),
        submit_time: at(base, 73.2),
        title: '2026-06-04 病重病危病程记录',
        content:
          '病程记录\n患者仍有咳嗽咳痰及活动后气促，鼻导管吸氧3L/分，SpO2 94%。2026-06-02全天未见病危日常病程记录、查房记录或病情变化记录；2026-06-03未见病重患者日常病程或上级医师查房记录。本次继续抗感染、化痰和氧疗。',
      }),
      createSyntheticDocument('senior_course_record', {
        record_time: at(base, 76),
        submit_time: at(base, 76.2),
        title: '2026-06-04 上级医师查房记录',
        content:
          '上级医师查房记录\n主任医师查房后认为患者重症肺炎诊断明确，需继续氧疗和抗感染治疗，关注培养结果及呼吸功能变化。',
      }),
    ],
    goldenAnswers: [
      createGoldenAnswer({
        qc_point_id: 'LX0609-008',
        expected_status: 'non_compliant',
        trigger_facts: ['2026-06-01 09:00 下达病重医嘱', '病重期间2天内未见查房病程记录'],
        evidence_keywords: ['病重医嘱', '未见病重患者日常病程', '上级医师查房记录'],
        human_reason: '病重医嘱持续期间，2天内缺少规定的查房或病程记录。',
      }),
      createGoldenAnswer({
        qc_point_id: 'LX0609-009',
        expected_status: 'non_compliant',
        trigger_facts: ['2026-06-02 09:00 下达病危医嘱', '病危当天未见每日病程或查房记录'],
        evidence_keywords: ['病危医嘱', '全天未见病危日常病程记录', '病情变化记录'],
        human_reason: '病危医嘱期间未按日记录病程或病情变化。',
      }),
    ],
  },
  {
    key: 'transfusion-defect',
    name: '输血闭环缺陷样本',
    family: '输血',
    description: '用于验证输血知情同意、输血前检查、评估、后评价和医嘱收费一致性。',
    suggestedRuleIds: ['LX0609-041', 'LX0609-043', 'LX0609-044', 'LX0609-047', 'LX0609-049'],
    basic: {
      caseTitle: '输血闭环测试',
      patientName: '测试患者己',
      sex: '女',
      age: 66,
      department: '胃肠外科',
      mainDiagnosis: '胃恶性肿瘤',
      otherDiagnosesText: '中度贫血',
    },
    documents: [
      createSyntheticDocument('medical_order', {
        record_time: at(base, 29),
        submit_time: at(base, 29),
        title: '输血医嘱与费用记录',
        content:
          '医嘱记录\n2026-06-02 13:00 医嘱：输注去白悬浮红细胞2U。收费明细：去白悬浮红细胞4U，血型鉴定1次，交叉配血1次。医嘱与收费数量存在差异。',
      }),
      createSyntheticDocument('blood_application', {
        record_time: at(base, 27),
        submit_time: at(base, 27.2),
        title: '输血申请及输血前检查',
        content:
          '输血申请\n患者术前血红蛋白68g/L，拟输注去白悬浮红细胞2U。输血前检查已见ABO血型、Rh(D)、血常规、凝血功能、肝功能、乙肝表面抗原结果；未见丙肝抗体、HIV抗体、梅毒抗体完整报告。未见本次输血知情同意书扫描件。',
      }),
      createSyntheticDocument('daily_course_record', {
        record_time: at(base, 28),
        submit_time: at(base, 28.1),
        title: '输血前病程记录',
        content:
          '病程记录\n患者贫血，拟按医嘱输血。记录中未完整说明输血适应证、既往输血反应史、输血风险评估及输血必要性判断。',
      }),
      createSyntheticDocument('bloodtrans_record', {
        record_time: at(base, 31),
        submit_time: at(base, 31.2),
        title: '输血记录',
        content:
          '输血记录\n2026-06-02 15:00 开始输注去白悬浮红细胞2U，17:10 输注结束。输血过程未见明显寒战、皮疹或呼吸困难。',
      }),
      createSyntheticDocument('daily_course_record', {
        record_time: at(base, 34),
        submit_time: at(base, 34.1),
        title: '输血后病程记录',
        content:
          '病程记录\n患者输血后生命体征平稳，但未见输血结束后的疗效评价、血红蛋白复查结果或迟发性输血反应观察记录。',
      }),
    ],
    goldenAnswers: [
      createGoldenAnswer({
        qc_point_id: 'LX0609-041',
        expected_status: 'non_compliant',
        trigger_facts: ['存在输血医嘱和输血记录', '未见输血知情同意书'],
        evidence_keywords: ['输血申请', '未见本次输血知情同意书', '输血记录'],
        human_reason: '有输血行为但缺少输血知情同意书。',
      }),
      createGoldenAnswer({
        qc_point_id: 'LX0609-043',
        expected_status: 'non_compliant',
        trigger_facts: ['存在输血治疗', '输血前常规检查不完整'],
        evidence_keywords: ['丙肝抗体', 'HIV抗体', '梅毒抗体', '未见完整报告'],
        human_reason: '输血前相关检查资料不完整。',
      }),
      createGoldenAnswer({
        qc_point_id: 'LX0609-044',
        expected_status: 'non_compliant',
        trigger_facts: ['存在输血治疗', '输血前评估记录不完整'],
        evidence_keywords: ['输血适应证', '输血风险评估', '未完整说明'],
        human_reason: '输血前评估缺少核心要素。',
      }),
      createGoldenAnswer({
        qc_point_id: 'LX0609-047',
        expected_status: 'non_compliant',
        trigger_facts: ['输血已完成', '未见输血后评价'],
        evidence_keywords: ['输血后', '未见', '疗效评价'],
        human_reason: '输血结束后缺少疗效评价和反应观察。',
      }),
      createGoldenAnswer({
        qc_point_id: 'LX0609-049',
        expected_status: 'non_compliant',
        trigger_facts: ['医嘱红细胞2U', '收费红细胞4U'],
        evidence_keywords: ['输血医嘱', '收费明细', '数量存在差异'],
        human_reason: '输血医嘱与收费数量不一致。',
      }),
    ],
  },
  {
    key: 'tumor-pathology-chemo-defect',
    name: '肿瘤病理化疗缺陷样本',
    family: '肿瘤病理',
    description: '用于验证病理结果、取材情况和化疗医嘱/病程记录一致性。',
    suggestedRuleIds: ['LX0609-013', 'LX0609-019', 'LX0609-026'],
    basic: {
      caseTitle: '肿瘤病理化疗测试',
      patientName: '测试患者庚',
      sex: '男',
      age: 61,
      department: '胃肠外科',
      mainDiagnosis: '胃腺癌',
      otherDiagnosesText: '贫血\n低蛋白血症',
    },
    documents: [
      createSyntheticDocument('admission_record', {
        record_time: at(base, 1),
        submit_time: at(base, 1.1),
        title: '入院记录',
        content:
          '入院记录\n患者因上腹胀痛伴消瘦2月入院。胃镜提示胃窦占位，考虑胃恶性肿瘤。拟完善术前检查后行胃癌根治术。',
      }),
      createSyntheticDocument('surgery_record', {
        record_time: at(base, 32),
        submit_time: at(base, 32.2),
        title: '胃癌根治术手术记录',
        content:
          '手术记录\n手术名称：腹腔镜远端胃癌根治术。术中见胃窦部肿物，行远端胃切除及淋巴结清扫。手术记录未详细记录病理取材部位、标本固定方式及送检标签。',
      }),
      createSyntheticDocument('lab_report', {
        record_time: at(base, 72),
        submit_time: at(base, 72),
        title: '病理检查报告',
        content:
          '病理检查报告\n标本：远端胃及淋巴结。病理诊断：胃中分化腺癌，浸润至浆膜下层，淋巴结转移2/18。建议结合临床分期制定后续治疗计划。',
      }),
      createSyntheticDocument('daily_course_record', {
        record_time: at(base, 76),
        submit_time: at(base, 76.1),
        title: '术后病程记录',
        content:
          '病程记录\n患者术后恢复可，腹部切口干燥，继续补液、营养支持及抗感染治疗。病程记录未体现病理结果回看、取材情况说明及后续肿瘤治疗计划。',
      }),
      createSyntheticDocument('medical_order', {
        record_time: at(base, 96),
        submit_time: at(base, 96),
        title: '化疗医嘱',
        content:
          '医嘱记录\n2026-06-05 08:00 医嘱：奥沙利铂 130mg d1 静滴；卡培他滨 1.5g bid po d1-d14。病程记录未同步记录化疗药物名称、剂量、使用方法和时间。',
      }),
    ],
    goldenAnswers: [
      createGoldenAnswer({
        qc_point_id: 'LX0609-013',
        expected_status: 'non_compliant',
        trigger_facts: ['存在胃癌手术和病理报告', '病程未记录病理结果分析'],
        evidence_keywords: ['病理检查报告', '胃中分化腺癌', '病程记录未体现病理结果'],
        human_reason: '病理结果未在手术记录或病程中充分记录和分析。',
      }),
      createGoldenAnswer({
        qc_point_id: 'LX0609-019',
        expected_status: 'non_compliant',
        trigger_facts: ['手术记录存在取材送检场景', '取材情况记录不完整'],
        evidence_keywords: ['手术记录', '未详细记录病理取材部位', '送检标签'],
        human_reason: '手术记录中病理取材信息不完整。',
      }),
      createGoldenAnswer({
        qc_point_id: 'LX0609-026',
        expected_status: 'non_compliant',
        trigger_facts: ['存在化疗医嘱', '病程未记录化疗药物名称、剂量和时间'],
        evidence_keywords: ['化疗医嘱', '奥沙利铂', '病程记录未同步记录'],
        human_reason: '化疗病程记录与医嘱信息不一致或缺失。',
      }),
    ],
  },
]

export const syntheticCaseRuleFamilies: SyntheticCaseRuleFamily[] = [
  {
    key: 'basic_timeliness',
    name: '基础时限',
    description: '覆盖入院记录 24 小时、首次病程 8 小时、48 小时主治首次查房。',
    templateKey: 'basic-timeliness-defect',
    rules: [
      {
        ruleId: 'LX0609-001',
        name: '入院记录：入院后24小时内是否完成',
        requiredDocumentsLabel: '入院记录',
      },
      {
        ruleId: 'LX0609-002',
        name: '首次病程：入院后 8 小时内无首次病程记录',
        requiredDocumentsLabel: '首次病程记录',
      },
      {
        ruleId: 'LX0609-005',
        name: '上级医生查房记录：入院后 48 小时内无主治医师首次查房记录',
        requiredDocumentsLabel: '上级查房记录',
      },
    ],
  },
  {
    key: 'ct_mri_culture',
    name: '检查检验',
    description: '覆盖 CT/MRI 阳性结果分析与细菌培养结果分析。',
    templateKey: 'ct-mri-culture-defect',
    rules: [
      {
        ruleId: 'LX0609-012',
        name: 'CT/MRI 检查记录：影像报告结果出具后24小时内阳性结果未进行分析',
        requiredDocumentsLabel: '病程记录、检查结果',
      },
      {
        ruleId: 'LX0609-014',
        name: '细菌培养记录：细菌培养结果在病程中未记录（报告出具后24小时内）',
        requiredDocumentsLabel: '病程记录、检验报告',
      },
    ],
  },
  {
    key: 'consultation_quality',
    name: '会诊质量',
    description: '覆盖会诊目的不明确、意见不明确、无执行记录。',
    templateKey: 'consultation-quality-defect',
    rules: [
      {
        ruleId: 'LX0609-020',
        name: '会诊记录：有会诊记录单无请会诊执行记录',
        requiredDocumentsLabel: '会诊记录、日常病程记录',
      },
      {
        ruleId: 'LX0609-021',
        name: '会诊记录：会诊申请单会诊目的不明确',
        requiredDocumentsLabel: '会诊记录',
      },
      {
        ruleId: 'LX0609-022',
        name: '会诊记录：会诊记录单会诊意见不明确',
        requiredDocumentsLabel: '会诊记录',
      },
    ],
  },
  {
    key: 'surgery_anesthesia',
    name: '手术麻醉',
    description: '覆盖术后记录时限与麻醉记录关键字段缺陷。',
    templateKey: 'surgery-anesthesia-defect',
    rules: [
      {
        ruleId: 'LX0609-003',
        name: '手术记录：手术后24小时内是否完成',
        requiredDocumentsLabel: '手术记录',
      },
      {
        ruleId: 'LX0609-038',
        name: '麻醉记录单：无麻醉记录单（局麻除外）',
        requiredDocumentsLabel: '麻醉记录、手术记录',
      },
    ],
  },
  {
    key: 'critical_rounds',
    name: '查房病程',
    description: '覆盖病重、病危医嘱期间的查房和病程频次。',
    templateKey: 'critical-round-defect',
    rules: [
      {
        ruleId: 'LX0609-008',
        name: '查房记录：病重患者2天内无查房病程记录',
        requiredDocumentsLabel: '病重医嘱、日常病程、上级查房记录',
      },
      {
        ruleId: 'LX0609-009',
        name: '查房记录：病危患者未每天记录查房病程或病情变化记录',
        requiredDocumentsLabel: '病危医嘱、日常病程、病情变化记录',
      },
    ],
  },
  {
    key: 'transfusion',
    name: '输血',
    description: '覆盖输血知情同意、输血前检查、输血前后评价和医嘱收费一致性。',
    templateKey: 'transfusion-defect',
    rules: [
      {
        ruleId: 'LX0609-041',
        name: '输血知情同意书：无输血知情同意书',
        requiredDocumentsLabel: '输血医嘱、输血申请、输血记录',
      },
      {
        ruleId: 'LX0609-043',
        name: '输血前辅助检查：输血前常规检查不完整',
        requiredDocumentsLabel: '输血申请、检验报告',
      },
      {
        ruleId: 'LX0609-044',
        name: '输血前评估：无输血前评估记录或记录不完整',
        requiredDocumentsLabel: '病程记录、输血申请',
      },
      {
        ruleId: 'LX0609-047',
        name: '输血后评价：无输血后评价',
        requiredDocumentsLabel: '输血记录、输血后病程',
      },
      {
        ruleId: 'LX0609-049',
        name: '输血医嘱：输血医嘱与收费不一致',
        requiredDocumentsLabel: '输血医嘱、费用明细、输血记录',
      },
    ],
  },
  {
    key: 'tumor_pathology',
    name: '肿瘤病理',
    description: '覆盖病理结果、取材情况和化疗记录与医嘱一致性。',
    templateKey: 'tumor-pathology-chemo-defect',
    rules: [
      {
        ruleId: 'LX0609-013',
        name: '病理检查：病理检查结果在手术记录、病程中未记录',
        requiredDocumentsLabel: '手术记录、病理报告、病程记录',
      },
      {
        ruleId: 'LX0609-019',
        name: '病理检查：取材情况未在病程记录或手术记录中记录',
        requiredDocumentsLabel: '手术记录、病理报告',
      },
      {
        ruleId: 'LX0609-026',
        name: '化疗记录：病程中化疗记录情况与医嘱不一致',
        requiredDocumentsLabel: '化疗医嘱、病程记录',
      },
    ],
  },
]
