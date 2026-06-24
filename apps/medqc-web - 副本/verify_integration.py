#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证四川省质控系统集成
检查所有组件是否正确集成
"""

import sys
import os
import importlib.util

def verify_integration():
    """验证集成状态"""
    print("🔍 四川省质控系统集成验证")
    print("=" * 60)
    
    # 检查1: 四川省质控服务
    print("1. 检查四川省质控服务...")
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
        from services.sichuan_qc_service import get_sichuan_qc_service
        service = get_sichuan_qc_service()
        print("   ✅ 四川省质控服务导入成功")
        
        # 检查规则
        rules = service.get_applicable_rules()
        print(f"   ✅ 四川省规则加载成功: {len(rules)} 条规则")
        
    except Exception as e:
        print(f"   ❌ 四川省质控服务导入失败: {e}")
        return False
    
    # 检查2: SingleCallQCEngine
    print("2. 检查单次调用质控引擎...")
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), 'semantic_rules_engine'))
        from single_call_qc_engine import SingleCallQCEngine
        print("   ✅ SingleCallQCEngine导入成功")
    except Exception as e:
        print(f"   ❌ SingleCallQCEngine导入失败: {e}")
        return False
    
    # 检查3: 四川省规则
    print("3. 检查四川省规则定义...")
    try:
        from sichuan_qc_rules import SICHUAN_QC_RULES
        print(f"   ✅ 四川省规则定义成功: {len(SICHUAN_QC_RULES)} 条规则")
        
        # 显示规则分类
        categories = set(rule.get("category", "未分类") for rule in SICHUAN_QC_RULES)
        print(f"   📋 规则分类: {list(categories)}")
        
        complexity_dist = {}
        for rule in SICHUAN_QC_RULES:
            complexity = rule.get("complexity", "未知")
            complexity_dist[complexity] = complexity_dist.get(complexity, 0) + 1
        print(f"   📊 复杂度分布: {complexity_dist}")
        
    except Exception as e:
        print(f"   ❌ 四川省规则定义失败: {e}")
        return False
    
    # 检查4: API端点定义
    print("4. 检查API端点定义...")
    try:
        from main_api import app
        
        # 检查路由
        routes = []
        for route in app.routes:
            if hasattr(route, 'path') and '/api/qc/sichuan/' in route.path:
                routes.append(f"{route.methods} {route.path}")
        
        if routes:
            print("   ✅ 四川省质控API端点定义成功:")
            for route in routes:
                print(f"      - {route}")
        else:
            print("   ❌ 未找到四川省质控API端点")
            return False
            
    except Exception as e:
        print(f"   ❌ API端点检查失败: {e}")
        return False
    
    # 检查5: 依赖库
    print("5. 检查依赖库...")
    required_libs = ['aiohttp', 'fastapi', 'uvicorn', 'pydantic']
    for lib in required_libs:
        try:
            spec = importlib.util.find_spec(lib)
            if spec is not None:
                print(f"   ✅ {lib} 可用")
            else:
                print(f"   ❌ {lib} 不可用")
                return False
        except Exception as e:
            print(f"   ❌ {lib} 检查失败: {e}")
            return False
    
    # 检查6: 测试文档
    print("6. 检查测试文档...")
    test_doc_path = os.path.join(os.path.dirname(__file__), 'backend', '张伟_病程记录.txt')
    if os.path.exists(test_doc_path):
        with open(test_doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"   ✅ 测试文档可用: {len(content)} 字符")
    else:
        print(f"   ❌ 测试文档不存在: {test_doc_path}")
        return False
    
    print("\n🎉 四川省质控系统集成验证完成!")
    print("=" * 60)
    print("✅ 所有组件集成成功")
    print("🚀 可以启动API服务器进行测试")
    print("📋 启动命令: cd backend && uvicorn main_api:app --host 0.0.0.0 --port 8001")
    print("📚 API文档: http://localhost:8001/docs")
    
    return True

if __name__ == "__main__":
    success = verify_integration()
    if success:
        print("\n✅ 集成验证成功!")
        exit(0)
    else:
        print("\n❌ 集成验证失败!")
        exit(1)
