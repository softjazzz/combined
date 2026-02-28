/**
 * 工作站 Mock 数据
 *
 * 提供拟真的住院病历数据，包含入院记录、出院记录、病程记录、手术记录等。
 * 后续对接真实数据库后替换为 API 调用。
 */

export interface MedicalRecord {
    visitId: string
    inpatNo: string
    name: string
    sex: string
    age: string
    deptName: string
    admissionDate: string
    dischargeDate: string
    status: 'pending' | 'completed'
    bedNo: string
    diagnosisMain: string
    admissionNote: string
    dischargeNote: string
    progressNote: string
    surgeryNote: string
}

export interface QCResult {
    ruleId: string
    ruleName: string
    category: string
    severity: 'error' | 'warning' | 'info'
    passed: boolean
    detail: string
    field?: string
    deduction: number
}

export interface FrontPageField {
    label: string
    value: string
    confidence: number
    source: string
}

// ==================== Mock 病历列表 ====================
export const mockRecords: MedicalRecord[] = [
    {
        visitId: 'V20250201001',
        inpatNo: 'ZY2025001234',
        name: '张三丰',
        sex: '男',
        age: '67岁',
        deptName: '心内科',
        admissionDate: '2025-02-01',
        dischargeDate: '2025-02-12',
        status: 'completed',
        bedNo: '3床',
        diagnosisMain: '急性前壁ST段抬高型心肌梗死',
        admissionNote: `<h4>入院记录</h4>
<p><b>主诉：</b>突发胸骨后压榨性疼痛6小时。</p>
<p><b>现病史：</b>患者于入院前6小时无明显诱因突发胸骨后压榨性疼痛，持续不缓解，伴大汗、恶心、呕吐一次，呕吐物为胃内容物。自服"速效救心丸"10粒无缓解。遂拨打120由急救车送入我院急诊科，心电图提示V1-V4导联ST段弓背向上抬高0.2-0.5mV，急查肌钙蛋白I 2.3ng/ml（正常＜0.04），考虑"急性前壁ST段抬高型心肌梗死"，予以口服阿司匹林300mg、替格瑞洛180mg，肝素钠5000U静脉注射，遂收入心内科监护室。</p>
<p><b>既往史：</b>高血压病史10年，最高血压180/110mmHg，长期口服硝苯地平缓释片30mg qd，血压控制尚可。2型糖尿病史5年，空腹血糖波动在7-10mmol/L，口服二甲双胍500mg tid。否认肝炎、结核病史。</p>
<p><b>个人史：</b>吸烟30年，20支/日，偶尔饮酒。</p>
<p><b>体格检查：</b>T 36.5℃，P 98次/分，R 20次/分，BP 145/90mmHg。神志清楚，精神差，表情痛苦。皮肤黏膜无黄染，浅表淋巴结未触及肿大。双肺呼吸音清，未闻及干湿性啰音。心率98次/分，律齐，各瓣膜区未闻及病理性杂音。腹软，无压痛、反跳痛。双下肢无水肿。</p>
<p><b>辅助检查：</b>心电图：窦性心律，V1-V4导联ST段弓背向上抬高0.2-0.5mV。肌钙蛋白I 2.3ng/ml↑。BNP 580pg/ml↑。</p>
<p><b>初步诊断：</b><br/>1. 急性前壁ST段抬高型心肌梗死 Killip II级<br/>2. 高血压病3级（极高危）<br/>3. 2型糖尿病</p>`,
        dischargeNote: `<h4>出院记录</h4>
<p><b>入院日期：</b>2025-02-01 &emsp; <b>出院日期：</b>2025-02-12 &emsp; <b>住院天数：</b>11天</p>
<p><b>入院诊断：</b>急性前壁ST段抬高型心肌梗死 Killip II级</p>
<p><b>出院诊断：</b><br/>1. 冠心病 急性前壁ST段抬高型心肌梗死 PCI术后 Killip II级<br/>2. 高血压病3级（极高危）<br/>3. 2型糖尿病</p>
<p><b>诊疗经过：</b>入院后急诊行冠脉造影示：前降支近段完全闭塞，予以球囊扩张后植入药物洗脱支架1枚（3.0×33mm），术后TIMI血流3级。术后给予双联抗血小板治疗（阿司匹林+替格瑞洛）、他汀调脂、ACEI降压、β受体阻滞剂控制心率等治疗，胸痛完全缓解，心电图ST段逐渐回落，复查心脏彩超LVEF 48%，患者病情稳定。</p>
<p><b>出院医嘱：</b><br/>1. 阿司匹林肠溶片 100mg qd<br/>2. 替格瑞洛 90mg bid<br/>3. 阿托伐他汀钙片 20mg qn<br/>4. 美托洛尔缓释片 47.5mg qd<br/>5. 培哚普利片 4mg qd<br/>6. 二甲双胍缓释片 500mg tid<br/>7. 1周后心内科门诊复诊</p>`,
        progressNote: `<h4>病程记录</h4>
<p><b>2025-02-01 20:30 首次病程记录</b></p>
<p>患者张三丰，男，67岁，因"突发胸骨后压榨性疼痛6小时"入院。查体：BP 145/90mmHg，HR 98bpm，双肺呼吸音清。心电图示V1-V4导联ST段抬高，肌钙蛋白I 2.3ng/ml。诊断：急性前壁ST段抬高型心肌梗死，Killip II级。已联系导管室急诊PCI。</p>
<p><b>2025-02-02 08:00 日常病程记录</b></p>
<p>患者昨晚急诊PCI术顺利，术中于前降支近段植入支架1枚，术后TIMI血流3级。今晨查房：患者胸痛缓解，生命体征平稳，BP 130/80mmHg，HR 72bpm。穿刺点无渗血渗液。继续当前治疗方案。</p>
<p><b>2025-02-05 08:00 上级医师查房记录</b></p>
<p>科主任王XX查房：患者PCI术后第4天，胸痛未再发作，心电图ST段较前回落。复查肌钙蛋白I 0.8ng/ml，较前下降。心脏彩超LVEF 48%，前壁运动减弱。同意继续目前治疗方案，注意心脏康复锻炼。</p>`,
        surgeryNote: `<h4>手术记录</h4>
<p><b>手术日期：</b>2025-02-01 21:15</p>
<p><b>手术名称：</b>经皮冠状动脉支架植入术（PCI）</p>
<p><b>术者：</b>李XX &emsp; <b>助手：</b>赵XX &emsp; <b>麻醉方式：</b>局部麻醉</p>
<p><b>手术过程：</b>常规消毒铺巾，利多卡因局部麻醉后，Seldinger法穿刺右桡动脉成功，置入6F鞘管。沿鞘管送入JL4.0指引导管至左冠状动脉口，造影示前降支近段完全闭塞。以BMW导丝通过闭塞段至远端，沿导丝送入2.5×15mm球囊至闭塞段，以10atm扩张2次，每次30秒。复查造影示前降支血流恢复，残余狭窄约40%。更换3.0×33mm药物洗脱支架释放于病变处，14atm释放。复查造影示支架膨胀良好，血管壁贴合紧密，无夹层，TIMI血流3级。术毕，拔除鞘管，桡动脉止血器加压包扎。术中出血约10ml，术程顺利。</p>`
    },
    {
        visitId: 'V20250203002',
        inpatNo: 'ZY2025001456',
        name: '李秀英',
        sex: '女',
        age: '45岁',
        deptName: '普外科',
        admissionDate: '2025-02-03',
        dischargeDate: '2025-02-08',
        status: 'completed',
        bedNo: '12床',
        diagnosisMain: '急性化脓性阑尾炎',
        admissionNote: `<h4>入院记录</h4>
<p><b>主诉：</b>转移性右下腹痛2天。</p>
<p><b>现病史：</b>患者2天前无明显诱因出现上腹部阵发性隐痛，后疼痛转移至右下腹，呈持续性钝痛，阵发性加剧，伴恶心、呕吐1次，低热。当地卫生院给予抗炎输液治疗无缓解，遂来我院急诊。腹部彩超提示：阑尾肿胀，周围渗出。</p>
<p><b>既往史：</b>否认高血压、糖尿病、心脏病史。2018年行剖宫产术。药物过敏：青霉素。</p>
<p><b>体格检查：</b>T 38.2℃，P 90次/分，R 18次/分，BP 120/75mmHg。腹部平坦，右下腹麦氏点压痛（+），反跳痛（+），肌紧张（+）。Rovsing征（+），腰大肌试验（+）。肠鸣音减弱。</p>
<p><b>辅助检查：</b>血常规：WBC 15.6×10⁹/L↑，N% 89%↑。CRP 68mg/L↑。</p>
<p><b>初步诊断：</b>急性化脓性阑尾炎</p>`,
        dischargeNote: `<h4>出院记录</h4>
<p><b>入院日期：</b>2025-02-03 &emsp; <b>出院日期：</b>2025-02-08 &emsp; <b>住院天数：</b>5天</p>
<p><b>出院诊断：</b>急性化脓性阑尾炎（术后）</p>
<p><b>诊疗经过：</b>入院后完善检查，于2025-02-04在全麻下行腹腔镜阑尾切除术，术中见阑尾充血肿胀，表面有脓苔覆盖，周围少量脓性渗出液。术后予以抗感染、补液等治疗，切口愈合良好，无感染征象。术后第4天复查血常规恢复正常，患者无不适，予以出院。</p>
<p><b>出院医嘱：</b><br/>1. 头孢克洛缓释片 0.375g bid × 5天<br/>2. 清淡饮食，避免辛辣刺激<br/>3. 术后2周门诊拆线复查</p>`,
        progressNote: `<h4>病程记录</h4>
<p><b>2025-02-04 17:00 术后首次病程</b></p>
<p>患者今日在全麻下行腹腔镜阑尾切除术，手术顺利。术中探查阑尾化脓性改变，未见穿孔。术后安返病房，生命体征平稳。予以头孢美唑抗感染，奥美拉唑抑酸保胃，补液支持治疗。</p>
<p><b>2025-02-05 08:00</b></p>
<p>术后第1天，患者已肛门排气，腹部切口敷料干燥，无渗血渗液。T 37.1℃，腹部轻压痛。可进流质饮食。</p>`,
        surgeryNote: `<h4>手术记录</h4>
<p><b>手术日期：</b>2025-02-04 14:00</p>
<p><b>手术名称：</b>腹腔镜阑尾切除术</p>
<p><b>术者：</b>王XX &emsp; <b>助手：</b>张XX &emsp; <b>麻醉方式：</b>全身麻醉</p>
<p><b>手术过程：</b>全麻满意后，取仰卧位，常规消毒铺巾。脐下缘切口置入10mm Trocar建立气腹，置入腹腔镜探查。于左下腹及耻骨上分别穿刺置入5mm Trocar。探查见阑尾明显充血肿胀，约8cm×1.5cm，表面覆盖脓苔，周围少量脓性渗出液约30ml，吸净。用超声刀依次切断阑尾系膜，0号可吸收线双重结扎阑尾根部后切断阑尾，残端电灼处理。取出阑尾标本送病理。冲洗腹腔，检查无活动性出血，拔除Trocar，缝合切口。手术顺利，出血约10ml。</p>`
    },
    {
        visitId: 'V20250210003',
        inpatNo: 'ZY2025001789',
        name: '王建国',
        sex: '男',
        age: '58岁',
        deptName: '呼吸内科',
        admissionDate: '2025-02-10',
        dischargeDate: '',
        status: 'pending',
        bedNo: '7床',
        diagnosisMain: '社区获得性肺炎（重症）',
        admissionNote: `<h4>入院记录</h4>
<p><b>主诉：</b>咳嗽、咳痰伴发热5天，气促1天。</p>
<p><b>现病史：</b>患者5天前受凉后出现咳嗽，咳黄色脓痰，量约30ml/日，伴发热，体温最高39.5℃，在当地诊所输液（具体不详）3天，症状无明显好转。1天前出现活动后气促、胸闷，静息状态SpO₂ 90%，遂来我院急诊，胸部CT示双下肺炎症，左侧少量胸腔积液，收入呼吸内科。</p>
<p><b>既往史：</b>COPD病史8年，长期吸入布地奈德/福莫特罗。吸烟40年，每日1包。</p>
<p><b>体格检查：</b>T 39.0℃，P 110次/分，R 28次/分，BP 100/65mmHg，SpO₂ 88%（未吸氧）。急性面容，口唇略发绀。双下肺可闻及湿啰音。</p>
<p><b>初步诊断：</b><br/>1. 社区获得性肺炎（重症）<br/>2. 慢性阻塞性肺疾病急性加重<br/>3. 左侧胸腔积液</p>`,
        dischargeNote: '',
        progressNote: `<h4>病程记录</h4>
<p><b>2025-02-10 15:00 首次病程记录</b></p>
<p>患者王建国，男，58岁，因"咳嗽、咳痰伴发热5天，气促1天"收入院。查体发现双下肺湿啰音，SpO₂ 88%。结合胸部CT，诊断社区获得性肺炎（重症），CURB-65评分3分。予以莫西沙星+头孢曲松经验性抗感染，面罩吸氧5L/min，补液等治疗。密切监测呼吸功能。</p>`,
        surgeryNote: ''
    },
    {
        visitId: 'V20250215004',
        inpatNo: 'ZY2025002001',
        name: '赵敏慧',
        sex: '女',
        age: '32岁',
        deptName: '产科',
        admissionDate: '2025-02-15',
        dischargeDate: '2025-02-20',
        status: 'completed',
        bedNo: '5床',
        diagnosisMain: '孕39+2周 G2P1 瘢痕子宫再次剖宫产',
        admissionNote: `<h4>入院记录</h4>
<p><b>主诉：</b>停经39+2周，要求入院待产。</p>
<p><b>现病史：</b>末次月经2024年5月10日，预产期2025年2月14日。孕期定期产检，唐筛、糖耐量试验、四维彩超均未见明显异常。2020年剖宫产1次，术后恢复好。今孕39+2周，胎动正常，无腹痛、阴道流血流液，要求择期剖宫产入院。</p>
<p><b>体格检查：</b>T 36.4℃，BP 118/72mmHg。宫高34cm，腹围101cm，胎心率140次/分，胎位LOA。骨盆外测量正常。</p>
<p><b>初步诊断：</b><br/>1. 孕39+2周 G2P1 LOA 待产<br/>2. 瘢痕子宫</p>`,
        dischargeNote: `<h4>出院记录</h4>
<p><b>出院诊断：</b><br/>1. 孕39+3周 G2P2 瘢痕子宫再次剖宫产<br/>2. 新生儿，男，3.4kg，Apgar评分10-10-10</p>
<p><b>诊疗经过：</b>入院后完善检查，于2025-02-16在腰硬联合麻醉下行子宫下段剖宫产术，顺利娩出一活男婴，体重3400g，Apgar评分10-10-10。术中发现子宫下段原瘢痕未变薄，子宫收缩好。术后予以缩宫素促进宫缩、头孢唑林预防感染、补液等。产妇和婴儿恢复良好。</p>`,
        progressNote: `<h4>病程记录</h4>
<p><b>2025-02-16 11:30 术后病程</b></p>
<p>患者今日在腰硬联合麻醉下行再次剖宫产术，手术顺利。术后血压稳定，宫底脐下两指，质硬，阴道流血不多。新生儿一般情况好，已母乳喂养。</p>`,
        surgeryNote: `<h4>手术记录</h4>
<p><b>手术日期：</b>2025-02-16 09:00</p>
<p><b>手术名称：</b>子宫下段剖宫产术</p>
<p><b>备注：</b>瘢痕子宫再次手术。术中情况见术后病程记录。</p>`
    },
    {
        visitId: 'V20250218005',
        inpatNo: 'ZY2025002234',
        name: '陈志强',
        sex: '男',
        age: '72岁',
        deptName: '骨科',
        admissionDate: '2025-02-18',
        dischargeDate: '',
        status: 'pending',
        bedNo: '21床',
        diagnosisMain: '左股骨颈骨折',
        admissionNote: `<h4>入院记录</h4>
<p><b>主诉：</b>摔倒致左髋部疼痛、活动受限2小时。</p>
<p><b>现病史：</b>患者2小时前在家中行走时不慎滑倒，左髋部着地，即感左髋部剧烈疼痛，不能站立行走。家属送来我院急诊，X线示左股骨颈骨折（Garden III型），收入骨科。</p>
<p><b>既往史：</b>高血压病史15年，口服氨氯地平5mg qd。骨质疏松症。否认糖尿病。</p>
<p><b>体格检查：</b>左下肢短缩约2cm，外旋畸形约45°。左腹股沟区压痛明显，叩击痛（+）。左髋关节活动受限。</p>
<p><b>初步诊断：</b><br/>1. 左股骨颈骨折（Garden III型）<br/>2. 骨质疏松症<br/>3. 高血压病</p>`,
        dischargeNote: '',
        progressNote: `<h4>病程记录</h4>
<p><b>2025-02-18 术前讨论</b></p>
<p>老年患者，左股骨颈骨折Garden III型，考虑骨折移位明显、患者年龄较大、骨质疏松，行人工股骨头置换术为宜。拟明日在腰硬联合麻醉下行左侧人工股骨头置换术。术前评估心肺功能基本正常，ASA II级。</p>`,
        surgeryNote: ''
    },
]

