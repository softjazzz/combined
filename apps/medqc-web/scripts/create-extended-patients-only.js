"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createExtendedPatientsOnly = createExtendedPatientsOnly;
const supabase_js_1 = require("@supabase/supabase-js");
const supabaseUrl = 'https://afsbjvihjfsngobccnjx.supabase.co';
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFmc2JqdmloamZzbmdvYmNjbmp4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIwNDE4NzQsImV4cCI6MjA2NzYxNzg3NH0.wA1Ho-pJrvPfF8k5npURDV8lL14nYdsImr8xJ5_Xvqg';
const supabase = (0, supabase_js_1.createClient)(supabaseUrl, supabaseAnonKey);
// 扩展的患者信息（10个患者）
const extendedPatients = [
    {
        name: '张明华',
        age: 45,
        gender: 'M',
        department: '心内科',
        chief_complaint: '胸痛伴气短3小时',
        present_illness: '患者于3小时前无明显诱因出现胸骨后疼痛，呈压榨性，向左肩背部放射，伴大汗淋漓、恶心呕吐、气短，无发热、咳嗽。疼痛持续不缓解，遂急诊就医。患者既往有高血压病史10年，平时血压控制尚可，有吸烟史20年，每日1包。否认糖尿病、冠心病病史。',
        past_history: '既往有高血压病史10年，长期服用氨氯地平5mg每日一次，血压控制在140/90mmHg左右。有吸烟史20年，每日约20支。否认糖尿病、冠心病、脑血管病史。否认手术外伤史。否认药物过敏史。',
        physical_exam: '一般情况：神志清楚，精神萎靡，急性病容，体温36.8℃，脉搏102次/分，呼吸22次/分，血压150/95mmHg。皮肤巩膜无黄染，浅表淋巴结未触及肿大。心脏检查：心界向左扩大，心率102次/分，律齐，各瓣膜听诊区未闻及病理性杂音。双肺呼吸音清，未闻及干湿性啰音。腹部平软，无压痛反跳痛，肝脾未触及。双下肢无水肿。',
        auxiliary_exam: '心电图：V1-V6导联ST段抬高，T波倒置，提示急性前壁心肌梗死。胸片：心影增大，肺野清晰。血常规：WBC 12.5×10^9/L，RBC 4.2×10^12/L，Hb 135g/L，PLT 280×10^9/L。生化：CK-MB 85U/L（正常<25），cTnI 8.5ng/ml（正常<0.04），总胆固醇6.8mmol/L，甘油三酯2.1mmol/L，LDL-C 4.2mmol/L。',
        diagnosis: '1.急性ST段抬高型心肌梗死（前壁）\n2.高血压病3级（极高危）\n3.高脂血症',
        treatment: '1.绝对卧床休息，心电监护\n2.急诊PCI术，植入药物洗脱支架\n3.双联抗血小板：阿司匹林100mg qd，氯吡格雷75mg qd\n4.抗凝：低分子肝素钠4000IU q12h皮下注射\n5.他汀类调脂：阿托伐他汀20mg qn\n6.ACEI类：依那普利5mg bid\n7.β受体阻滞剂：美托洛尔25mg bid\n8.营养心肌：辅酶Q10 10mg tid\n9.低盐低脂饮食，戒烟戒酒'
    },
    {
        name: '李秀英',
        age: 32,
        gender: 'F',
        department: '呼吸内科',
        chief_complaint: '发热、咳嗽、咳痰5天',
        present_illness: '患者5天前受凉后出现发热，体温最高达39.2℃，伴寒战，同时出现咳嗽、咳痰，痰液呈黄色脓性，量较多，伴胸痛，深呼吸时加重。无咯血、盗汗。曾自服感冒药物，症状无明显缓解。患者既往体健，否认慢性疾病史。',
        past_history: '既往体健，否认高血压、糖尿病、心脏病史。否认手术外伤史。否认药物过敏史。月经史：14岁初潮，周期规律，末次月经2周前。已婚，育有一子，顺产。',
        physical_exam: '一般情况：神志清楚，精神可，急性病容，体温38.5℃，脉搏96次/分，呼吸24次/分，血压110/70mmHg。皮肤巩膜无黄染，浅表淋巴结未触及肿大。心脏检查：心界不大，心率96次/分，律齐，各瓣膜听诊区未闻及病理性杂音。肺部检查：右下肺叩诊呈浊音，听诊可闻及湿性啰音和支气管呼吸音。腹部平软，无压痛反跳痛，肝脾未触及。',
        auxiliary_exam: '胸部CT：右下肺大片状高密度影，边界模糊，支气管充气征阳性，少量胸腔积液。血常规：WBC 15.2×10^9/L，N 85%，RBC 4.0×10^12/L，Hb 125g/L。CRP 85mg/L，PCT 2.1ng/ml。痰培养：肺炎链球菌，对青霉素敏感。血气分析：pH 7.42，PO2 75mmHg，PCO2 35mmHg。',
        diagnosis: '1.社区获得性肺炎（右下肺）\n2.少量胸腔积液',
        treatment: '1.一般治疗：卧床休息，多饮水，高蛋白饮食\n2.抗感染：头孢曲松2g ivgtt qd\n3.化痰止咳：氨溴索30mg tid\n4.退热：对乙酰氨基酚0.5g po prn（体温>38.5℃）\n5.营养支持：复合维生素B片\n6.密切观察病情变化，监测体温、呼吸、血氧饱和度'
    },
    {
        name: '王建国',
        age: 58,
        gender: 'M',
        department: '消化内科',
        chief_complaint: '上腹痛伴恶心呕吐2天',
        present_illness: '患者2天前进食油腻食物后出现上腹部疼痛，呈持续性胀痛，向腰背部放射，伴恶心呕吐，呕吐物为胃内容物，无咯血。疼痛在进食后加重，平卧时加重，前倾坐位时稍缓解。患者有饮酒史30年，每日白酒约200ml。既往有慢性胃炎病史。',
        past_history: '既往有慢性胃炎病史5年，间断服用奥美拉唑。有长期饮酒史30年，每日白酒约200ml。否认高血压、糖尿病史。否认手术外伤史。否认药物过敏史。',
        physical_exam: '一般情况：神志清楚，精神萎靡，痛苦面容，体温37.8℃，脉搏88次/分，呼吸20次/分，血压125/80mmHg。皮肤巩膜轻度黄染，浅表淋巴结未触及肿大。心肺检查未见异常。腹部检查：上腹部压痛明显，无反跳痛，Murphy征阴性，肝脾未触及，肠鸣音减弱。',
        auxiliary_exam: '腹部CT：胰腺头部肿胀，胰周渗出，胰管扩张，胆总管轻度扩张。血常规：WBC 13.8×10^9/L，N 82%。生化：血淀粉酶580U/L（正常<100），脂肪酶1200U/L（正常<300），总胆红素45μmol/L，直接胆红素32μmol/L，ALT 85U/L，AST 120U/L。',
        diagnosis: '1.急性胰腺炎\n2.慢性胃炎\n3.长期饮酒史',
        treatment: '1.禁食禁水，胃肠减压\n2.补液维持水电解质平衡\n3.抑制胰酶分泌：奥曲肽0.1mg q8h皮下注射\n4.抑制胃酸：奥美拉唑40mg ivgtt bid\n5.抗感染：头孢哌酮舒巴坦3g ivgtt q12h\n6.营养支持：肠外营养\n7.镇痛：哌替啶50mg im prn\n8.密切观察病情，监测生命体征'
    },
    {
        name: '赵丽华',
        age: 28,
        gender: 'F',
        department: '妇产科',
        chief_complaint: '停经45天，阴道流血3天',
        present_illness: '患者末次月经45天前，平时月经规律，周期28-30天。3天前无明显诱因出现阴道流血，量少于月经量，色暗红，无血块，伴轻微下腹痛。无恶心呕吐，无发热。患者已婚，有正常性生活，未避孕。既往月经规律，无痛经史。',
        past_history: '既往体健，否认高血压、糖尿病、心脏病史。月经史：14岁初潮，周期28-30天，经期5-7天，量中等。婚育史：已婚2年，未孕，有正常性生活，未避孕。否认手术外伤史，否认药物过敏史。',
        physical_exam: '一般情况：神志清楚，精神可，体温36.6℃，脉搏76次/分，呼吸18次/分，血压110/70mmHg。皮肤巩膜无黄染，浅表淋巴结未触及肿大。心肺检查未见异常。妇科检查：外阴发育正常，阴道内少量暗红色血液，宫颈光滑，子宫前位，增大如孕6周大小，质软，双侧附件未触及异常。',
        auxiliary_exam: '血HCG：15000mIU/ml（正常非孕<5）。阴道超声：子宫增大，宫腔内见妊娠囊，大小约2.0×1.5cm，囊内见胎芽及原始心管搏动，胎芽长径约0.8cm，相当于孕6-7周。双侧卵巢大小正常，盆腔无积液。血常规：WBC 6.8×10^9/L，RBC 3.8×10^12/L，Hb 115g/L。',
        diagnosis: '1.早期妊娠\n2.先兆流产',
        treatment: '1.卧床休息，避免剧烈活动\n2.保胎治疗：黄体酮胶囊200mg po bid\n3.维生素E 100mg po tid\n4.叶酸片5mg po qd\n5.禁止性生活\n6.定期复查血HCG和超声\n7.如出血增多或腹痛加重及时就诊\n8.心理支持和健康宣教'
    },
    {
        name: '孙志强',
        age: 65,
        gender: 'M',
        department: '神经内科',
        chief_complaint: '突发左侧肢体无力2小时',
        present_illness: '患者2小时前在家中看电视时突然出现左侧肢体无力，伴言语不清，无意识障碍，无头痛、呕吐。家属发现后立即送医。患者既往有高血压病史15年，糖尿病史10年，血压、血糖控制不佳。有吸烟史40年。',
        past_history: '既往有高血压病史15年，长期服用氨氯地平，血压控制不佳，常在160/100mmHg左右。糖尿病史10年，服用二甲双胍，血糖控制不佳，空腹血糖常在8-10mmol/L。有吸烟史40年，每日1-2包。否认心脏病史。',
        physical_exam: '一般情况：神志清楚，精神萎靡，体温36.5℃，脉搏82次/分，呼吸18次/分，血压180/110mmHg。神经系统检查：言语不清，左侧鼻唇沟变浅，左上肢肌力3级，左下肢肌力4级，左侧巴氏征阳性。心肺腹检查未见明显异常。',
        auxiliary_exam: '头颅CT：右侧基底节区低密度影，考虑急性脑梗死。颈动脉超声：双侧颈动脉粥样硬化，右侧颈内动脉中度狭窄。血常规正常。生化：空腹血糖12.5mmol/L，总胆固醇6.2mmol/L，甘油三酯3.8mmol/L，LDL-C 4.1mmol/L。凝血功能正常。',
        diagnosis: '1.急性脑梗死（右侧基底节区）\n2.高血压病3级（极高危）\n3.2型糖尿病\n4.高脂血症\n5.颈动脉粥样硬化',
        treatment: '1.急性期治疗：阿司匹林300mg po qd\n2.改善脑循环：依达拉奉30mg ivgtt bid\n3.降压治疗：氨氯地平10mg po qd\n4.降糖治疗：胰岛素皮下注射\n5.调脂治疗：阿托伐他汀20mg po qn\n6.康复治疗：早期康复训练\n7.预防并发症：翻身拍背，预防压疮\n8.营养支持：鼻饲流质饮食'
    },
    {
        name: '陈美玲',
        age: 8,
        gender: 'F',
        department: '儿科',
        chief_complaint: '发热、咽痛3天',
        present_illness: '患儿3天前开始发热，体温最高达39.5℃，伴咽痛、头痛，食欲减退，精神萎靡。无咳嗽、流涕，无腹痛、腹泻。家长给予物理降温，体温可暂时下降，但很快又升高。患儿既往体健，按时接种疫苗。',
        past_history: '既往体健，生长发育正常，按时接种疫苗。否认先天性疾病史，否认药物过敏史。出生史：足月顺产，出生体重3.2kg，无窒息史。喂养史：母乳喂养至1岁，添加辅食及时。',
        physical_exam: '一般情况：神志清楚，精神萎靡，急性病容，体温39.2℃，脉搏120次/分，呼吸28次/分，血压90/60mmHg。皮肤可见散在红色皮疹，压之褪色。咽部充血明显，扁桃体II度肿大，表面有脓性分泌物。颈部淋巴结肿大，质软，有压痛。心肺腹检查未见异常。',
        auxiliary_exam: '血常规：WBC 18.5×10^9/L，N 85%，RBC 4.2×10^12/L，Hb 120g/L。CRP 120mg/L。咽拭子培养：A组β溶血性链球菌。尿常规正常。心电图正常。',
        diagnosis: '1.急性化脓性扁桃体炎\n2.猩红热',
        treatment: '1.隔离治疗，预防传播\n2.抗感染：青霉素V 25万U po qid\n3.退热：布洛芬混悬液5ml po prn（体温>38.5℃）\n4.局部治疗：复方硼砂溶液漱口\n5.多饮水，清淡饮食\n6.密切观察病情，预防并发症\n7.家属健康宣教'
    },
    {
        name: '刘建华',
        age: 42,
        gender: 'M',
        department: '骨科',
        chief_complaint: '右小腿疼痛、肿胀1天',
        present_illness: '患者1天前从2米高处跌落，右小腿着地，当时即感剧烈疼痛，不能站立行走。伴右小腿肿胀、畸形，无开放性伤口，无意识障碍。急诊X线检查提示右胫腓骨骨折。患者既往体健，无骨折史。',
        past_history: '既往体健，否认高血压、糖尿病、心脏病史。否认骨折、手术史。否认药物过敏史。职业：建筑工人，经常高空作业。',
        physical_exam: '一般情况：神志清楚，精神可，因疼痛表情痛苦，体温36.8℃，脉搏88次/分，呼吸20次/分，血压130/85mmHg。专科检查：右小腿中下段肿胀明显，皮肤完整，局部压痛明显，异常活动，骨擦音阳性。足背动脉搏动可触及，足趾活动正常，感觉正常。',
        auxiliary_exam: 'X线检查：右胫骨中下段横行骨折，骨折线清晰，有轻度移位。右腓骨中段斜行骨折。血常规、凝血功能、生化检查均正常。心电图正常。胸片未见异常。',
        diagnosis: '1.右胫腓骨骨折\n2.外伤史',
        treatment: '1.急诊手术：右胫腓骨骨折切开复位内固定术\n2.术后制动：石膏外固定\n3.抗感染：头孢唑林1g ivgtt q8h\n4.镇痛：双氯芬酸钠50mg po bid\n5.消肿治疗：甘露醇250ml ivgtt bid\n6.预防血栓：低分子肝素钠4000IU qd皮下注射\n7.功能锻炼：早期足趾活动，后期关节功能锻炼\n8.定期复查X线，观察骨折愈合情况'
    },
    {
        name: '杨慧敏',
        age: 55,
        gender: 'F',
        department: '内分泌科',
        chief_complaint: '多饮、多尿、体重下降2个月',
        present_illness: '患者2个月前开始出现多饮、多尿，每日饮水量约3000ml，夜尿4-5次，同时体重下降约8kg。伴乏力、视物模糊，无发热、腹痛。既往体健，有糖尿病家族史（母亲患糖尿病）。',
        past_history: '既往体健，否认高血压、心脏病史。家族史：母亲患2型糖尿病。否认手术外伤史，否认药物过敏史。月经史：已绝经3年。',
        physical_exam: '一般情况：神志清楚，精神萎靡，消瘦，体温36.5℃，脉搏92次/分，呼吸18次/分，血压140/90mmHg，体重55kg（较前减轻8kg）。皮肤干燥，弹性差。心肺腹检查未见明显异常。双足皮肤完整，足背动脉搏动可触及。',
        auxiliary_exam: '空腹血糖：16.8mmol/L，餐后2小时血糖：22.5mmol/L。糖化血红蛋白：11.2%。尿常规：尿糖+++，尿酮体+。肾功能：肌酐85μmol/L，尿素氮6.8mmol/L。眼底检查：轻度糖尿病视网膜病变。',
        diagnosis: '1.2型糖尿病\n2.糖尿病酮症\n3.糖尿病视网膜病变',
        treatment: '1.糖尿病教育，制定个体化治疗方案\n2.胰岛素治疗：门冬胰岛素三餐前皮下注射\n3.补液纠正脱水：生理盐水静脉滴注\n4.纠正酮症：小剂量胰岛素持续静脉滴注\n5.饮食控制：糖尿病饮食\n6.监测血糖：每日4次血糖监测\n7.定期复查：糖化血红蛋白、肾功能、眼底\n8.预防并发症：足部护理，血压管理'
    },
    {
        name: '马志远',
        age: 38,
        gender: 'M',
        department: '外科',
        chief_complaint: '右上腹痛6小时',
        present_illness: '患者6小时前进食油腻食物后出现右上腹痛，呈阵发性绞痛，向右肩背部放射，伴恶心呕吐，呕吐物为胃内容物。疼痛剧烈，辗转不安，无发热、黄疸。既往有类似发作史，但程度较轻。',
        past_history: '既往有胆囊结石病史2年，曾有类似腹痛发作，保守治疗后缓解。否认高血压、糖尿病史。否认手术史。否认药物过敏史。',
        physical_exam: '一般情况：神志清楚，因疼痛表情痛苦，体温37.5℃，脉搏96次/分，呼吸22次/分，血压125/80mmHg。腹部检查：右上腹压痛明显，Murphy征阳性，无反跳痛，肝脾未触及，肠鸣音正常。',
        auxiliary_exam: '腹部B超：胆囊壁增厚，囊内见多发强回声团伴声影，胆囊颈部结石嵌顿，胆总管不扩张。血常规：WBC 12.8×10^9/L，N 80%。生化：总胆红素28μmol/L，直接胆红素18μmol/L，ALT 65U/L，AST 58U/L。',
        diagnosis: '1.急性胆囊炎\n2.胆囊结石\n3.胆囊颈部结石嵌顿',
        treatment: '1.禁食禁水，胃肠减压\n2.抗感染：头孢哌酮舒巴坦3g ivgtt q12h\n3.解痉镇痛：山莨菪碱10mg im q8h\n4.补液维持水电解质平衡\n5.择期手术：腹腔镜胆囊切除术\n6.术前准备：完善术前检查\n7.密切观察病情，如症状加重考虑急诊手术'
    },
    {
        name: '周雅琴',
        age: 72,
        gender: 'F',
        department: '肾内科',
        chief_complaint: '双下肢水肿、尿少1周',
        present_illness: '患者1周前开始出现双下肢水肿，从足踝部开始，逐渐向上发展至小腿，伴尿量减少，每日约500ml，尿色深黄。无发热、胸闷气短，无腰痛。既往有高血压病史20年，糖尿病史15年。',
        past_history: '既往有高血压病史20年，长期服用降压药，血压控制一般。糖尿病史15年，长期服用降糖药，血糖控制不佳。否认心脏病史。否认肾脏疾病史。',
        physical_exam: '一般情况：神志清楚，精神萎靡，体温36.8℃，脉搏88次/分，呼吸20次/分，血压160/95mmHg。双下肢凹陷性水肿，达膝关节以下。心肺检查未见明显异常。腹部无异常。',
        auxiliary_exam: '尿常规：蛋白+++，红细胞10-15/HP，白细胞5-8/HP，管型++。24小时尿蛋白定量：3.2g。肾功能：肌酐280μmol/L，尿素氮18.5mmol/L，内生肌酐清除率35ml/min。血常规：轻度贫血。肾脏B超：双肾大小正常，实质回声增强。',
        diagnosis: '1.慢性肾脏病4期\n2.糖尿病肾病\n3.高血压肾病\n4.肾性水肿',
        treatment: '1.低盐低蛋白饮食，限制水钠摄入\n2.利尿消肿：呋塞米20mg po bid\n3.降压治疗：ACEI类药物，控制血压<130/80mmHg\n4.降糖治疗：调整降糖方案，控制血糖\n5.纠正贫血：促红细胞生成素\n6.保护肾功能：避免肾毒性药物\n7.定期复查肾功能、电解质\n8.肾脏替代治疗准备：建立血管通路'
    }
];
// 生成详细病历内容（约1000字）
function generateDetailedMedicalRecord(patient) {
    return `
【患者基本信息】
姓名：${patient.name}
年龄：${patient.age}岁
性别：${patient.gender === 'M' ? '男' : '女'}
科室：${patient.department}
入院时间：${new Date().toLocaleDateString()}

【主诉】
${patient.chief_complaint}

【现病史】
${patient.present_illness}

【既往史】
${patient.past_history}

【体格检查】
${patient.physical_exam}

【辅助检查】
${patient.auxiliary_exam}

【临床诊断】
${patient.diagnosis}

【治疗方案】
${patient.treatment}

【医嘱】
1. 专科护理，密切观察病情变化
2. 按医嘱执行各项治疗措施
3. 定期复查相关检验检查
4. 如有异常及时报告医师
5. 健康宣教，指导患者配合治疗

【医师签名】主治医师：王医生
【记录时间】${new Date().toLocaleString()}
`.trim();
}
async function createExtendedPatientsOnly() {
    console.log('🚀 开始创建扩展患者数据（仅病案记录）...\n');
    try {
        // 1. 清空现有数据
        console.log('1. 清空现有数据...');
        await supabase.from('medical_records').delete().neq('id', '00000000-0000-0000-0000-000000000000');
        console.log('✅ 现有数据已清空\n');
        // 2. 创建扩展的病案记录
        console.log('2. 创建扩展的病案记录...');
        const recordsToCreate = [];
        // 使用所有详细患者数据
        for (let i = 0; i < extendedPatients.length; i++) {
            const patient = extendedPatients[i];
            const content = generateDetailedMedicalRecord(patient);
            const createdAt = new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString();
            recordsToCreate.push({
                patient_name: patient.name,
                patient_age: patient.age,
                patient_gender: patient.gender,
                department: patient.department,
                admission_date: createdAt.split('T')[0],
                record_type: 'inpatient',
                content,
                status: 'completed',
                created_at: createdAt,
                updated_at: createdAt
            });
        }
        console.log(`准备创建 ${recordsToCreate.length} 条详细病案记录...`);
        const { data: records, error: recordsError } = await supabase
            .from('medical_records')
            .insert(recordsToCreate)
            .select();
        if (recordsError) {
            throw recordsError;
        }
        console.log(`✅ 已创建 ${records.length} 条病案记录\n`);
        // 3. 统计信息
        console.log('📊 数据统计:');
        console.log(`- 总病案数: ${records.length}`);
        const departmentStats = {};
        records.forEach(record => {
            departmentStats[record.department] = (departmentStats[record.department] || 0) + 1;
        });
        console.log('\n📊 科室分布:');
        Object.entries(departmentStats).forEach(([dept, count]) => {
            console.log(`- ${dept}: ${count} 条`);
        });
        console.log('\n🎉 扩展患者数据创建完成！');
        console.log('现在可以在系统中查看详细的病案记录了。');
        console.log('注意：质控结果需要通过系统的质控分析功能生成。');
    }
    catch (error) {
        console.error('❌ 创建扩展患者数据失败:', error);
        throw error;
    }
}
// 运行脚本
createExtendedPatientsOnly().catch(console.error);
