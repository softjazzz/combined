#!/usr/bin/env python3
"""
测试 LX-003 优化效果
验证前置短路和提示词优化是否生效
"""
import asyncio
import sys
from pathlib import Path

# 添加父目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_lx003():
    """测试 LX-003 的前置短路功能"""
    from routers.qc_sichuan import TestRuleRequest
    from routers.qc_sichuan import router
    from fastapi import Request
    from starlette.datastructures import Headers

    print("\n" + "="*80)
    print("测试 LX-003 - 成人病历（应触发前置短路）")
    print("="*80 + "\n")

    # 模拟成人病历
    adult_medical_text = """
    入院记录

    姓名：张三
    性别：男
    年龄：44岁
    主诉：胸痛3天，加重1天。

    现病史：患者3天前无明显诱因出现胸痛，位于胸骨后，呈压榨样疼痛，
    向左肩及左臂放射，伴大汗、恶心。1天前症状加重，遂来我院就诊。

    体格检查：T 36.5℃，P 88次/分，R 18次/分，BP 145/92mmHg。
    神志清楚，精神可。心界不大，心率88次/分，律齐，各瓣膜听诊区未闻及病理性杂音。
    双肺呼吸音清，未闻及干湿啰音。腹软，无压痛。

    辅助检查：心电图示：ST段抬高。心肌酶谱：肌钙蛋白I 2.5ng/ml。
    """

    # 创建请求
    req = TestRuleRequest(
        rule_id="LX-003",
        medical_text=adult_medical_text
    )

    # 模拟 Request 对象
    class MockRequest:
        def __init__(self):
            self.headers = Headers({})
            self.state = type('obj', (object,), {'trace_id': 'test-trace-id'})()

    mock_request = MockRequest()

    try:
        # 调用测试接口
        from routers.qc_sichuan import test_rule
        result = await test_rule(mock_request, req)

        print("✅ 测试成功！")
        print("\n响应数据：")
        print(f"  规则ID: {result['data']['rule_id']}")
        print(f"  合规状态: {result['data']['is_compliant']}")
        print(f"  findings: {result['data']['findings']}")
        print(f"  evidence: {result['data']['evidence']}")
        print(f"  not_applicable: {result['data'].get('not_applicable', 'N/A')}")
        print(f"  not_applicable_reason: {result['data'].get('not_applicable_reason', 'N/A')}")
        print(f"  llm_raw_output: {result['data']['llm_raw_output']}")
        print(f"  Token使用: {result['data']['token_usage']}")

        # 验证前置短路
        if result['data']['llm_raw_output'] is None:
            print("\n✅ 前置短路成功！未调用 LLM，节省了 Token")
        else:
            print("\n⚠️  未触发前置短路，LLM 被调用了")

        if result['data'].get('not_applicable'):
            print("✅ not_applicable 字段正确标记")
        else:
            print("⚠️  not_applicable 字段未设置")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n开始测试 LX-003 优化...\n")
    asyncio.run(test_lx003())
    print("\n测试完成！\n")
