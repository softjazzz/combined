#!/usr/bin/env python3
"""
使用146条四川规则测试首次病程记录质控
只应用与病程记录相关的规则
"""
import requests
import json

# 首次病程记录测试数据
first_course_record = """
首次病程记录

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
患者于3天前无明显诱因出现胸闷、胸痛，呈压榨性疼痛，位于胸骨后，持续时间约5-10分钟，休息后可缓解。1天前上述症状加重，伴有气促、出汗，活动后明显，休息时亦有发作。患者自服"速效救心丸"后症状无明显缓解，遂来我院急诊就诊。

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

四肢：四肢活动自如，双下肢无水肿，足背动脉搏动正常。

神经系统：生理反射存在，病理反射未引出。

七、辅助检查
1. 心电图（2025-10-11 急诊）：窦性心律，心率85次/分，V1-V4导联ST段压低0.1-0.2mV，T波倒置。

2. 心肌酶谱（2025-10-11 急诊）：
   - 肌钙蛋白I（cTnI）：0.8 ng/mL ↑（正常值<0.04 ng/mL）
   - 肌酸激酶同工酶（CK-MB）：45 U/L ↑（正常值<25 U/L）
   - 肌酸激酶（CK）：280 U/L ↑（正常值<190 U/L）
   - 乳酸脱氢酶（LDH）：320 U/L（正常值135-225 U/L）

3. 血常规（2025-10-11）：
   - 白细胞：8.5×10^9/L（正常值4-10×10^9/L）
   - 红细胞：4.8×10^12/L（正常值4.3-5.8×10^12/L）
   - 血红蛋白：145 g/L（正常值130-175 g/L）
   - 血小板：220×10^9/L（正常值100-300×10^9/L）

4. 生化检查（2025-10-11）：
   - 空腹血糖：8.2 mmol/L ↑（正常值3.9-6.1 mmol/L）
   - 总胆固醇：6.5 mmol/L ↑（正常值<5.2 mmol/L）
   - 甘油三酯：2.8 mmol/L ↑（正常值<1.7 mmol/L）
   - 低密度脂蛋白：4.2 mmol/L ↑（正常值<3.4 mmol/L）
   - 高密度脂蛋白：0.9 mmol/L ↓（正常值>1.0 mmol/L）
   - 肌酐：85 μmol/L（正常值44-133 μmol/L）
   - 尿素氮：6.5 mmol/L（正常值2.9-8.2 mmol/L）

5. 凝血功能（2025-10-11）：
   - 凝血酶原时间（PT）：12.5秒（正常值11-13秒）
   - 活化部分凝血活酶时间（APTT）：32秒（正常值26-36秒）
   - 国际标准化比值（INR）：1.05（正常值0.8-1.2）

八、初步诊断
1. 急性冠脉综合征
   - 不稳定型心绞痛
2. 高血压病 3级 极高危组
3. 2型糖尿病
4. 血脂异常

九、诊疗计划
1. 心内科一级护理，低盐低脂糖尿病饮食。
2. 心电监护，吸氧（鼻导管2-3L/min）。
3. 完善相关检查：
   - 复查心肌酶谱、心电图（每日）
   - 心脏彩超
   - 冠状动脉造影（择期）
   - 动态心电图
   - 胸部X线片
4. 药物治疗：
   - 抗血小板聚集：阿司匹林 100mg qd po + 氯吡格雷 75mg qd po
   - 抗凝治疗：低分子肝素钙 5000U q12h ih
   - 扩冠治疗：硝酸异山梨酯 10mg tid po
   - 调脂治疗：阿托伐他汀 20mg qn po
   - 降压治疗：硝苯地平缓释片 30mg qd po
   - 降糖治疗：二甲双胍 0.5g tid po
   - β受体阻滞剂：美托洛尔 25mg bid po
   - ACEI类药物：依那普利 5mg qd po
5. 密切观察病情变化，如有胸痛加重、心律失常等情况及时报告上级医师。
6. 向患者及家属交代病情，告知可能需要行冠状动脉造影及支架植入术，取得知情同意。

十、上级医师查房意见
（待上级医师查房后补充）

记录医师：张医生
记录时间：2025年10月11日 15:00
""".strip()