// ==================== Mock 质控结果 ====================
export function generateMockQCResults(record: MedicalRecord): QCResult[] {
    const results: QCResult[] = []

    // 通用形式质控
    results.push({
        ruleId: 'F001',
        ruleName: '入院记录 24 小时时限',
        category: '时限要求',
        severity: 'error',
        passed: true,
        detail: '入院记录在 24 小时内完成，符合要求',
        deduction: 0,
    })

    results.push({
        ruleId: 'F002',
        ruleName: '主诉字数限制',
        category: '书写规范',
        severity: record.admissionNote.includes('主诉') ? 'info' : 'error',
        passed: true,
        detail: '主诉用语简洁，符合 ≤20 字要求',
        deduction: 0,
    })

    results.push({
        ruleId: 'F003',
        ruleName: '出院记录完整性',
        category: '完整性检查',
        severity: record.dischargeNote ? 'info' : 'error',
        passed: !!record.dischargeNote,
        detail: record.dischargeNote ? '出院记录已填写完整' : '缺少出院记录',
        field: 'dischargeNote',
        deduction: record.dischargeNote ? 0 : 5,
    })

    results.push({
        ruleId: 'F004',
        ruleName: '首次病程记录完整性',
        category: '完整性检查',
        severity: 'info',
        passed: true,
        detail: '首次病程记录包含病例特点、初步诊断、诊疗计划',
        deduction: 0,
    })

    results.push({
        ruleId: 'F005',
        ruleName: '手术记录 24 小时时限',
        category: '时限要求',
        severity: record.surgeryNote ? 'info' : 'warning',
        passed: true,
        detail: record.surgeryNote ? '手术记录在 24 小时内完成' : '非手术病历，不适用',
        deduction: 0,
    })

    // 根据病历状态添加特定质控
    if (record.status === 'pending') {
        results.push({
            ruleId: 'F006',
            ruleName: '出院诊断与入院诊断一致性',
            category: '逻辑校验',
            severity: 'warning',
            passed: false,
            detail: '患者尚未出院，出院诊断待补充',
            field: 'dischargeNote',
            deduction: 0,
        })
    }

    if (!record.surgeryNote && record.deptName === '普外科') {
        results.push({
            ruleId: 'F007',
            ruleName: '手术科室手术记录检查',
            category: '完整性检查',
            severity: 'error',
            passed: false,
            detail: '手术科室病历缺少手术记录',
            field: 'surgeryNote',
            deduction: 5,
        })
    }

    results.push({
        ruleId: 'F008',
        ruleName: '知情同意书签署',
        category: '病案完整性',
        severity: 'warning',
        passed: true,
        detail: '知情同意书已签署（模拟检查）',
        deduction: 0,
    })

    return results
}

