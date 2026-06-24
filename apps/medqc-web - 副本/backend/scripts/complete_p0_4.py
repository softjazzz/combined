#!/usr/bin/env python3
"""
完成 P0-4 剩余工作的脚本

此脚本会更新所有剩余的路由文件，使其使用统一的响应格式。
"""

import re
from pathlib import Path
from typing import List, Tuple

ROUTERS_DIR = Path(__file__).parent.parent / "app" / "routers"

# 需要完成的文件
FILES_TO_COMPLETE = [
    "semantic_rules.py",
    "llm_configs.py",
    "qc_sichuan.py",
    "qc_llm_configs.py",
    "proxy.py",
    "medical_documents.py",
    "debug.py",
    "ingest.py",
]


def ensure_imports(content: str) -> str:
    """确保文件包含必要的导入"""
    has_request = "Request" in content and "from fastapi import" in content
    has_response = "from ..core.response import" in content
    
    lines = content.split('\n')
    
    # 添加 Request 导入
    if not has_request:
        for i, line in enumerate(lines):
            if line.startswith('from fastapi import'):
                if 'Request' not in line:
                    # 在导入列表中添加 Request
                    lines[i] = line.rstrip() + ', Request' if not line.endswith(',') else line.rstrip() + ' Request'
                break
    
    # 添加响应辅助函数导入
    if not has_response:
        insert_index = -1
        for i, line in enumerate(lines):
            if line.startswith('from ..core') or line.startswith('from ..schemas') or line.startswith('from ..services'):
                insert_index = i
                break
        
        if insert_index > 0:
            lines.insert(insert_index, 'from ..core.response import success_response, paginated_response, error_response, get_trace_id, ErrorCode, StatusCode')
    
    return '\n'.join(lines)


def add_request_param(content: str) -> str:
    """为路由函数添加 request: Request 参数"""
    # 匹配 @router.xxx 装饰器后的函数定义
    pattern = r'(@router\.(get|post|put|delete|patch)\([^)]+\)\s*\n\s*async def \w+)\('
    
    def replacer(match):
        func_start = match.group(0)
        if 'request: Request' not in func_start:
            # 在参数列表开始处添加 request: Request
            return func_start.rstrip('(') + '(\n    request: Request,'
        return func_start
    
    return re.sub(pattern, replacer, content)


def update_return_statements(content: str) -> str:
    """更新返回语句"""
    # 简单的字典返回 -> success_response
    # return {"success": True, ...} -> success_response(...)
    content = re.sub(
        r'return \{"success": True, "([^"]+)": ([^,}]+), "([^"]+)": ([^}]+)\}',
        r'return success_response(data={"\1": \2, "\3": \4}, trace_id=get_trace_id(request))',
        content
    )
    
    # return {"success": True} -> success_response(...)
    content = content.replace(
        'return {"success": True}',
        'return success_response(data={}, message="操作成功", trace_id=get_trace_id(request))'
    )
    
    # return {"message": "xxx"} -> success_response(...)
    content = re.sub(
        r'return \{"message": "([^"]+)"\}',
        r'return success_response(data={}, message="\1", trace_id=get_trace_id(request))',
        content
    )
    
    # return {"data": xxx} -> success_response(data=xxx, ...)
    content = re.sub(
        r'return \{"data": ([^}]+)\}',
        r'return success_response(data=\1, trace_id=get_trace_id(request))',
        content
    )
    
    return content


def update_http_exceptions(content: str) -> str:
    """更新 HTTPException 状态码"""
    replacements = {
        'status_code=404': 'status_code=StatusCode.NOT_FOUND',
        'status_code=400': 'status_code=StatusCode.BAD_REQUEST',
        'status_code=401': 'status_code=StatusCode.UNAUTHORIZED',
        'status_code=403': 'status_code=StatusCode.FORBIDDEN',
        'status_code=500': 'status_code=StatusCode.INTERNAL_SERVER_ERROR',
        'status_code=422': 'status_code=StatusCode.UNPROCESSABLE_ENTITY',
        'status_code=status.HTTP_404_NOT_FOUND': 'status_code=StatusCode.NOT_FOUND',
        'status_code=status.HTTP_400_BAD_REQUEST': 'status_code=StatusCode.BAD_REQUEST',
        'status_code=status.HTTP_401_UNAUTHORIZED': 'status_code=StatusCode.UNAUTHORIZED',
        'status_code=status.HTTP_403_FORBIDDEN': 'status_code=StatusCode.FORBIDDEN',
        'status_code=status.HTTP_500_INTERNAL_SERVER_ERROR': 'status_code=StatusCode.INTERNAL_SERVER_ERROR',
    }
    
    for old, new in replacements.items():
        content = content.replace(old, new)
    
    return content


def process_file(file_path: Path) -> Tuple[bool, str]:
    """处理单个文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        content = original_content
        
        # 1. 确保导入
        content = ensure_imports(content)
        
        # 2. 添加 request 参数
        content = add_request_param(content)
        
        # 3. 更新返回语句
        content = update_return_statements(content)
        
        # 4. 更新 HTTPException
        content = update_http_exceptions(content)
        
        # 如果有变化，写回文件
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, "已更新"
        else:
            return False, "无需更新"
    
    except Exception as e:
        return False, f"错误: {e}"


def main():
    """主函数"""
    print("=" * 80)
    print("完成 P0-4 剩余工作")
    print("=" * 80)
    print()
    
    results = []
    
    for filename in FILES_TO_COMPLETE:
        file_path = ROUTERS_DIR / filename
        if not file_path.exists():
            results.append((filename, False, "文件不存在"))
            continue
        
        updated, message = process_file(file_path)
        results.append((filename, updated, message))
        
        status = "✅" if updated else "⏭️"
        print(f"{status} {filename}: {message}")
    
    print()
    print("=" * 80)
    updated_count = sum(1 for _, updated, _ in results if updated)
    print(f"完成！已更新 {updated_count}/{len(FILES_TO_COMPLETE)} 个文件")
    print("=" * 80)
    print()
    print("注意：此脚本只进行基本的自动替换。")
    print("请手动检查每个文件，特别是复杂的返回语句。")
    print()


if __name__ == "__main__":
    main()

