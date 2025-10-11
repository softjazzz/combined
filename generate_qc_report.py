#!/usr/bin/env python3
"""
生成首次病程记录的质控报告
"""
import sys
sys.path.insert(0, '/home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/backend')

from fastapi.testclient import TestClient
from app.main import app
import json

# 首次病程记录内容
content = """首次病程记录

记录时间：2025年10月11日 15:00

一、患者基本信息
姓名：李明
性别：男
年龄：58岁
科室：心内科
住院号：2025001234
床号：15床
入院时间：2025年10月11日 09:30

二、主诉
反复胸闷、胸痛3天，加重伴气促1天。

三、现病史
患者于3天前无明显诱因出现胸闷、胸痛，呈压榨性疼痛，位于胸骨后,持续时间约5-10分钟，休息后可缓解。1天前上述症状加重，伴有气促、出汗，活动后明显，休息时亦有发作。患者自服"速效救心丸"后症状无明显缓解，遂来我院急诊就诊。

急诊查心电图示：V1-V4导联ST段压低0.1-0.2mV，T波倒置。
急诊查心肌酶谱：肌钙蛋白I 0.8 ng/mL（正常值<0.04 ng/mL），肌酸激酶同工酶（CK-MB）45 U/L（正常值<25 U/L）。

急诊诊断为"急性冠脉综合征"，予以阿司匹林、氯吡格雷抗血小板聚集，低分子肝素抗凝，硝酸甘油扩冠等治疗后，症状稍缓解，为进一步诊治收入我科。

发病以来，患者精神欠佳，食欲减退，睡眠欠佳，大小便正常，体重无明显变化。

四、既往史
1. 高血压病史10年，最高血压180/110 mmHg，平时口服"硝苯地平缓释片"控制，血压控制尚可。
2. 2型糖尿病病史5年，口服"二甲双胍"控制，血糖控制一般。
3. 吸烟史30年，每天约20支，已戒烟2年。
4. 否认肝炎、结核等传染病史。
5. 否认手术、外伤史。
6. 否认药物、食物过敏史。
7. 否认输血史。

五、个人史及家族史
1. 个人史：生于本地，长期居住本地，无疫区居住史，无毒物接触史。
2. 家族史：父亲有高血压病史，母亲有糖尿病史，否认家族遗传性疾病史。

六、体格检查
T: 36.8℃  P: 88次/分  R: 20次/分  BP: 145/90 mmHg

一般情况：神志清楚，精神欠佳，体型偏胖，营养中等，自主体位，查体合作。

皮肤黏膜：皮肤无黄染、出血点，浅表淋巴结未触及肿大。

头颈部：头颅无畸形，双侧瞳孔等大等圆，对光反射灵敏，巩膜无黄染，结膜无充血，口唇无发绀，咽部无充血，扁桃体无肿大，颈软，气管居中，甲状腺无肿大，颈静脉无怒张。

胸部：
- 肺部：胸廓对称，呼吸运动正常，双肺叩诊清音，双肺呼吸音清晰，未闻及干湿性啰音。
- 心脏：心前区无隆起，心尖搏动位于左侧第5肋间锁骨中线内0.5cm，心界不大，心率88次/分，律齐，各瓣膜听诊区未闻及病理性杂音。

腹部：腹部平软，无压痛、反跳痛，肝脾肋下未触及，Murphy征阴性，移动性浊音阴性，肠鸣音正常。

脊柱四肢：脊柱无畸形，四肢活动正常，双下肢无水肿。

神经系统：生理反射存在，病理反射未引出。

七、辅助检查
1. 心电图（2025-10-11 急诊）：V1-V4导联ST段压低0.1-0.2mV，T波倒置。
2. 心肌酶谱（2025-10-11 急诊）：
   - 肌钙蛋白I：0.8 ng/mL（正常值<0.04 ng/mL）↑
   - 肌酸激酶同工酶（CK-MB）：45 U/L（正常值<25 U/L）↑
3. 血常规（2025-10-11）：WBC 8.5×10^9/L，RBC 4.8×10^12/L，Hb 145 g/L，PLT 220×10^9/L。
4. 生化全套（2025-10-11）：
   - 空腹血糖：8.2 mmol/L（正常值3.9-6.1 mmol/L）↑
   - 总胆固醇：6.5 mmol/L（正常值<5.2 mmol/L）↑
   - 低密度脂蛋白：4.2 mmol/L（正常值<3.4 mmol/L）↑
   - 肝肾功能正常。

八、初步诊断
1. 急性冠脉综合征（ACS）
   - 不稳定型心绞痛？
   - 非ST段抬高型心肌梗死（NSTEMI）？
2. 高血压病 3级 很高危
3. 2型糖尿病
4. 血脂异常

九、诊疗计划
1. 完善检查：
   - 急查心肌标志物动态变化
   - 心脏彩超
   - 冠脉CTA或冠脉造影
   - 动态心电图监测
   
2. 治疗方案：
   - 一级护理，心电监护，吸氧
   - 绝对卧床休息，低盐低脂糖尿病饮食
   - 抗血小板聚集：阿司匹林 100mg qd + 氯吡格雷 75mg qd
   - 抗凝治疗：低分子肝素 4000U q12h 皮下注射
   - 扩冠治疗：硝酸甘油 10mg 静脉泵入
   - 调脂稳定斑块：阿托伐他汀 20mg qn
   - 控制血压：继续硝苯地平缓释片 30mg qd
   - 控制血糖：胰岛素降糖治疗，监测血糖
   - 改善心肌代谢：曲美他嗪 20mg tid
   
3. 病情观察：
   - 密切观察胸痛、胸闷症状变化
   - 监测生命体征、心电图变化
   - 监测心肌标志物动态变化
   - 注意有无心律失常、心力衰竭等并发症

十、医师签名
主治医师：张医生
记录时间：2025年10月11日 15:00"""

