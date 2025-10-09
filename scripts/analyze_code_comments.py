#!/usr/bin/env python3
"""
代码注释分析脚本

功能:
- 分析 Python 文件中的注释覆盖率
- 识别缺少 docstring 的函数和类
- 识别复杂逻辑（需要注释）
- 生成详细的分析报告

使用方法:
    python scripts/analyze_code_comments.py
"""

import os
import ast
import re
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict


class CodeAnalyzer(ast.NodeVisitor):
    """代码分析器"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.functions_without_docstring = []
        self.classes_without_docstring = []
        self.complex_functions = []
        self.total_functions = 0
        self.total_classes = 0
        self.functions_with_docstring = 0
        self.classes_with_docstring = 0

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """访问函数定义"""
        self.total_functions += 1

        # 检查是否有 docstring
        has_docstring = (
            node.body and
            isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, ast.Constant) and
            isinstance(node.body[0].value.value, str)
        )

        if has_docstring:
            self.functions_with_docstring += 1
        else:
            # 跳过私有函数和测试函数（可选）
            if not node.name.startswith('_') and not node.name.startswith('test_'):
                self.functions_without_docstring.append({
                    'name': node.name,
                    'line': node.lineno,
                    'args': len(node.args.args)
                })

        # 检查复杂度（简单估算：行数）
        if len(node.body) > 20:  # 函数体超过 20 行
            self.complex_functions.append({
                'name': node.name,
                'line': node.lineno,
                'lines': len(node.body)
            })

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """访问类定义"""
        self.total_classes += 1

        # 检查是否有 docstring
        has_docstring = (
            node.body and
            isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, ast.Constant) and
            isinstance(node.body[0].value.value, str)
        )

        if has_docstring:
            self.classes_with_docstring += 1
        else:
            if not node.name.startswith('_'):
                self.classes_without_docstring.append({
                    'name': node.name,
                    'line': node.lineno
                })

        self.generic_visit(node)


def analyze_file(filepath: Path) -> Dict:
    """
    分析单个文件

    Args:
        filepath: 文件路径

    Returns:
        分析结果
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析 AST
        tree = ast.parse(content, filename=str(filepath))

        # 分析代码
        analyzer = CodeAnalyzer(str(filepath))
        analyzer.visit(tree)

        # 计算注释覆盖率
        func_coverage = 0
        if analyzer.total_functions > 0:
            func_coverage = (analyzer.functions_with_docstring / analyzer.total_functions) * 100

        class_coverage = 0
        if analyzer.total_classes > 0:
            class_coverage = (analyzer.classes_with_docstring / analyzer.total_classes) * 100

        return {
            'filepath': str(filepath),
            'total_functions': analyzer.total_functions,
            'functions_with_docstring': analyzer.functions_with_docstring,
            'functions_without_docstring': analyzer.functions_without_docstring,
            'total_classes': analyzer.total_classes,
            'classes_with_docstring': analyzer.classes_with_docstring,
            'classes_without_docstring': analyzer.classes_without_docstring,
            'complex_functions': analyzer.complex_functions,
            'function_coverage': func_coverage,
            'class_coverage': class_coverage,
        }

    except Exception as e:
        return None


def analyze_directory(directory: Path) -> List[Dict]:
    """
    分析目录下的所有 Python 文件

    Args:
        directory: 目录路径

    Returns:
        分析结果列表
    """
    results = []

    # 查找所有 Python 文件
    for filepath in directory.rglob("*.py"):
        # 跳过虚拟环境和测试文件
        if 'venv' in str(filepath) or '__pycache__' in str(filepath):
            continue

        result = analyze_file(filepath)
        if result:
            results.append(result)

    return results


