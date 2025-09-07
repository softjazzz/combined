#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医疗质控系统简化集成验证脚本
不依赖外部库，仅验证文件结构和基本配置
"""

import os
import json
from pathlib import Path
from datetime import datetime

class SimpleIntegrationChecker:
    """简化集成检查器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "overall_status": "unknown",
            "summary": {}
        }
        
        print("🔍 医疗质控系统简化集成验证")
        print(f"📁 项目根目录: {self.project_root}")
        print("=" * 60)

    def check_database_structure(self):
        """检查数据库文件结构"""
        print("\n📊 1. 数据库文件结构检查")
        
        result = {
            "status": "success",
            "details": {},
            "issues": []
        }
        
        # 检查数据库目录结构
        db_base = self.project_root / "database"
        if not db_base.exists():
            result["issues"].append("database/ 目录不存在")
            result["status"] = "error"
            print("  ❌ database/ 目录不存在")
            return result
        
        # 检查子目录
        subdirs = {
            "setup": "数据库初始化脚本",
            "fixes": "数据库修复脚本", 
            "migrations": "数据库迁移文件",
            "schemas": "数据库架构文件"
        }
        
        for subdir, desc in subdirs.items():
            subdir_path = db_base / subdir
            if subdir_path.exists():
                sql_files = list(subdir_path.glob("*.sql"))
                result["details"][subdir] = {
                    "exists": True,
                    "file_count": len(sql_files),
                    "files": [f.name for f in sql_files]
                }
                print(f"  ✅ {subdir}/ ({desc}): {len(sql_files)} 个文件")
            else:
                result["details"][subdir] = {"exists": False}
                if subdir in ["setup", "fixes"]:  # 关键目录
                    result["issues"].append(f"{subdir}/ 目录不存在")
                    print(f"  ❌ {subdir}/ 目录不存在")
                else:
                    print(f"  ⚠️  {subdir}/ 目录不存在（可选）")
        
        # 检查关键脚本
        key_scripts = [
            ("setup/database_init_complete.sql", "主要表结构初始化"),
            ("setup/verify_database.sql", "数据库验证脚本"),
            ("fixes/database_simple_fix.sql", "简单修复脚本")
        ]
        
        for script_path, desc in key_scripts:
            full_path = db_base / script_path
            if full_path.exists():
                print(f"  ✅ {script_path} ({desc})")
            else:
                result["issues"].append(f"缺少关键脚本: {script_path}")
                print(f"  ❌ {script_path} 不存在")
        
        if result["issues"]:
            result["status"] = "error" if any("❌" in str(issue) for issue in result["issues"]) else "warning"
        
        return result

    def check_project_structure(self):
        """检查项目整体结构"""
        print("\n🏗️ 2. 项目结构检查")
        
        result = {
            "status": "success",
            "directories": {},
            "core_files": {},
            "issues": []
        }
        
        # 检查核心目录
        core_dirs = {
            "src": "前端源码",
            "production_system": "后端系统",
            "docs": "项目文档",
            "tools": "工具脚本",
            "config": "配置文件",
            "assets": "静态资源"
        }
        
        for dir_name, desc in core_dirs.items():
            dir_path = self.project_root / dir_name
            if dir_path.exists():
                # 计算子文件数量
                try:
                    file_count = len([f for f in dir_path.rglob("*") if f.is_file()])
                    result["directories"][dir_name] = {
                        "exists": True,
                        "file_count": file_count,
                        "description": desc
                    }
                    print(f"  ✅ {dir_name}/ ({desc}): {file_count} 个文件")
                except Exception as e:
                    result["directories"][dir_name] = {
                        "exists": True,
                        "error": str(e)
                    }
                    print(f"  ⚠️  {dir_name}/ 存在但无法统计文件: {e}")
            else:
                result["directories"][dir_name] = {"exists": False}
                if dir_name in ["src", "production_system"]:  # 关键目录
                    result["issues"].append(f"{dir_name}/ 目录不存在")
                    print(f"  ❌ {dir_name}/ 目录不存在")
                else:
                    print(f"  ⚠️  {dir_name}/ 目录不存在")
        
        # 检查核心文件
        core_files = {
            "package.json": "前端依赖配置",
            "README.md": "项目说明文档",
            "PROJECT_STRUCTURE.md": "项目结构说明",
            ".env": "环境变量配置"
        }
        
        for file_name, desc in core_files.items():
            file_path = self.project_root / file_name
            if file_path.exists():
                try:
                    file_size = file_path.stat().st_size
                    result["core_files"][file_name] = {
                        "exists": True,
                        "size": file_size,
                        "description": desc
                    }
                    print(f"  ✅ {file_name} ({desc}): {file_size} bytes")
                except Exception as e:
                    result["core_files"][file_name] = {
                        "exists": True,
                        "error": str(e)
                    }
                    print(f"  ⚠️  {file_name} 存在但无法读取: {e}")
            else:
                result["core_files"][file_name] = {"exists": False}
                if file_name in ["package.json", "README.md"]:  # 关键文件
                    result["issues"].append(f"{file_name} 文件不存在")
                    print(f"  ❌ {file_name} 不存在")
                else:
                    print(f"  ⚠️  {file_name} 不存在")
        
        if result["issues"]:
            result["status"] = "error" if any("❌" in str(issue) for issue in result["issues"]) else "warning"
        
        return result

    def check_frontend_config(self):
        """检查前端配置"""
        print("\n🎨 3. 前端配置检查")
        
        result = {
            "status": "success",
            "package_json": {},
            "dependencies": {},
            "issues": []
        }
        
        # 检查 package.json
        package_path = self.project_root / "package.json"
        if package_path.exists():
            try:
                with open(package_path, 'r', encoding='utf-8') as f:
                    package_data = json.load(f)
                
                result["package_json"] = {
                    "name": package_data.get("name", "未知"),
                    "version": package_data.get("version", "未知"),
                    "scripts_count": len(package_data.get("scripts", {})),
                    "deps_count": len(package_data.get("dependencies", {})),
                    "dev_deps_count": len(package_data.get("devDependencies", {}))
                }
                
                print(f"  ✅ package.json 解析成功")
                print(f"    项目名称: {result['package_json']['name']}")
                print(f"    版本: {result['package_json']['version']}")
                print(f"    脚本数量: {result['package_json']['scripts_count']}")
                print(f"    依赖数量: {result['package_json']['deps_count']}")
                print(f"    开发依赖数量: {result['package_json']['dev_deps_count']}")
                
                # 检查关键依赖
                all_deps = {**package_data.get("dependencies", {}), **package_data.get("devDependencies", {})}
                key_deps = ["vue", "@supabase/supabase-js", "vite", "typescript"]
                
                for dep in key_deps:
                    if dep in all_deps:
                        result["dependencies"][dep] = all_deps[dep]
                        print(f"    ✅ {dep}: {all_deps[dep]}")
                    else:
                        result["issues"].append(f"缺少关键依赖: {dep}")
                        print(f"    ❌ 缺少依赖: {dep}")
                
            except json.JSONDecodeError as e:
                result["issues"].append(f"package.json 格式错误: {e}")
                print(f"  ❌ package.json 格式错误: {e}")
            except Exception as e:
                result["issues"].append(f"读取 package.json 失败: {e}")
                print(f"  ❌ 读取 package.json 失败: {e}")
        else:
            result["issues"].append("package.json 不存在")
            print("  ❌ package.json 不存在")
        
        # 检查前端源码结构
        src_path = self.project_root / "src"
        if src_path.exists():
            key_src_dirs = ["components", "views", "services", "stores", "types"]
            for dir_name in key_src_dirs:
                dir_path = src_path / dir_name
                if dir_path.exists():
                    file_count = len([f for f in dir_path.rglob("*") if f.is_file()])
                    print(f"  ✅ src/{dir_name}/: {file_count} 个文件")
                else:
                    print(f"  ⚠️  src/{dir_name}/ 不存在")
        
        if result["issues"]:
            result["status"] = "error"
        
        return result

    def check_backend_config(self):
        """检查后端配置"""
        print("\n🔧 4. 后端配置检查")
        
        result = {
            "status": "success",
            "structure": {},
            "issues": []
        }
        
        backend_path = self.project_root / "production_system"
        if not backend_path.exists():
            result["issues"].append("production_system/ 目录不存在")
            result["status"] = "error"
            print("  ❌ production_system/ 目录不存在")
            return result
        
        # 检查关键文件
        key_files = {
            "main.py": "主程序入口",
            "requirements.txt": "Python依赖配置",
            ".env": "环境变量配置"
        }
        
        for file_name, desc in key_files.items():
            file_path = backend_path / file_name
            if file_path.exists():
                file_size = file_path.stat().st_size
                result["structure"][file_name] = {
                    "exists": True,
                    "size": file_size
                }
                print(f"  ✅ {file_name} ({desc}): {file_size} bytes")
            else:
                result["structure"][file_name] = {"exists": False}
                if file_name in ["main.py", "requirements.txt"]:
                    result["issues"].append(f"{file_name} 不存在")
                    print(f"  ❌ {file_name} 不存在")
                else:
                    print(f"  ⚠️  {file_name} 不存在")
        
        # 检查目录结构
        key_dirs = ["api", "core", "services", "models"]
        for dir_name in key_dirs:
            dir_path = backend_path / dir_name
            if dir_path.exists():
                py_files = len(list(dir_path.glob("*.py")))
                result["structure"][f"{dir_name}_dir"] = {
                    "exists": True,
                    "py_files": py_files
                }
                print(f"  ✅ {dir_name}/: {py_files} 个 Python 文件")
            else:
                result["structure"][f"{dir_name}_dir"] = {"exists": False}
                print(f"  ⚠️  {dir_name}/ 目录不存在")
        
        if result["issues"]:
            result["status"] = "error"
        
        return result

    def generate_summary(self):
        """生成验证总结"""
        print("\n" + "=" * 60)
        print("📊 集成验证总结")
        print("=" * 60)
        
        # 收集所有检查结果
        checks = self.results["checks"]
        
        status_counts = {"success": 0, "warning": 0, "error": 0}
        total_issues = 0
        
        for check_name, check_result in checks.items():
            status = check_result.get("status", "unknown")
            if status in status_counts:
                status_counts[status] += 1
            
            issues = check_result.get("issues", [])
            total_issues += len(issues)
            
            status_emoji = {"success": "✅", "warning": "⚠️", "error": "❌"}.get(status, "❓")
            print(f"{status_emoji} {check_name}: {status.upper()}")
            
            if issues:
                for issue in issues[:3]:  # 只显示前3个问题
                    print(f"    - {issue}")
                if len(issues) > 3:
                    print(f"    - ... 还有 {len(issues) - 3} 个问题")
        
        # 计算总体状态
        if status_counts["error"] > 0:
            overall_status = "error"
            status_emoji = "❌"
            message = "系统存在严重问题，需要修复后才能正常使用"
        elif status_counts["warning"] > 0:
            overall_status = "warning"
            status_emoji = "⚠️"
            message = "系统基本可用，但存在一些警告项需要关注"
        else:
            overall_status = "success"
            status_emoji = "✅"
            message = "恭喜！系统集成验证通过！"
        
        self.results["overall_status"] = overall_status
        self.results["summary"] = {
            "total_checks": len(checks),
            "success_count": status_counts["success"],
            "warning_count": status_counts["warning"],
            "error_count": status_counts["error"],
            "total_issues": total_issues
        }
        
        print(f"\n🎯 总体状态: {status_emoji} {overall_status.upper()}")
        print(f"📈 检查统计: {status_counts['success']} 成功, {status_counts['warning']} 警告, {status_counts['error']} 错误")
        print(f"📋 问题总数: {total_issues}")
        print(f"\n💬 {message}")
        
        return overall_status

    def run_check(self):
        """运行完整检查"""
        print("🚀 开始医疗质控系统集成验证\n")
        
        # 执行各项检查
        self.results["checks"]["数据库结构"] = self.check_database_structure()
        self.results["checks"]["项目结构"] = self.check_project_structure()
        self.results["checks"]["前端配置"] = self.check_frontend_config()
        self.results["checks"]["后端配置"] = self.check_backend_config()
        
        # 生成总结
        overall_status = self.generate_summary()
        
        # 保存结果
        try:
            reports_dir = self.project_root / "reports"
            reports_dir.mkdir(exist_ok=True)
            
            report_file = reports_dir / f"integration_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            
            print(f"\n📄 详细报告已保存: {report_file}")
        except Exception as e:
            print(f"\n⚠️  保存报告失败: {e}")
        
        return self.results

if __name__ == "__main__":
    checker = SimpleIntegrationChecker()
    results = checker.run_check()
