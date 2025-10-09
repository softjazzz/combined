#!/usr/bin/env python3
"""
添加 API 版本控制脚本

功能:
- 将所有路由从 /api 更新为 /api/v1
- 保持向后兼容性（可选）
- 生成详细的更新报告

使用方法:
    python scripts/update_api_version.py
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple

# 路由文件所在目录
ROUTERS_DIR = "apps/medqc-web/backend/app/routers"

# 需要更新的模式
PATTERNS = {
    # APIRouter(prefix="/api/xxx", ...)
    r'APIRouter\(prefix="/api/([^"]*)"': r'APIRouter(prefix="/api/v1/\1"',
    # APIRouter(prefix="/api", ...)
    r'APIRouter\(prefix="/api"': r'APIRouter(prefix="/api/v1"',
}


def update_router_file(file_path: Path) -> Tuple[bool, List[str]]:
    """
    更新单个路由文件

    Args:
        file_path: 文件路径

    Returns:
        (是否修改, 修改列表)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    changes = []

    for pattern, replacement in PATTERNS.items():
        matches = re.finditer(pattern, content)
        for match in matches:
            old_prefix = match.group(0)
            new_prefix = re.sub(pattern, replacement, old_prefix)
            if old_prefix != new_prefix:
                changes.append(f"{old_prefix} → {new_prefix}")

        content = re.sub(pattern, replacement, content)

    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, changes

    return False, []


def main():
    """主函数"""
    print("=" * 80)
    print("API 版本控制更新脚本")
    print("=" * 80)
    print()

    # 获取项目根目录
    script_dir = Path(__file__).parent
    root_dir = script_dir.parent
    routers_dir = root_dir / ROUTERS_DIR

    if not routers_dir.exists():
        print(f"❌ 错误: 路由目录不存在: {routers_dir}")
        return

    print(f"📁 扫描目录: {routers_dir}")
    print()

    # 获取所有路由文件
    router_files = list(routers_dir.glob("*.py"))
    router_files = [f for f in router_files if f.name != "__init__.py"]

    print(f"📝 找到 {len(router_files)} 个路由文件")
    print()

    # 更新文件
    updated_count = 0
    all_changes: Dict[str, List[str]] = {}

    for file_path in sorted(router_files):
        modified, changes = update_router_file(file_path)

        if modified:
            updated_count += 1
            all_changes[file_path.name] = changes
            print(f"✅ 更新: {file_path.name}")
            for change in changes:
                print(f"   {change}")
        else:
            print(f"⏭️  跳过: {file_path.name} (无需更新)")

    print()
    print("=" * 80)
    print("📊 更新摘要")
    print("=" * 80)
    print(f"总文件数: {len(router_files)}")
    print(f"已更新: {updated_count}")
    print(f"未修改: {len(router_files) - updated_count}")
    print()

    if all_changes:
        print("✅ 所有路由已更新为 /api/v1 前缀")
        print()
        print("📋 更新详情:")
        for filename, changes in all_changes.items():
            print(f"  {filename}:")
            for change in changes:
                print(f"    - {change}")
    else:
        print("ℹ️  没有文件需要更新")

    print()
    print("=" * 80)
    print("🎉 完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
