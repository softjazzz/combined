#!/usr/bin/env python3
"""
SQL 注入安全审查脚本

检查代码库中可能存在的 SQL 注入风险
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple

# 危险模式列表
DANGEROUS_PATTERNS = [
    # 字符串拼接 SQL
    (r'f".*SELECT.*\{', 'f-string with SELECT and variable interpolation'),
    (r"f'.*SELECT.*\{", 'f-string with SELECT and variable interpolation'),
    (r'f".*INSERT.*\{', 'f-string with INSERT and variable interpolation'),
    (r"f'.*INSERT.*\{", 'f-string with INSERT and variable interpolation'),
    (r'f".*UPDATE.*\{', 'f-string with UPDATE and variable interpolation'),
    (r"f'.*UPDATE.*\{", 'f-string with UPDATE and variable interpolation'),
    (r'f".*DELETE.*\{', 'f-string with DELETE and variable interpolation'),
    (r"f'.*DELETE.*\{", 'f-string with DELETE and variable interpolation'),
    
    # 字符串拼接
    (r'"\s*\+\s*.*\s*\+\s*".*WHERE', 'String concatenation in WHERE clause'),
    (r"'\s*\+\s*.*\s*\+\s*'.*WHERE", 'String concatenation in WHERE clause'),
    (r'"\s*\+\s*.*\s*\+\s*".*SET', 'String concatenation in SET clause'),
    (r"'\s*\+\s*.*\s*\+\s*'.*SET", 'String concatenation in SET clause'),
    
    # .format() 方法
    (r'\.format\(.*\).*SELECT', '.format() with SELECT'),
    (r'\.format\(.*\).*INSERT', '.format() with INSERT'),
    (r'\.format\(.*\).*UPDATE', '.format() with UPDATE'),
    (r'\.format\(.*\).*DELETE', '.format() with DELETE'),
    
    # % 格式化
    (r'%\s*\(.*\).*SELECT', '% formatting with SELECT'),
    (r'%\s*\(.*\).*INSERT', '% formatting with INSERT'),
    (r'%\s*\(.*\).*UPDATE', '% formatting with UPDATE'),
    (r'%\s*\(.*\).*DELETE', '% formatting with DELETE'),
]

# 安全模式列表（白名单）
SAFE_PATTERNS = [
    r'\.eq\(',  # Supabase .eq() method
    r'\.neq\(',  # Supabase .neq() method
    r'\.gt\(',  # Supabase .gt() method
    r'\.gte\(',  # Supabase .gte() method
    r'\.lt\(',  # Supabase .lt() method
    r'\.lte\(',  # Supabase .lte() method
    r'\.like\(',  # Supabase .like() method
    r'\.ilike\(',  # Supabase .ilike() method
    r'\.in_\(',  # Supabase .in_() method
    r'\.filter\(',  # Supabase .filter() method
    r'\.match\(',  # Supabase .match() method
    r'execute\(select\(',  # SQLAlchemy select()
    r'execute\(insert\(',  # SQLAlchemy insert()
    r'execute\(update\(',  # SQLAlchemy update()
    r'execute\(delete\(',  # SQLAlchemy delete()
]


def is_safe_pattern(line: str) -> bool:
    """检查是否匹配安全模式"""
    for pattern in SAFE_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def scan_file(file_path: Path) -> List[Dict]:
    """扫描单个文件"""
    issues = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, 1):
            # 跳过注释
            if line.strip().startswith('#'):
                continue

            # 跳过字符串字面量（正则表达式模式定义等）
            if re.search(r'^\s*[\'"]\(r[\'"]', line):
                continue

            # 跳过日志消息（message=, print(, logger.）
            if re.search(r'(message\s*=|print\(|logger\.|logging\.)', line):
                continue

            # 跳过安全模式
            if is_safe_pattern(line):
                continue

            # 检查危险模式
            for pattern, description in DANGEROUS_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    # 额外检查：确保不是在字符串字面量中
                    if not re.search(r'[\'"].*' + pattern + r'.*[\'"]', line, re.IGNORECASE):
                        issues.append({
                            'file': str(file_path),
                            'line': line_num,
                            'code': line.strip(),
                            'pattern': description,
                            'severity': 'HIGH'
                        })

    except Exception as e:
        print(f"Error scanning {file_path}: {e}")

    return issues


def scan_directory(directory: Path, exclude_patterns: List[str] = None) -> List[Dict]:
    """扫描目录"""
    if exclude_patterns is None:
        exclude_patterns = [
            '__pycache__',
            '.venv',
            'venv',
            '.git',
            'node_modules',
            'test_',
            '_test.py',
        ]
    
    all_issues = []
    
    for py_file in directory.rglob('*.py'):
        # 检查是否应该排除
        should_exclude = False
        for pattern in exclude_patterns:
            if pattern in str(py_file):
                should_exclude = True
                break
        
        if should_exclude:
            continue
        
        issues = scan_file(py_file)
        all_issues.extend(issues)
    
    return all_issues


def generate_report(issues: List[Dict]) -> str:
    """生成报告"""
    report_lines = [
        "# SQL 注入安全审查报告",
        "",
        f"**扫描时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**发现问题数**: {len(issues)}",
        "",
    ]
    
    if not issues:
        report_lines.extend([
            "## ✅ 结果",
            "",
            "**未发现 SQL 注入风险！**",
            "",
            "所有数据库查询都使用了安全的方式：",
            "- Supabase 客户端方法（.eq(), .filter() 等）",
            "- SQLAlchemy ORM",
            "- 参数化查询",
            "",
        ])
    else:
        report_lines.extend([
            "## ⚠️ 发现的问题",
            "",
        ])
        
        # 按文件分组
        issues_by_file = {}
        for issue in issues:
            file_path = issue['file']
            if file_path not in issues_by_file:
                issues_by_file[file_path] = []
            issues_by_file[file_path].append(issue)
        
        for file_path, file_issues in sorted(issues_by_file.items()):
            report_lines.append(f"### {file_path}")
            report_lines.append("")
            
            for issue in file_issues:
                report_lines.extend([
                    f"**行 {issue['line']}** - {issue['severity']} - {issue['pattern']}",
                    "```python",
                    issue['code'],
                    "```",
                    "",
                ])
    
    report_lines.extend([
        "## 📋 安全建议",
        "",
        "### ✅ 推荐的安全做法",
        "",
        "1. **使用 Supabase 客户端方法**",
        "   ```python",
        "   # ✅ 安全",
        "   supabase.table('users').select('*').eq('name', user_input).execute()",
        "   ```",
        "",
        "2. **使用 SQLAlchemy ORM**",
        "   ```python",
        "   # ✅ 安全",
        "   query = select(User).where(User.name == user_input)",
        "   result = await db.execute(query)",
        "   ```",
        "",
        "3. **使用参数化查询**",
        "   ```python",
        "   # ✅ 安全",
        "   query = text('SELECT * FROM users WHERE name = :name')",
        "   result = await db.execute(query, {'name': user_input})",
        "   ```",
        "",
        "### ❌ 避免的危险做法",
        "",
        "1. **字符串拼接**",
        "   ```python",
        "   # ❌ 危险",
        "   query = f\"SELECT * FROM users WHERE name = '{user_input}'\"",
        "   ```",
        "",
        "2. **字符串格式化**",
        "   ```python",
        "   # ❌ 危险",
        "   query = \"SELECT * FROM users WHERE name = '{}'\".format(user_input)",
        "   ```",
        "",
        "3. **% 格式化**",
        "   ```python",
        "   # ❌ 危险",
        "   query = \"SELECT * FROM users WHERE name = '%s'\" % user_input",
        "   ```",
        "",
    ])
    
    return "\n".join(report_lines)


def main():
    """主函数"""
    print("🔍 开始 SQL 注入安全审查...\n")
    
    # 获取项目根目录
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent
    
    print(f"扫描目录: {backend_dir}\n")
    
    # 扫描代码
    issues = scan_directory(backend_dir)
    
    # 生成报告
    report = generate_report(issues)
    
    # 保存报告
    report_path = backend_dir / "SQL_INJECTION_AUDIT_REPORT.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ 审查完成！")
    print(f"📄 报告已保存到: {report_path}")
    print(f"🔍 发现问题数: {len(issues)}")
    
    if issues:
        print("\n⚠️ 发现潜在的 SQL 注入风险，请查看报告！")
        return 1
    else:
        print("\n✅ 未发现 SQL 注入风险！")
        return 0


if __name__ == "__main__":
    exit(main())

