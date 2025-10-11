"""
首次病程记录质控分析测试 - 使用真实的 LLM API

本测试使用四川质控引擎（Sichuan QC Engine），调用真实的阿里云百炼 API 进行质控分析。

测试流程：
1. 创建符合医疗规范的首次病程记录
2. 调用四川质控引擎进行分析
3. 验证 LLM 返回的质控结果
4. 输出详细的质控报告

与 test_first_course_record_qc.py 的区别：
- test_first_course_record_qc.py: 使用模拟引擎（QCService）
- test_first_course_record_qc_real_llm.py: 使用真实 LLM（SichuanQCService）
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestFirstCourseRecordQCRealLLM:
    """首次病程记录质控分析测试类 - 真实 LLM"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    @pytest.fixture
    def first_course_record(self):
        """创建符合医疗规范的首次病程记录"""
        return {
            "record_id": "record-first-course-real-llm-001",
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

    def test_first_course_record_qc_with_real_llm(self, client: TestClient, first_course_record):
        """测试首次病程记录质控分析 - 使用真实 LLM API"""
        
        print("\n" + "="*80)
        print("首次病程记录质控分析 - 真实 LLM API 测试")
        print("="*80)
        
        # 【步骤 1】显示病程记录基本信息
        print(f"\n【步骤 1】病程记录基本信息")
        print(f"患者姓名：{first_course_record['patient_name']}")
        print(f"年龄：{first_course_record['age']}岁")
        print(f"性别：{first_course_record['gender']}")
        print(f"科室：{first_course_record['department']}")
        print(f"入院时间：{first_course_record['admission_date']} {first_course_record['admission_time']}")
        print(f"记录时间：{first_course_record['record_date']}")
        print(f"内容长度：{len(first_course_record['content'])} 字符")
        
        # 【步骤 2】调用四川质控引擎进行分析
        print(f"\n【步骤 2】调用四川质控引擎（真实 LLM API）")
        print(f"API 端点：https://dashscope.aliyuncs.com/compatible-mode/v1")
        print(f"模型：qwen2.5-14b-instruct")
        print(f"文档类型：首次病程记录")
        
        response = client.post(
            "/api/v1/qc/sichuan/evaluate",
            json={
                "document_id": first_course_record["record_id"],
                "document_content": first_course_record["content"],
                "document_type": "首次病程记录",
                "persist": True
            }
        )
        
        print(f"响应状态码：{response.status_code}")
        assert response.status_code == 200, f"API 调用失败: {response.text}"
        
        result_data = response.json()
        print(f"响应结构：{list(result_data.keys())}")

        # 【步骤 3】解析质控结果
        print(f"\n【步骤 3】解析质控结果")

        # 四川质控引擎的响应格式（不包装在 data 中）
        qc_result = result_data
        evaluation_summary = qc_result.get("evaluation_summary", {})
        performance_metrics = qc_result.get("performance_metrics", {})

        # 检查是否成功调用 LLM
        status = qc_result.get("status", "")
        mode = qc_result.get("mode", "")

        if status == "success":
            print("✅ 成功调用真实 LLM API")
            print(f"模式：{mode}")
        else:
            print(f"⚠️  警告：质控分析失败，状态：{status}")

        # 【步骤 4】显示质控结果
        print(f"\n【步骤 4】质控结果详情")
        print(f"文档 ID：{qc_result.get('document_id', 'N/A')}")
        print(f"状态：{status}")
        print(f"时间戳：{qc_result.get('timestamp', 'N/A')}")

        # 评估摘要
        print(f"\n【评估摘要】")
        print(f"总规则数：{evaluation_summary.get('total_rules', 0)}")
        print(f"合规规则数：{evaluation_summary.get('compliant_rules', 0)}")
        print(f"合规率：{evaluation_summary.get('compliance_rate', 0)}%")
        print(f"总体等级：{evaluation_summary.get('overall_grade', 'N/A')}")
        print(f"严重违规数：{evaluation_summary.get('critical_violations', 0)}")

        # 评估结果
        evaluation_results = qc_result.get("evaluation_results", [])
        if evaluation_results:
            print(f"\n【评估结果】（共 {len(evaluation_results)} 条）")
            for idx, result in enumerate(evaluation_results[:3], 1):  # 只显示前 3 条
                print(f"\n结果 {idx}:")
                print(f"  规则 ID：{result.get('rule_id', 'N/A')}")
                print(f"  是否合规：{result.get('is_compliant', False)}")
                print(f"  发现：{result.get('findings', 'N/A')}")
                print(f"  置信度：{result.get('confidence', 0)}")
                evidence = result.get('evidence', '')
                if evidence:
                    print(f"  证据：{evidence[:200]}...")  # 只显示前 200 字符

        # 性能指标
        if performance_metrics:
            print(f"\n【性能指标】")
            print(f"处理时间：{performance_metrics.get('processing_time', 0):.2f} 秒")
            print(f"Token 使用量：{performance_metrics.get('token_usage', 0)}")
            print(f"预估成本：${performance_metrics.get('estimated_cost', 0):.6f}")

        # 优化指标
        optimization_metrics = qc_result.get("optimization_metrics", {})
        if optimization_metrics:
            print(f"\n【优化指标】")
            print(f"Token 节省率：{optimization_metrics.get('token_savings_rate', 0)*100:.1f}%")
            print(f"实际节省 Token：{optimization_metrics.get('actual_tokens_saved', 0)}")
            print(f"成本节省：${optimization_metrics.get('cost_savings', 0):.6f}")

        # 【步骤 5】验证结果
        print(f"\n【步骤 5】验证结果")
        assert "document_id" in qc_result, "缺少 document_id"
        assert "evaluation_summary" in qc_result, "缺少 evaluation_summary"
        assert "status" in qc_result, "缺少 status"
        assert qc_result["status"] == "success", f"质控分析失败：{qc_result.get('status')}"
        assert evaluation_summary.get("compliance_rate", 0) > 0, "合规率应大于 0"

        print("✅ 所有验证通过")
        
        print("\n" + "="*80)
        print("测试完成")
        print("="*80)