def main():
    print("="*80)
    print("四川省质控规则测试 - 首次病程记录（146条规则）")
    print("="*80)

    # 步骤1: 获取适用于病程记录的规则
    print("\n【步骤1】获取适用于病程记录的质控规则...")
    try:
        rules_response = requests.get(
            "http://localhost:8000/api/v1/qc/sichuan/rules",
            params={"document_type": "progress_note"},  # 使用英文文档类型
            timeout=10
        )

        if rules_response.status_code == 200:
            rules_data = rules_response.json()
            rules = rules_data.get("rules", [])
            print(f"✅ 成功获取 {len(rules)} 条适用于病程记录的规则")
            print(f"   数据来源: {rules_data.get('source', 'unknown')}")

            # 显示前5条规则
            print(f"\n📋 规则示例（前5条）:")
            for i, rule in enumerate(rules[:5], 1):
                print(f"  {i}. [{rule.get('rule_id')}] {rule.get('name')[:60]}...")
        else:
            print(f"❌ 获取规则失败: {rules_response.status_code}")
            print(f"   响应内容: {rules_response.text[:200]}")
            return
    except Exception as e:
        print(f"❌ 请求规则API失败: {e}")
        return

    # 步骤2: 提交质控评估
    print(f"\n【步骤2】提交首次病程记录进行质控评估...")
    print(f"   病历长度: {len(first_course_record)} 字符")

    try:
        qc_payload = {
            "document_id": "test-first-course-001",
            "document_content": first_course_record,
            "document_type": "病程记录",
            "patient_info": {
                "name": "李明",
                "age": "58",
                "gender": "男"
            },
            "persist": False  # 不持久化到数据库
        }

        eval_response = requests.post(
            "http://localhost:8000/api/v1/qc/sichuan/evaluate",
            json=qc_payload,
            timeout=120  # LLM调用可能需要较长时间
        )

        if eval_response.status_code == 200:
            result = eval_response.json()
            print(f"✅ 质控评估完成")

            # 步骤3: 显示评估结果
            print("\n" + "="*80)
            print("【步骤3】质控评估结果")
            print("="*80)

            # 总体评估
            summary = result.get("evaluation_summary", {})
            print(f"\n📊 总体评估:")
            print(f"   应用规则数: {summary.get('total_rules', 0)} 条")
            print(f"   符合规则数: {summary.get('compliant_rules', 0)} 条")
            print(f"   违规规则数: {summary.get('total_rules', 0) - summary.get('compliant_rules', 0)} 条")
            print(f"   符合率: {summary.get('compliance_rate', 0):.1f}%")
            print(f"   综合评分: {summary.get('overall_score', 0):.1f} 分")
            print(f"   质量等级: {summary.get('overall_grade', 'N/A')}")
            print(f"   严重违规: {summary.get('critical_violations', 0)} 个")

            # 详细结果
            eval_results = result.get("evaluation_results", [])
            if eval_results:
                print(f"\n📋 详细质控结果（共 {len(eval_results)} 条）:")
                print("-"*80)

                # 分类统计
                compliant_count = sum(1 for r in eval_results if r.get("is_compliant"))
                non_compliant_count = len(eval_results) - compliant_count

                # 显示不符合的规则
                non_compliant_rules = [r for r in eval_results if not r.get("is_compliant")]
                if non_compliant_rules:
                    print(f"\n❌ 不符合的规则（{len(non_compliant_rules)} 条）:")
                    for i, item in enumerate(non_compliant_rules, 1):
                        rule_info = item.get("rule_info", {})
                        print(f"\n  {i}. [{item.get('rule_id')}] {rule_info.get('name', 'N/A')}")
                        print(f"     缺陷等级: {rule_info.get('defect_level', 'N/A')}")
                        print(f"     扣分: {rule_info.get('score_deduction', 'N/A')}")
                        print(f"     评估意见: {item.get('reason', 'N/A')[:200]}...")
                        if item.get("suggestions"):
                            print(f"     改进建议: {item.get('suggestions')[:200]}...")
                else:
                    print(f"\n✅ 所有规则均符合要求！")

                # 显示符合的规则（简要）
                compliant_rules = [r for r in eval_results if r.get("is_compliant")]
                if compliant_rules:
                    print(f"\n✅ 符合的规则（{len(compliant_rules)} 条）:")
                    for i, item in enumerate(compliant_rules[:10], 1):  # 只显示前10条
                        rule_info = item.get("rule_info", {})
                        print(f"  {i}. [{item.get('rule_id')}] {rule_info.get('name', 'N/A')[:60]}...")
                    if len(compliant_rules) > 10:
                        print(f"  ... 还有 {len(compliant_rules) - 10} 条符合的规则")

            # API性能统计
            print(f"\n⏱️  性能统计:")
            print(f"   API调用时间: {result.get('api_time', 0):.2f} 秒")
            token_usage = result.get("token_usage", {})
            if token_usage:
                print(f"   Token使用: {token_usage.get('total_tokens', 0)} (提示: {token_usage.get('prompt_tokens', 0)}, 补全: {token_usage.get('completion_tokens', 0)})")
            print(f"   使用模型: {result.get('model_used', 'N/A')}")

        else:
            print(f"❌ 质控评估失败: {eval_response.status_code}")
            print(f"   响应内容: {eval_response.text[:500]}")
            return

    except requests.exceptions.Timeout:
        print(f"❌ 请求超时（120秒），LLM响应时间过长")
        return
    except Exception as e:
        print(f"❌ 质控评估失败: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "="*80)
    print("【测试完成】")
    print("="*80)

if __name__ == "__main__":
    main()
