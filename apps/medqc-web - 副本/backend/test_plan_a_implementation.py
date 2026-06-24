#!/usr/bin/env python3
"""
测试方案 A 的实际实施效果

测试内容：
1. 验证 _extract_check_points 函数是否正确提取检查要点
2. 验证 _extract_enhanced_guidance 函数是否为复杂规则提取增强指导
3. 验证 _build_prompt 函数是否正确构建提示词
4. 对比优化前后的提示词长度和内容
"""

import sys
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.sichuan_qc_service import SichuanQCService


# 测试病历
TEST_MEDICAL_RECORD = """患者信息：张伟，男，44岁，入院科室：呼吸与危重症医学科，病区：呼吸内一科。 

主诉：体检发现肺部结节1周。

现病史：患者1周前单位组织体检，行胸部CT发现右肺下叶磨玻璃结节，直径约1.8cm，边界清晰。患者无咳嗽、咳痰、咯血、胸痛、气促等不适。为进一步诊治来我院就诊，门诊完善相关检查后以'右肺占位性病变'收入院。

既往史：既往体健。否认高血压、糖尿病病史。否认肝炎、结核病史。否认手术史、外伤史、输血史。否认食物、药物过敏史。

体格检查：T 36.5℃，P 72次/分，R 18次/分，BP 125/78 mmHg。神志清楚，精神可，自主体位，查体合作。全身皮肤黏膜无黄染，浅表淋巴结未触及肿大。双肺呼吸音清，未闻及干湿啰音。心律齐，各瓣膜听诊区未闻及杂音。腹部平软，无压痛，肝脾肋下未触及。双下肢无水肿。

辅助检查：
1. 血常规：WBC 8.6×10⁹/L，N 72%，Hb 135g/L，PLT 210×10⁹/L
2. 肝功能：ALT 38U/L，AST 42U/L，TBIL 16μmol/L，ALB 41g/L
3. 肾功能：Cr 78μmol/L，BUN 5.2mmol/L
4. 心电图：窦性心律，大致正常心电图
5. 胸部CT平扫（2024-10-25，外院）：右肺下叶见直径约1.8cm磨玻璃结节，边界清晰，无毛刺征，未见明显淋巴结肿大
6. 腹部超声：肝胆胰脾未见明显异常，双肾未见结石及积水
7. 空腹血糖：5.9mmol/L
8. 凝血功能：PT 12.3s，APTT 31.5s，FIB 3.8g/L

入院诊断：右肺占位性病变"""


# LX 系列规则 ID
LX_ADMISSION_RULES = [
    "LX-001", "LX-002", "LX-003", "LX-004", "LX-005",
    "LX-006", "LX-007", "LX-008", "LX-009"
]


def load_rules():
    """加载规则"""
    rules_file = Path(__file__).parent / "app" / "data" / "sichuan_rules_146.json"
    
    with open(rules_file, 'r', encoding='utf-8') as f:
        all_rules = json.load(f)
    
    # 筛选 LX 系列规则
    lx_rules = [rule for rule in all_rules if rule.get('rule_id') in LX_ADMISSION_RULES]
    
    return lx_rules


def test_extract_check_points():
    """测试检查要点提取"""
    print("=" * 80)
    print("测试 1: 检查要点提取")
    print("=" * 80)
    print()
    
    service = SichuanQCService()
    rules = load_rules()
    
    print(f"加载了 {len(rules)} 条规则")
    print()
    
    for rule in rules[:3]:  # 只测试前 3 条
        rule_id = rule.get('rule_id')
        rule_name = rule.get('name')
        custom_prompt = rule.get('custom_prompt', '')
        
        check_points = service._extract_check_points(custom_prompt)
        
        print(f"规则: {rule_id} - {rule_name}")
        print(f"custom_prompt 长度: {len(custom_prompt)} 字符")
        print(f"提取的检查要点长度: {len(check_points)} 字符")
        
        if check_points:
            print(f"检查要点预览:")
            print(check_points[:200] + "..." if len(check_points) > 200 else check_points)
        else:
            print("⚠️  未提取到检查要点")
        
        print()


