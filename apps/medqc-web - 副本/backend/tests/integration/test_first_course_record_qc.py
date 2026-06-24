"""
首次病程记录质控分析测试

创建一个符合医疗规范的首次病程记录，并使用质控流程进行分析
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime
import json


class TestFirstCourseRecordQC:
    """首次病程记录质控测试"""

    @pytest.fixture
    def first_course_record(self):
        """
        创建符合医疗规范的首次病程记录
        
        首次病程记录是住院病历的重要组成部分，应在患者入院后8小时内完成
        """
        return {
            "record_id": "record-first-course-001",
            "record_type": "first_course",
            "patient_name": "李明",
            "age": 58,
            "gender": "男",
            "department": "心内科",
            "admission_number": "2025001234",
            "bed_number": "15床",
            "admission_date": "2025-10-11",
            "admission_time": "09:30",
            "record_date": "2025-10-11 15:00",
            "doctor_name": "张医生",
            "content": """
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
        }

    def test_first_course_record_qc_analysis(self, client: TestClient, first_course_record):
        """
        测试首次病程记录的质控分析
        
        验证流程：
        1. 创建首次病程记录
        2. 提交质控分析
        3. 查询分析进度
        4. 获取质控结果
        5. 验证质控结果的完整性
        """
        print("\n" + "="*80)
        print("首次病程记录质控分析测试")
        print("="*80)
        
        # 步骤 1: 显示病程记录内容
        print("\n【步骤 1】首次病程记录内容")
        print("-"*80)
        print(f"患者姓名：{first_course_record['patient_name']}")
        print(f"年龄：{first_course_record['age']}岁")
        print(f"性别：{first_course_record['gender']}")
        print(f"科室：{first_course_record['department']}")
        print(f"入院时间：{first_course_record['admission_date']} {first_course_record['admission_time']}")
        print(f"记录时间：{first_course_record['record_date']}")
        print(f"\n病程记录详细内容：\n{first_course_record['content']}")
        
        # 步骤 2: 提交质控分析
        print("\n" + "="*80)
        print("【步骤 2】提交质控分析")
        print("-"*80)
        
        record_id = first_course_record["record_id"]
        response = client.post(
            f"/api/v1/qc/analyze/{record_id}",
            json=first_course_record
        )
        
        assert response.status_code == 200, f"质控分析请求失败: {response.text}"
        
        analysis_data = response.json()
        assert analysis_data["success"] is True, "质控分析返回失败状态"
        
        analysis_result = analysis_data["data"]
        analysis_id = analysis_result.get("analysis_id")
        
        print(f"✅ 质控分析已提交")
        print(f"   分析ID: {analysis_id}")
        print(f"   病历ID: {record_id}")
        print(f"   分析状态: {analysis_result.get('status')}")
        
        # 步骤 3: 查询分析进度
        print("\n" + "="*80)
        print("【步骤 3】查询分析进度")
        print("-"*80)
        
        if analysis_id:
            progress_response = client.get(f"/api/v1/qc/progress/{analysis_id}")
            assert progress_response.status_code == 200
            
            progress_data = progress_response.json()
            progress_info = progress_data["data"]
            
            print(f"✅ 分析进度查询成功")
            print(f"   状态: {progress_info.get('status')}")
            print(f"   进度: {progress_info.get('progress', 0)}%")
            print(f"   开始时间: {progress_info.get('started_at')}")
        
        # 步骤 4: 获取质控结果
        print("\n" + "="*80)
        print("【步骤 4】获取质控结果")
        print("-"*80)
        
        result_response = client.get(f"/api/v1/qc/result/{record_id}")
        assert result_response.status_code == 200, f"获取质控结果失败: {result_response.text}"

        # 注意：get_result 端点直接返回 QCResult 模型，不包装在 success_response 中
        qc_result = result_response.json()
        
        print(f"✅ 质控结果获取成功")
        print(f"\n质控评分: {qc_result.get('overall_score', 0)}/100")
        print(f"质控等级: {qc_result.get('overall_grade', 'N/A')}")
        print(f"分析时间: {qc_result.get('analysis_date', 'N/A')}")
        
        # 步骤 5: 显示详细质控结果
        print("\n" + "="*80)
        print("【步骤 5】详细质控结果")
        print("="*80)
        
        issues = qc_result.get("issues", [])
        
        if issues:
            print(f"\n发现 {len(issues)} 个质控问题：\n")
            
            for idx, issue in enumerate(issues, 1):
                print(f"{idx}. {issue.get('title', '未知问题')}")
                print(f"   严重程度: {issue.get('severity', 'N/A')}")
                print(f"   问题描述: {issue.get('description', 'N/A')}")
                print(f"   涉及规则: {issue.get('rule_code', 'N/A')}")
                
                if issue.get('suggestion'):
                    print(f"   改进建议: {issue['suggestion']}")
                
                print()
        else:
            print("\n✅ 未发现质控问题，病程记录符合规范！")
        
        # 显示使用的质控规则
        rule_results = qc_result.get("rule_results", [])
        if rule_results:
            print(f"\n使用的质控规则（共 {len(rule_results)} 条）：")
            for rule in rule_results:
                print(f"  - {rule.get('rule_name', 'N/A')} ({rule.get('rule_id', 'N/A')}) - 评分: {rule.get('score', 0)}/{rule.get('max_score', 100)}")
        
        # 步骤 6: 获取统计汇总
        print("\n" + "="*80)
        print("【步骤 6】质控统计汇总")
        print("-"*80)
        
        summary_response = client.get("/api/v1/reports/qc/summary")
        assert summary_response.status_code == 200
        
        summary_data = summary_response.json()
        summary = summary_data["data"]
        
        print(f"✅ 统计汇总获取成功")
        print(f"\n总病历数: {summary.get('total_records', 0)}")
        print(f"已质控数: {summary.get('qc_completed', 0)}")
        print(f"平均评分: {summary.get('average_score', 0):.2f}")
        print(f"优秀率: {summary.get('excellent_rate', 0):.2f}%")
        
        # 最终总结
        print("\n" + "="*80)
        print("【质控分析完成】")
        print("="*80)
        print(f"\n✅ 首次病程记录质控分析已完成")
        print(f"   患者: {first_course_record['patient_name']}")
        print(f"   科室: {first_course_record['department']}")
        print(f"   质控评分: {qc_result.get('overall_score', 0)}/100")
        print(f"   质控等级: {qc_result.get('overall_grade', 'N/A')}")
        print(f"   发现问题: {len(issues)} 个")
        print(f"   分析状态: 成功")
        print("\n" + "="*80)

        # 验证结果完整性
        assert "overall_score" in qc_result, "质控结果缺少评分"
        assert "overall_grade" in qc_result, "质控结果缺少等级"
        assert "issues" in qc_result, "质控结果缺少问题列表"
        
        return qc_result

