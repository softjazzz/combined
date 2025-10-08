#!/usr/bin/env python3
"""
批量更新简单路由文件的响应格式

此脚本会自动更新以下简单路由文件：
- auth.py
- medical_records_alias.py
- tools.py
- tasks.py
- classification.py
- reports.py
"""

import re
from pathlib import Path

ROUTERS_DIR = Path(__file__).parent.parent / "app" / "routers"

# 简单的替换规则
REPLACEMENTS = {
    # 导入替换
    'from fastapi import APIRouter': 'from fastapi import APIRouter, Request',
    
    # 添加响应导入（在第一个 from ..core 或 from ..schemas 之前）
    'add_response_import': 'from ..core.response import success_response, error_response, get_trace_id, ErrorCode, StatusCode\n',
    
    # 返回语句替换模式
    'return {"message": "': 'return success_response(data={}, message="',
    'return {"success": True}': 'return success_response(data={}, message="操作成功", trace_id=get_trace_id(request))',
    'return {"success": True, "message": "': 'return success_response(data={}, message="',
    
    # HTTPException 替换
    'status_code=404': 'status_code=StatusCode.NOT_FOUND',
    'status_code=400': 'status_code=StatusCode.BAD_REQUEST',
    'status_code=401': 'status_code=StatusCode.UNAUTHORIZED',
    'status_code=403': 'status_code=StatusCode.FORBIDDEN',
    'status_code=500': 'status_code=StatusCode.INTERNAL_SERVER_ERROR',
}


def add_request_parameter(content: str) -> str:
    """为路由函数添加 request: Request 参数"""
    # 匹配路由装饰器后的函数定义
    pattern = r'(@router\.(get|post|put|delete|patch)\([^)]+\)\s*\n\s*async def \w+\()'
    
    def replacer(match):
        func_def = match.group(0)
        if 'request: Request' not in func_def:
            # 在函数参数列表开始处添加 request: Request
            return func_def.rstrip('(') + '\n    request: Request,'
        return func_def
    
    return re.sub(pattern, replacer, content)


def update_file(file_path: Path) -> bool:
    """更新单个文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 1. 添加 Request 导入
        if 'from fastapi import' in content and 'Request' not in content:
            content = content.replace(
                'from fastapi import APIRouter',
                'from fastapi import APIRouter, Request'
            )
        
        # 2. 添加响应辅助函数导入
        if 'from ..core.response import' not in content:
            # 在第一个 from ..core 或 from ..schemas 之前添加
            lines = content.split('\n')
            insert_index = -1
            for i, line in enumerate(lines):
                if line.startswith('from ..core') or line.startswith('from ..schemas') or line.startswith('from ..services'):
                    insert_index = i
                    break
            
            if insert_index > 0:
                lines.insert(insert_index, 'from ..core.response import success_response, error_response, get_trace_id, ErrorCode, StatusCode')
                content = '\n'.join(lines)
        
        # 3. 添加 request: Request 参数
        content = add_request_parameter(content)
        
        # 4. 替换 HTTPException 状态码
        for old, new in REPLACEMENTS.items():
            if old.startswith('status_code='):
                content = content.replace(old, new)
        
        # 5. 简单的返回语句替换
        # return {"message": "xxx"} -> return success_response(data={}, message="xxx", trace_id=get_trace_id(request))
        content = re.sub(
            r'return \{"message": "([^"]+)"\}',
            r'return success_response(data={}, message="\1", trace_id=get_trace_id(request))',
            content
        )
        
        # return {"success": True} -> return success_response(...)
        content = content.replace(
            'return {"success": True}',
            'return success_response(data={}, message="操作成功", trace_id=get_trace_id(request))'
        )
        
        # 如果内容有变化，写回文件
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ 已更新: {file_path.name}")
            return True
        else:
            print(f"⏭️  无需更新: {file_path.name}")
            return False
            
    except Exception as e:
        print(f"❌ 更新失败 {file_path.name}: {e}")
        return False


def main():
    """主函数"""
    files_to_update = [
        "auth.py",
        "medical_records_alias.py",
        "tools.py",
        "tasks.py",
        "classification.py",
        "reports.py",
    ]
    
    print("=" * 80)
    print("批量更新简单路由文件")
    print("=" * 80)
    print()
    
    updated_count = 0
    for filename in files_to_update:
        file_path = ROUTERS_DIR / filename
        if file_path.exists():
            if update_file(file_path):
                updated_count += 1
        else:
            print(f"⚠️  文件不存在: {filename}")
    
    print()
    print("=" * 80)
    print(f"完成！已更新 {updated_count}/{len(files_to_update)} 个文件")
    print("=" * 80)
    print()
    print("注意：此脚本只进行基本的自动替换。")
    print("请手动检查每个文件，确保：")
    print("1. 所有路由函数都有 request: Request 参数")
    print("2. 所有返回语句都使用 success_response()")
    print("3. 所有错误都使用 StatusCode 常量")
    print("4. 运行 Python 语法检查")
    print()


if __name__ == "__main__":
    main()