def generate_report(results: List[Dict]):
    """
    生成分析报告

    Args:
        results: 分析结果列表
    """
    print("=" * 80)
    print("代码注释分析报告")
    print("=" * 80)
    print()

    # 统计总览
    total_files = len(results)
    total_functions = sum(r['total_functions'] for r in results)
    total_classes = sum(r['total_classes'] for r in results)
    functions_with_docstring = sum(r['functions_with_docstring'] for r in results)
    classes_with_docstring = sum(r['classes_with_docstring'] for r in results)

    overall_func_coverage = 0
    if total_functions > 0:
        overall_func_coverage = (functions_with_docstring / total_functions) * 100

    overall_class_coverage = 0
    if total_classes > 0:
        overall_class_coverage = (classes_with_docstring / total_classes) * 100

    print(f"📁 扫描文件数: {total_files}")
    print(f"📝 总函数数: {total_functions}")
    print(f"📝 总类数: {total_classes}")
    print(f"✅ 有 docstring 的函数: {functions_with_docstring} ({overall_func_coverage:.1f}%)")
    print(f"✅ 有 docstring 的类: {classes_with_docstring} ({overall_class_coverage:.1f}%)")
    print()

    # 找出注释覆盖率最低的文件
    print("=" * 80)
    print("📊 注释覆盖率最低的文件（Top 10）")
    print("=" * 80)

    # 按函数注释覆盖率排序
    sorted_results = sorted(
        [r for r in results if r['total_functions'] > 0],
        key=lambda x: x['function_coverage']
    )[:10]

    for i, result in enumerate(sorted_results, 1):
        filepath = Path(result['filepath']).relative_to(Path.cwd())
        print(f"{i}. {filepath}")
        print(f"   函数覆盖率: {result['function_coverage']:.1f}%")
        print(f"   类覆盖率: {result['class_coverage']:.1f}%")
        print(f"   缺少 docstring 的函数: {len(result['functions_without_docstring'])}")
        print()

    # 列出所有缺少 docstring 的函数
    print("=" * 80)
    print("❌ 缺少 docstring 的函数（按文件分组）")
    print("=" * 80)

    for result in sorted_results[:5]:  # 只显示前 5 个文件
        if result['functions_without_docstring']:
            filepath = Path(result['filepath']).relative_to(Path.cwd())
            print(f"\n📄 {filepath}")
            for func in result['functions_without_docstring'][:5]:  # 每个文件只显示前 5 个
                print(f"   - {func['name']} (行 {func['line']}, {func['args']} 个参数)")

    print()

    # 列出复杂函数
    print("=" * 80)
    print("⚠️  复杂函数（需要详细注释）")
    print("=" * 80)

    complex_funcs = []
    for result in results:
        for func in result['complex_functions']:
            complex_funcs.append({
                'filepath': result['filepath'],
                'name': func['name'],
                'line': func['line'],
                'lines': func['lines']
            })

    # 按行数排序
    complex_funcs.sort(key=lambda x: x['lines'], reverse=True)

    for i, func in enumerate(complex_funcs[:10], 1):
        filepath = Path(func['filepath']).relative_to(Path.cwd())
        print(f"{i}. {func['name']} ({func['lines']} 行)")
        print(f"   文件: {filepath}:{func['line']}")
        print()

    # 建议
    print("=" * 80)
    print("💡 建议")
    print("=" * 80)
    print()

    if overall_func_coverage < 60:
        print("⚠️  函数注释覆盖率较低，建议：")
        print("   1. 为所有公开函数添加 docstring")
        print("   2. 使用 Google 或 NumPy 风格的 docstring")
        print("   3. 说明参数、返回值和异常")
        print()

    if overall_class_coverage < 60:
        print("⚠️  类注释覆盖率较低，建议：")
        print("   1. 为所有公开类添加 docstring")
        print("   2. 说明类的用途和主要方法")
        print()

    if complex_funcs:
        print("⚠️  发现复杂函数，建议：")
        print("   1. 添加详细的行内注释")
        print("   2. 考虑重构为多个小函数")
        print("   3. 添加算法说明和时间复杂度")
        print()

    print("=" * 80)
    print("🎉 分析完成！")
    print("=" * 80)


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

    print(f"📁 分析目录: {backend_dir}")
    print()

    # 分析代码
    results = analyze_directory(backend_dir)

    # 生成报告
    generate_report(results)


if __name__ == "__main__":
    main()