def test_extract_enhanced_guidance():
    """测试增强指导提取"""
    print("=" * 80)
    print("测试 2: 增强指导提取（复杂规则）")
    print("=" * 80)
    print()
    
    service = SichuanQCService()
    rules = load_rules()
    
    # 测试复杂规则
    complex_rule_ids = ["LX-007", "LX-009"]
    
    for rule_id in complex_rule_ids:
        rule = next((r for r in rules if r.get('rule_id') == rule_id), None)
        if not rule:
            print(f"⚠️  未找到规则 {rule_id}")
            continue
        
        rule_name = rule.get('name')
        custom_prompt = rule.get('custom_prompt', '')
        
        # 提取检查要点（方案 A）
        check_points = service._extract_check_points(custom_prompt)
        
        # 提取增强指导（方案 A + 判定逻辑）
        enhanced_guidance = service._extract_enhanced_guidance(custom_prompt, rule_id)
        
        print(f"规则: {rule_id} - {rule_name}")
        print(f"custom_prompt 长度: {len(custom_prompt)} 字符")
        print(f"检查要点长度: {len(check_points)} 字符")
        print(f"增强指导长度: {len(enhanced_guidance)} 字符")
        print(f"增强比例: {len(enhanced_guidance) / len(check_points) * 100:.1f}%" if check_points else "N/A")
        
        if enhanced_guidance:
            print(f"增强指导预览:")
            print(enhanced_guidance[:300] + "..." if len(enhanced_guidance) > 300 else enhanced_guidance)
        
        print()


async def test_build_prompt():
    """测试提示词构建"""
    print("=" * 80)
    print("测试 3: 提示词构建")
    print("=" * 80)
    print()
    
    service = SichuanQCService()
    rules = load_rules()
    
    # 构建提示词
    prompt = await service._build_prompt(
        rules=rules,
        content=TEST_MEDICAL_RECORD,
        document_type="入院记录"
    )
    
    print(f"✅ 提示词构建成功")
    print(f"提示词总长度: {len(prompt)} 字符")
    print(f"估算 Token 数: {len(prompt) // 1.5:.0f}")
    print()
    
    # 保存提示词到文件
    output_file = "/tmp/plan_a_implementation_prompt.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(prompt)
    
    print(f"💾 提示词已保存到: {output_file}")
    print()
    
    # 显示提示词预览
    print("提示词预览（前 1000 字符）:")
    print("=" * 80)
    print(prompt[:1000])
    print("...")
    print("=" * 80)


def test_statistics():
    """统计优化效果"""
    print("=" * 80)
    print("测试 4: 优化效果统计")
    print("=" * 80)
    print()
    
    service = SichuanQCService()
    rules = load_rules()
    
    total_rules = len(rules)
    rules_with_custom_prompt = 0
    rules_with_check_points = 0
    complex_rules = 0
    
    total_custom_prompt_length = 0
    total_check_points_length = 0
    total_enhanced_guidance_length = 0
    
    for rule in rules:
        rule_id = rule.get('rule_id')
        custom_prompt = rule.get('custom_prompt', '')
        
        if custom_prompt:
            rules_with_custom_prompt += 1
            total_custom_prompt_length += len(custom_prompt)
        
        check_points = service._extract_check_points(custom_prompt)
        if check_points:
            rules_with_check_points += 1
            total_check_points_length += len(check_points)
        
        enhanced_guidance = service._extract_enhanced_guidance(custom_prompt, rule_id)
        if enhanced_guidance and len(enhanced_guidance) > len(check_points):
            complex_rules += 1
            total_enhanced_guidance_length += len(enhanced_guidance)
    
    print(f"总规则数: {total_rules}")
    print(f"包含 custom_prompt 的规则: {rules_with_custom_prompt} ({rules_with_custom_prompt/total_rules*100:.1f}%)")
    print(f"成功提取检查要点的规则: {rules_with_check_points} ({rules_with_check_points/total_rules*100:.1f}%)")
    print(f"使用增强指导的复杂规则: {complex_rules} ({complex_rules/total_rules*100:.1f}%)")
    print()
    
    if rules_with_custom_prompt > 0:
        avg_custom_prompt = total_custom_prompt_length / rules_with_custom_prompt
        print(f"平均 custom_prompt 长度: {avg_custom_prompt:.0f} 字符")
    
    if rules_with_check_points > 0:
        avg_check_points = total_check_points_length / rules_with_check_points
        print(f"平均检查要点长度: {avg_check_points:.0f} 字符")
        
        if rules_with_custom_prompt > 0:
            compression_ratio = (avg_check_points / avg_custom_prompt) * 100
            print(f"压缩比例: {compression_ratio:.1f}%")
    
    if complex_rules > 0:
        avg_enhanced = total_enhanced_guidance_length / complex_rules
        print(f"平均增强指导长度: {avg_enhanced:.0f} 字符")


async def main():
    """主函数"""
    print()
    print("=" * 80)
    print("方案 A 实施效果测试")
    print("=" * 80)
    print()
    
    # 测试 1: 检查要点提取
    test_extract_check_points()
    
    # 测试 2: 增强指导提取
    test_extract_enhanced_guidance()
    
    # 测试 3: 提示词构建
    await test_build_prompt()
    
    # 测试 4: 优化效果统计
    test_statistics()
    
    print()
    print("=" * 80)
    print("✅ 所有测试完成")
    print("=" * 80)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

