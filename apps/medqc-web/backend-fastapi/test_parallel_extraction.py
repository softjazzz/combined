#!/usr/bin/env python3
"""
测试多模块并行提取功能
"""
import requests
import json
import time

API_BASE = "http://localhost:8000/api/v1/case-front-page"

# 测试病历：包含入院记录和手术记录
TEST_MEDICAL_TEXT = """
入院记录

患者张伟，性别男，年龄44岁，已婚，汉族，农民。
身份证号：510521198102040018
联系电话：13541593206
现住址：泸州泸县天立B区01号
联系人：张伟（本人）
联系人电话：13541593206

以"发现肛旁肿物疼痛2+天"为主诉于2025年03月29日13:49入院。

现病史：
患者2天前无明显诱因出现肛旁肿物，伴疼痛，无发热，无恶心呕吐。

既往史：
有慢病病史"甲减"，现口服优甲乐。否认传染病史。
2024年10月01日行体外冲击波碎石术。
药物过敏：无

体格检查：
T 36.3℃，P 98次/分，R 20次/分，BP 147/95mmHg
身高170cm，体重75Kg

辅助检查：
2025-03-29 常规心电图检查：窦性心律
2025-03-29 腹部彩超：轻度脂肪肝。右肾结石。左肾砂粒样结石。
2025-03-29 心脏彩超：二、三尖瓣反流（轻度）。左室舒张功能降低。
2025-03-29 血常规：WBC 8.58×10^9/L，RBC 5.17×10^12/L，HGB 158g/L，PLT 266×10^9/L

初步诊断：
1. 肛周脓肿
2. 甲状腺功能减退

入院科室：外二科
病房：54床
住院号：350827
第2次入院

手术记录：
手术时间：2025年03月31日
手术方式：高位复杂性肛瘘切除术+肛周脓肿切开引流术+亚甲蓝肛周封闭术
麻醉方式：腰麻联合硬脊膜外腔阻滞麻醉
术中诊断：1.高位复杂性肛瘘 2.肛周脓肿 3.肛窦炎
术者：王标
Ⅰ助：孙治庆
麻醉医师：刘杰
术中出血约5ml，麻醉满意，手术顺利

科主任：王飞
主治医师：王标
住院医师：李方健
责任护士：张小红

出院诊断：
1. 高位复杂性肛瘘
2. 肛周脓肿
3. 肛窦炎
4. 甲状腺功能减退
5. 脂肪肝
6. 双肾结石

住院天数：5天
离院方式：医嘱离院
住院总费用：8562.50元
自付金额：1285.00元
"""

def test_extract_structured():
    """测试结构化提取 API"""
    print("=" * 60)
    print("测试：多模块并行病案首页结构化提取")
    print("=" * 60)
    
    url = f"{API_BASE}/extract"
    payload = {"medical_text": TEST_MEDICAL_TEXT}
    
    print(f"\n请求 URL: {url}")
    print(f"病历长度: {len(TEST_MEDICAL_TEXT)} 字符")
    print("\n正在提取，请稍候...")
    
    start_time = time.time()
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        elapsed = time.time() - start_time
        
        print(f"\n响应状态: {response.status_code}")
        print(f"耗时: {elapsed:.2f} 秒")
        
        if response.status_code == 200:
            data = response.json()
            result = data.get("data", {})
            
            print("\n" + "=" * 60)
            print("提取结果摘要")
            print("=" * 60)
            
            # 患者基本信息
            basic = result.get("basic_info", {})
            print(f"\n【患者基本信息】")
            print(f"  姓名: {basic.get('patient_name')}")
            print(f"  性别: {basic.get('gender_text')}")
            print(f"  年龄: {basic.get('age_years')}")
            print(f"  民族: {basic.get('ethnicity')}")
            print(f"  身份证: {basic.get('id_number')}")
            print(f"  职业: {basic.get('occupation')}")
            
            # 住院信息
            hosp = result.get("hospitalization", {})
            print(f"\n【住院信息】")
            print(f"  住院号: {hosp.get('medical_record_no')}")
            print(f"  第 {hosp.get('admission_times_in_hospital')} 次住院")
            print(f"  入院科室: {hosp.get('admission_dept')}")
            print(f"  入院日期: {hosp.get('admission_datetime')}")
            print(f"  住院天数: {hosp.get('actual_hospital_days')}")
            
            # 诊断信息
            diag = result.get("diagnoses", {})
            print(f"\n【诊断信息】")
            print(f"  入院主诊断: {diag.get('admission_main_diagnosis_text')}")
            admission_others = diag.get('admission_other_diagnoses_texts', [])
            if admission_others:
                print(f"  入院其他诊断: {', '.join(admission_others[:3])}")
            print(f"  出院主诊断: {diag.get('discharge_main_diagnosis_text')}")
            discharge_others = diag.get('discharge_other_diagnoses_texts', [])
            if discharge_others:
                print(f"  出院其他诊断: {', '.join(discharge_others[:3])}")
            
            # 手术信息
            proc = result.get("procedures", {})
            print(f"\n【手术信息】")
            print(f"  主要手术: {proc.get('main_procedure_text')}")
            print(f"  手术日期: {proc.get('main_procedure_date')}")
            print(f"  术者: {proc.get('surgeon_name')}")
            print(f"  麻醉方式: {proc.get('anesthesia_method')}")
            
            # 人员信息
            staff = result.get("staff", {})
            print(f"\n【人员信息】")
            print(f"  科主任: {staff.get('dept_director')}")
            print(f"  主治医师: {staff.get('attending_physician')}")
            print(f"  住院医师: {staff.get('resident_physician')}")
            print(f"  责任护士: {staff.get('responsible_nurse')}")
            
            # 其他信息
            other = result.get("other_medical_info", {})
            print(f"\n【其他医疗信息】")
            print(f"  药物过敏: {other.get('drug_allergy_flag_text') or '无'}")
            print(f"  离院方式: {other.get('discharge_method')}")
            
            # 费用信息
            costs = result.get("costs", {})
            print(f"\n【费用信息】")
            print(f"  住院总费用: {costs.get('total_cost')}")
            print(f"  自付金额: {costs.get('self_paid')}")
            
            # 统计提取字段数
            total_fields = 0
            for key in result:
                if isinstance(result[key], dict):
                    total_fields += len([v for v in result[key].values() if v is not None])
            
            print(f"\n" + "=" * 60)
            print(f"总计提取有效字段: {total_fields} 个")
            print(f"提取耗时: {elapsed:.2f} 秒")
            print("=" * 60)
            
            # 保存完整结果到文件
            with open("/tmp/extraction_result.json", "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n完整结果已保存到: /tmp/extraction_result.json")
            
            return True
        else:
            print(f"错误: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("错误: 请求超时")
        return False
    except Exception as e:
        print(f"错误: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_extract_structured()
    exit(0 if success else 1)