print("=" * 100)
print("首次病程记录质控分析报告")
print("=" * 100)
print()
print("【病历信息】")
print(f"文档类型：首次病程记录")
print(f"患者姓名：李明")
print(f"年龄/性别：58岁/男")
print(f"科室：心内科")
print(f"住院号：2025001234")
print(f"记录时间：2025年10月11日 15:00")
print(f"内容长度：{len(content)} 字符")
print()
print("【开始质控分析】")
print("正在调用四川质控引擎（阿里云百炼 LLM API）...")
print()

client = TestClient(app)

response = client.post(
    "/api/v1/qc/sichuan/evaluate",
    json={
        "document_id": "record-first-course-qc-report",
        "document_content": content,
        "document_type": "首次病程记录",
        "persist": False
    }
)

if response.status_code != 200:
    print(f"❌ API 调用失败: {response.status_code}")
    print(response.text)
    sys.exit(1)

result = response.json()

print("【质控结果】")
print()
print(f"状态：{result['status']}")
print(f"文档 ID：{result['document_id']}")
print(f"评估模式：{result['mode']}")
print(f"时间戳：{result['timestamp']}")
print()

summary = result['evaluation_summary']
print("【评估摘要】")
print(f"总规则数：{summary['total_rules']}")
print(f"合规规则数：{summary['compliant_rules']}")
print(f"不合规规则数：{summary['total_rules'] - summary['compliant_rules']}")
print(f"合规率：{summary['compliance_rate']:.1f}%")
print(f"总体等级：{summary['overall_grade']}")
print(f"严重违规数：{summary['critical_violations']}")
print()

metrics = result['performance_metrics']
print("【性能指标】")
print(f"处理时间：{metrics['processing_time']:.2f} 秒")
print(f"Token 使用量：{metrics['token_usage']}")
print(f"预估成本：${metrics['estimated_cost']:.6f} (约 ¥{metrics['estimated_cost'] * 7:.4f})")
print()

print("【详细评估结果】")
print()

# 检查数据结构
if result['evaluation_results']:
    first_item = result['evaluation_results'][0]
    print(f"DEBUG: 第一个评估结果的键: {list(first_item.keys())}")
    print()

# 按类别分组
categories = {}
for item in result['evaluation_results']:
    cat = item.get('category', '未分类')
    if cat not in categories:
        categories[cat] = []
    categories[cat].append(item)

for category, items in sorted(categories.items()):
    compliant_count = sum(1 for item in items if item.get('is_compliant', False))
    total_count = len(items)
    compliance_rate = (compliant_count / total_count * 100) if total_count > 0 else 0
    
    print(f"\n{'=' * 100}")
    print(f"【{category}】 合规率: {compliance_rate:.1f}% ({compliant_count}/{total_count})")
    print('=' * 100)
    
    for idx, item in enumerate(items, 1):
        status = "✅ 合规" if item.get('is_compliant', False) else "❌ 不合规"
        severity = item.get('severity', 'N/A')
        print(f"\n{idx}. {status} | {item.get('rule_name', 'N/A')}")
        print(f"   严重程度: {severity}")
        print(f"   评分: {item.get('score', 0)}/100")
        if item.get('issues'):
            print(f"   问题: {'; '.join(item['issues'])}")
        if item.get('suggestions'):
            print(f"   建议: {'; '.join(item['suggestions'])}")

print()
print("=" * 100)
print("质控分析完成")
print("=" * 100)

# 保存详细报告到文件
output_file = '/home/ubuntu/coding/health-qc-monorepo/FIRST_COURSE_RECORD_QC_REPORT.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print()
print(f"✅ 详细报告已保存到: {output_file}")