// ==================== Mock 首页数据 ====================
export function generateMockFrontPage(record: MedicalRecord): FrontPageField[] {
    return [
        { label: '医疗机构名称', value: '泸县人民医院', confidence: 1.0, source: '系统默认' },
        { label: '患者姓名', value: record.name, confidence: 1.0, source: '入院记录' },
        { label: '性别', value: record.sex, confidence: 1.0, source: '入院记录' },
        { label: '年龄', value: record.age, confidence: 0.98, source: '入院记录' },
        { label: '住院号', value: record.inpatNo, confidence: 1.0, source: '系统' },
        { label: '入院日期', value: record.admissionDate, confidence: 0.99, source: '入院记录' },
        { label: '出院日期', value: record.dischargeDate || '–', confidence: record.dischargeDate ? 0.99 : 0, source: '出院记录' },
        { label: '住院天数', value: record.dischargeDate ? `${Math.round((new Date(record.dischargeDate).getTime() - new Date(record.admissionDate).getTime()) / 86400000)}天` : '–', confidence: 0.99, source: '计算' },
        { label: '入院科室', value: record.deptName, confidence: 1.0, source: '入院记录' },
        { label: '床号', value: record.bedNo, confidence: 1.0, source: '系统' },
        { label: '主要诊断', value: record.diagnosisMain, confidence: 0.92, source: 'AI 提取' },
        { label: '主要手术/操作', value: record.surgeryNote ? '详见手术记录' : '无', confidence: 0.88, source: 'AI 提取' },
    ]
}
