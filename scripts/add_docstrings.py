#!/usr/bin/env python3
"""
自动添加 docstring 脚本

功能:
- 为缺少 docstring 的函数和类添加模板
- 支持 Google 风格的 docstring
- 生成参数、返回值说明模板

使用方法:
    python scripts/add_docstrings.py
"""

import os
import ast
import astor
from pathlib import Path
from typing import List


def generate_function_docstring(node: ast.FunctionDef) -> str:
    """
    生成函数的 docstring 模板

    Args:
        node: 函数 AST 节点

    Returns:
        str: docstring 模板
    """
    lines = [f'    """']

    # 添加简短描述（占位符）
    lines.append(f"    {node.name} 函数")
    lines.append("    ")

    # 添加参数说明
    args = node.args.args
    if args:
        # 跳过 self 和 cls
        filtered_args = [arg for arg in args if arg.arg not in ['self', 'cls']]
        if filtered_args:
            lines.append("    Args:")
            for arg in filtered_args:
                arg_type = "类型待定"
                if arg.annotation:
                    arg_type = astor.to_source(arg.annotation).strip()
                lines.append(f"        {arg.arg}: {arg_type} - 参数说明")

    # 添加返回值说明
    if node.returns:
        lines.append("    ")
        lines.append("    Returns:")
        return_type = astor.to_source(node.returns).strip()
        lines.append(f"        {return_type}: 返回值说明")

    lines.append('    """')

    return '\n'.join(lines)


def generate_class_docstring(node: ast.ClassDef) -> str:
    """
    生成类的 docstring 模板

    Args:
        node: 类 AST 节点

    Returns:
        str: docstring 模板
    """
    return f'''    """
    {node.name} 类

    该类用于...（待补充）

    Attributes:
        待补充

    Example:
        >>> obj = {node.name}()
        >>> # 使用示例
    """'''


def add_docstrings_to_file(filepath: Path, dry_run: bool = False) -> bool:
    """
    为文件中缺少 docstring 的函数和类添加模板

    Args:
        filepath: 文件路径
        dry_run: 是否为演习模式（不实际修改文件）

    Returns:
        bool: 是否有修改
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content, filename=str(filepath))
        modified = False

        # 注意：这个脚本只生成模板，实际添加 docstring 需要手动编辑或使用更复杂的 AST 重写
        # 这里我们只打印需要添加 docstring 的位置

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                # 检查是否有 docstring
                has_docstring = (
                    node.body and
                    isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant) and
                    isinstance(node.body[0].value.value, str)
                )

                if not has_docstring:
                    # 跳过私有和测试函数/类
                    if node.name.startswith('_') or node.name.startswith('test_'):
                        continue

                    modified = True
                    if isinstance(node, ast.FunctionDef):
                        docstring = generate_function_docstring(node)
                        print(f"\n{filepath}:{node.lineno}")
                        print(f"函数: {node.name}")
                        print("建议的 docstring:")
                        print(docstring)
                    else:
                        docstring = generate_class_docstring(node)
                        print(f"\n{filepath}:{node.lineno}")
                        print(f"类: {node.name}")
                        print("建议的 docstring:")
                        print(docstring)

        return modified

    except Exception as e:
        print(f"处理文件失败 {filepath}: {e}")
        return False


def main():
    """主函数"""
    # 获取项目根目录
    script_dir = Path(__file__).parent
    root_dir = script_dir.parent

    # 分析后端代码
    backend_dir = root_dir / "apps" / "medqc-web" / "backend" / "app"

    if not backend_dir.exists():
        print(f"❌ 错误: 目录不存在: {backend_dir}")
        return

    print("=" * 80)
    print("自动生成 Docstring 模板")
    print("=" * 80)
    print()
    print(f"📁 分析目录: {backend_dir}")
    print()

    # 重点文件列表
    priority_files = [
        backend_dir / "services" / "record_service.py",
        backend_dir / "services" / "qc_service.py",
        backend_dir / "services" / "records_ingest_service.py",
        backend_dir / "services" / "sichuan_qc_service.py",
        backend_dir / "services" / "auth_service.py",
    ]

    total_modified = 0

    for filepath in priority_files:
        if filepath.exists():
            modified = add_docstrings_to_file(filepath, dry_run=True)
            if modified:
                total_modified += 1

    print()
    print("=" * 80)
    print(f"📊 发现 {total_modified} 个文件需要添加 docstring")
    print("=" * 80)
    print()
    print("💡 提示: 以上是自动生成的模板，请手动编辑并完善内容")


if __name__ == "__main__":
    main()
