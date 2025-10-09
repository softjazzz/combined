#!/usr/bin/env python3
"""
修复缺少 Request 导入的文件
"""

import os
import re
from pathlib import Path


def fix_request_import(file_path: Path) -> bool:
    """
    修复单个文件的 Request 导入
    
    Returns:
        bool: 是否进行了修改
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否使用了 Request 但没有导入
        if 'request: Request' in content or 'Request,' in content:
            # 检查是否已经导入了 Request
            if 'from fastapi import' in content and 'Request' not in content.split('from fastapi import')[1].split('\n')[0]:
                # 找到 fastapi 导入行
                lines = content.split('\n')
                modified = False
                
                for i, line in enumerate(lines):
                    if line.strip().startswith('from fastapi import'):
                        # 检查这一行是否已经包含 Request
                        if 'Request' not in line:
                            # 添加 Request 到导入列表
                            if line.endswith(')'):
                                # 多行导入
                                lines[i] = line.replace(')', ', Request)')
                            else:
                                # 单行导入
                                # 找到最后一个导入项
                                parts = line.split('import')
                                if len(parts) == 2:
                                    imports = parts[1].strip()
                                    lines[i] = f"from fastapi import {imports}, Request"
                            modified = True
                            break
                
                if modified:
                    # 写回文件
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(lines))
                    return True
        
        return False
    
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """主函数"""
    # 获取 routers 目录
    routers_dir = Path(__file__).parent.parent / 'app' / 'routers'
    
    if not routers_dir.exists():
        print(f"Routers directory not found: {routers_dir}")
        return
    
    print(f"Scanning {routers_dir}...")
    
    fixed_count = 0
    for py_file in routers_dir.glob('*.py'):
        if py_file.name == '__init__.py':
            continue
        
        if fix_request_import(py_file):
            print(f"✅ Fixed: {py_file.name}")
            fixed_count += 1
        else:
            print(f"⏭️  Skipped: {py_file.name}")
    
    print(f"\n✅ Fixed {fixed_count} files")


if __name__ == "__main__":
    main()

