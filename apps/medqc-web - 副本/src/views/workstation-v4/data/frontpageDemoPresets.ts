import type { FrontpageReportScene } from '@/api/frontpage'

export interface FrontpageDemoPreset {
  id: string
  title: string
  description: string
  visit_id: string
  patient_id?: string
  mr_no?: string
  tags: string[]
  scene: FrontpageReportScene
  synthetic_settlement_text: string
}

const syntheticNotice =
  '本段为 demo/synthetic 演示补充信息，仅用于本次生成草稿抽取，不写入正式首页表、结算表或业务库。'

export const frontpageDemoPresets: FrontpageDemoPreset[] = [
  {
    id: 'demo-internal-no-surgery',
    title: '示例一：内科出院病例',
    description: '用于演示普通住院病历生成病案首页和结算清单草稿，无手术场景。',
    visit_id: '2212117',
    patient_id: '0000066881',
    mr_no: '211576',
    tags: ['内科', '无手术', '费用演示'],
    scene: 'combined',
    synthetic_settlement_text: `【演示用医保结算补充信息】
${syntheticNotice}
医保类型：城镇职工基本医疗保险
总费用：18436.25 元
自付费用：1260.50 元
西药费：3260.00 元
检查费：2180.00 元
检验费：1650.00 元
护理费：780.00 元
其他费用：360.25 元`,
  },
  {
    id: 'demo-surgery-anesthesia',
    title: '示例二：外科手术病例',
    description: '用于演示手术、麻醉、术者信息和费用分类进入联合草稿。',
    visit_id: '1870471',
    patient_id: '0000534433',
    mr_no: '362948',
    tags: ['外科', '手术', '麻醉'],
    scene: 'combined',
    synthetic_settlement_text: `【演示用医保结算补充信息】
${syntheticNotice}
医保类型：城乡居民基本医疗保险
总费用：52680.80 元
自付费用：6840.35 元
手术治疗费：9800.00 元
麻醉费：2650.00 元
手术费：7200.00 元
检查费：3680.00 元
检验费：2240.00 元
西药费：8560.00 元
一次性医用材料费：11800.00 元`,
  },
  {
    id: 'demo-icu-ventilation',
    title: '示例三：ICU 呼吸机病例',
    description: '用于演示 ICU 进出、呼吸机使用时间和重症费用草稿。',
    visit_id: '1411295',
    patient_id: '0000150703',
    mr_no: '248892',
    tags: ['ICU', '呼吸机', '重症'],
    scene: 'combined',
    synthetic_settlement_text: `【演示用医保结算补充信息】
${syntheticNotice}
医保类型：城镇职工基本医疗保险
总费用：78620.40 元
自付费用：9420.60 元
一般医疗服务费：4200.00 元
护理费：3600.00 元
西药费：18600.00 元
检查费：4980.00 元
检验费：5120.00 元
治疗费：12600.00 元
其他费用：1480.40 元`,
  },
  {
    id: 'demo-tcm-diagnosis',
    title: '示例四：中医诊断病例',
    description: '用于演示门急诊中医诊断、中医治疗费用和联合 coverage。',
    visit_id: '2073320',
    patient_id: '0000237455',
    tags: ['中医诊断', '本机候选', '费用演示'],
    scene: 'combined',
    synthetic_settlement_text: `【演示用医保结算补充信息】
${syntheticNotice}
医保类型：城镇职工基本医疗保险
总费用：23680.00 元
自付费用：1680.00 元
中医治疗费：4200.00 元
中成药费：1860.00 元
中草药费：1260.00 元
检查费：1380.00 元
检验费：920.00 元
护理费：660.00 元`,
  },
]
