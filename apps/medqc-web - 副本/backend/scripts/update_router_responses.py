#!/usr/bin/env python3
"""
自动更新路由文件以使用统一的响应格式

此脚本会：
1. 检查每个路由文件
2. 添加必要的导入
3. 生成更新建议报告

注意：此脚本只生成报告，不会自动修改文件。
需要手动审查并应用更改。
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple

# 路由文件目录
ROUTERS_DIR = Path(__file__).parent.parent / "app" / "routers"

# 需要的导入
REQUIRED_IMPORTS = [
    "from fastapi import Request",
    "from ..core.response import success_response, error_response, get_trace_id, ErrorCode, StatusCode",
]

# 已完成的文件
COMPLETED_FILES = [
    "system.py",
    "llm_info.py",
    "records.py",  # 部分完成
]


def check_file_imports(file_path: Path) -> Dict[str, bool]:
    """检查文件是否包含必要的导入"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return {
        "has_request_import": "from fastapi import" in content and "Request" in content,
        "has_response_import": "from ..core.response import" in content,
        "has_success_response": "success_response" in content,
        "has_error_response": "error_response" in content,
    }


def find_return_statements(file_path: Path) -> List[Tuple[int, str]]:
    """查找文件中的 return 语句"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    returns = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("return {") or stripped.startswith("return JSONResponse"):
            returns.append((i, stripped))
    
    return returns


def analyze_router_file(file_path: Path) -> Dict:
    """分析路由文件"""
    imports = check_file_imports(file_path)
    returns = find_return_statements(file_path)
    
    # 统计需要更新的 return 语句
    needs_update = []
    for line_num, statement in returns:
        if "success_response" not in statement and "error_response" not in statement:
            needs_update.append((line_num, statement))
    
    return {
        "file": file_path.name,
        "imports": imports,
        "total_returns": len(returns),
        "needs_update": len(needs_update),
        "return_statements": needs_update,
    }


def generate_report():
    """生成更新报告"""
    print("=" * 80)
    print("路由响应格式更新报告")
    print("=" * 80)
    print()
    
    router_files = sorted([f for f in ROUTERS_DIR.glob("*.py") if f.name != "__init__.py"])
    
    total_files = len(router_files)
    completed = 0
    pending = 0
    
    pending_files = []
    
    for file_path in router_files:
        analysis = analyze_router_file(file_path)
        
        is_completed = file_path.name in COMPLETED_FILES
        
        if is_completed:
            completed += 1
            status = "✅ 已完成"
        else:
            pending += 1
            status = "⏳ 待更新"
            pending_files.append(analysis)
        
        print(f"{status} - {analysis['file']}")
        print(f"  导入状态:")
        print(f"    - Request: {'✓' if analysis['imports']['has_request_import'] else '✗'}")
        print(f"    - response helpers: {'✓' if analysis['imports']['has_response_import'] else '✗'}")
        print(f"  返回语句: {analysis['total_returns']} 个，需要更新: {analysis['needs_update']} 个")
        print()
    
    print("=" * 80)
    print(f"总计: {total_files} 个文件")
    print(f"已完成: {completed} 个 ({completed/total_files*100:.1f}%)")
    print(f"待更新: {pending} 个 ({pending/total_files*100:.1f}%)")
    print("=" * 80)
    print()
    
    if pending_files:
        print("待更新文件详情:")
        print("=" * 80)
        for analysis in pending_files:
            print(f"\n📄 {analysis['file']}")
            print(f"   需要更新 {analysis['needs_update']} 个返回语句")
            
            if analysis['return_statements']:
                print("   示例返回语句:")
                for line_num, statement in analysis['return_statements'][:3]:  # 只显示前3个
                    print(f"     行 {line_num}: {statement[:60]}...")
    
    print()
    print("=" * 80)
    print("下一步操作:")
    print("=" * 80)
    print("1. 手动更新每个待更新的文件")
    print("2. 添加必要的导入:")
    for imp in REQUIRED_IMPORTS:
        print(f"   {imp}")
    print("3. 将所有 return 语句改为使用 success_response()")
    print("4. 将所有 HTTPException 改为使用 StatusCode 常量")
    print("5. 为每个路由函数添加 request: Request 参数")
    print("6. 测试每个更新的路由")
    print()


def generate_update_template(file_name: str):
    """为特定文件生成更新模板"""
    file_path = ROUTERS_DIR / file_name
    if not file_path.exists():
        print(f"错误: 文件 {file_name} 不存在")
        return
    
    analysis = analyze_router_file(file_path)
    
    print(f"更新模板 - {file_name}")
    print("=" * 80)
    print()
    print("1. 添加导入（在文件顶部）:")
    print()
    for imp in REQUIRED_IMPORTS:
        print(f"   {imp}")
    print()
    print("2. 需要更新的返回语句:")
    print()
    
    for line_num, statement in analysis['return_statements']:
        print(f"   行 {line_num}:")
        print(f"   旧代码: {statement}")
        print(f"   新代码: return success_response(data=..., trace_id=get_trace_id(request))")
        print()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 为特定文件生成模板
        generate_update_template(sys.argv[1])
    else:
        # 生成总体报告
        generate_report()

