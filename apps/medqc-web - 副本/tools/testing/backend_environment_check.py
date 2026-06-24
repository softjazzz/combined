#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
后端开发环境检查脚本
验证 Agent B 开发环境是否就绪
"""

import os
import sys
import subprocess
import importlib
import requests
from pathlib import Path
from datetime import datetime
import json

class BackendEnvironmentChecker:
    """后端环境检查器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.backend_root = self.project_root / "production_system"
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "overall_status": "unknown"
        }
        
        print("🔧 后端开发环境检查")
        print(f"📁 项目根目录: {self.project_root}")
        print(f"🔧 后端目录: {self.backend_root}")
        print("=" * 60)

    def check_python_environment(self):
        """检查 Python 环境"""
        print("\n🐍 Python 环境检查")
        
        result = {
            "status": "success",
            "details": {},
            "issues": []
        }
        
        # 检查 Python 版本
        python_version = sys.version_info
        if python_version >= (3, 10):
            result["details"]["python_version"] = f"{python_version.major}.{python_version.minor}.{python_version.micro}"
            print(f"  ✅ Python 版本: {result['details']['python_version']}")
        else:
            result["issues"].append(f"Python 版本过低: {python_version.major}.{python_version.minor}")
            print(f"  ❌ Python 版本过低: {python_version.major}.{python_version.minor}")
        
        # 检查 pip
        try:
            import pip
            result["details"]["pip_available"] = True
            print("  ✅ pip 可用")
        except ImportError:
            result["issues"].append("pip 不可用")
            print("  ❌ pip 不可用")
        
        if result["issues"]:
            result["status"] = "error"
        
        return result

    def check_required_packages(self):
        """检查必需的 Python 包"""
        print("\n📦 Python 包检查")
        
        result = {
            "status": "success",
            "installed": {},
            "missing": [],
            "issues": []
        }
        
        required_packages = {
            "fastapi": "0.100.0",
            "uvicorn": "0.20.0",
            "pydantic": "2.0.0",
            "supabase": "1.0.0",
            "bcrypt": "4.0.0",
            "pyjwt": "2.8.0",
            "python-multipart": "0.0.6",
            "python-dotenv": "1.0.0",
            "asyncpg": "0.28.0",
            "httpx": "0.24.0"
        }
        
        for package, min_version in required_packages.items():
            try:
                module = importlib.import_module(package.replace("-", "_"))
                version = getattr(module, "__version__", "unknown")
                result["installed"][package] = version
                print(f"  ✅ {package}: {version}")
            except ImportError:
                result["missing"].append(package)
                print(f"  ❌ {package}: 未安装")
        
        if result["missing"]:
            result["status"] = "error"
            result["issues"] = [f"缺少包: {', '.join(result['missing'])}"]
        
        return result

    def check_environment_variables(self):
        """检查环境变量"""
        print("\n⚙️ 环境变量检查")
        
        result = {
            "status": "success",
            "configured": {},
            "missing": [],
            "issues": []
        }
        
        required_env_vars = {
            "VITE_SUPABASE_URL": "Supabase 项目 URL",
            "VITE_SUPABASE_ANON_KEY": "Supabase 匿名密钥"
        }
        
        optional_env_vars = {
            "JWT_SECRET_KEY": "JWT 密钥",
            "OPENAI_API_KEY": "OpenAI API 密钥"
        }
        
        # 检查必需的环境变量
        for var, desc in required_env_vars.items():
            value = os.getenv(var)
            if value:
                # 只显示前几位，保护敏感信息
                masked_value = value[:10] + "..." if len(value) > 10 else value
                result["configured"][var] = masked_value
                print(f"  ✅ {var}: {masked_value}")
            else:
                result["missing"].append(var)
                print(f"  ❌ {var}: 未配置")
        
        # 检查可选的环境变量
        for var, desc in optional_env_vars.items():
            value = os.getenv(var)
            if value:
                masked_value = value[:10] + "..." if len(value) > 10 else value
                result["configured"][var] = masked_value
                print(f"  ✅ {var}: {masked_value}")
            else:
                print(f"  ⚠️  {var}: 未配置（可选）")
        
        if result["missing"]:
            result["status"] = "error"
            result["issues"] = [f"缺少环境变量: {', '.join(result['missing'])}"]
        
        return result

    def check_backend_structure(self):
        """检查后端项目结构"""
        print("\n🏗️ 后端项目结构检查")
        
        result = {
            "status": "success",
            "directories": {},
            "files": {},
            "issues": []
        }
        
        # 检查目录结构
        required_dirs = [
            "api",
            "core", 
            "services",
            "models",
            "utils",
            "middleware"
        ]
        
        for dir_name in required_dirs:
            dir_path = self.backend_root / dir_name
            if dir_path.exists():
                file_count = len([f for f in dir_path.rglob("*.py") if f.is_file()])
                result["directories"][dir_name] = {
                    "exists": True,
                    "py_files": file_count
                }
                print(f"  ✅ {dir_name}/: {file_count} 个 Python 文件")
            else:
                result["directories"][dir_name] = {"exists": False}
                result["issues"].append(f"{dir_name}/ 目录不存在")
                print(f"  ❌ {dir_name}/ 目录不存在")
        
        # 检查关键文件
        required_files = [
            "main.py",
            "requirements.txt",
            "__init__.py"
        ]
        
        for file_name in required_files:
            file_path = self.backend_root / file_name
            if file_path.exists():
                file_size = file_path.stat().st_size
                result["files"][file_name] = {
                    "exists": True,
                    "size": file_size
                }
                print(f"  ✅ {file_name}: {file_size} bytes")
            else:
                result["files"][file_name] = {"exists": False}
                if file_name in ["main.py", "requirements.txt"]:
                    result["issues"].append(f"{file_name} 文件不存在")
                    print(f"  ❌ {file_name} 不存在")
                else:
                    print(f"  ⚠️  {file_name} 不存在")
        
        if result["issues"]:
            result["status"] = "error"
        
        return result

    def check_database_connection(self):
        """检查数据库连接"""
        print("\n🗄️ 数据库连接检查")
        
        result = {
            "status": "unknown",
            "connection": False,
            "tables": [],
            "issues": []
        }
        
        try:
            # 检查 Supabase 连接
            supabase_url = os.getenv('VITE_SUPABASE_URL')
            supabase_key = os.getenv('VITE_SUPABASE_ANON_KEY')
            
            if not supabase_url or not supabase_key:
                result["issues"].append("Supabase 配置缺失")
                result["status"] = "error"
                print("  ❌ Supabase 配置缺失")
                return result
            
            # 测试连接
            headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{supabase_url}/rest/v1/user_profiles?select=count",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result["connection"] = True
                result["status"] = "success"
                print("  ✅ Supabase 连接成功")
                
                # 检查核心表
                core_tables = ["user_profiles", "departments", "medical_records", "qc_rules"]
                for table in core_tables:
                    try:
                        table_response = requests.get(
                            f"{supabase_url}/rest/v1/{table}?select=*&limit=0",
                            headers=headers,
                            timeout=5
                        )
                        if table_response.status_code == 200:
                            result["tables"].append(table)
                            print(f"    ✅ 表 {table} 可访问")
                        else:
                            print(f"    ❌ 表 {table} 无法访问")
                    except Exception as e:
                        print(f"    ❌ 检查表 {table} 时出错: {e}")
            else:
                result["issues"].append(f"连接失败: HTTP {response.status_code}")
                result["status"] = "error"
                print(f"  ❌ Supabase 连接失败: HTTP {response.status_code}")
                
        except Exception as e:
            result["issues"].append(f"连接异常: {str(e)}")
            result["status"] = "error"
            print(f"  ❌ 数据库连接异常: {e}")
        
        return result

    def check_api_server(self):
        """检查 API 服务器"""
        print("\n🌐 API 服务器检查")
        
        result = {
            "status": "unknown",
            "server_running": False,
            "endpoints": {},
            "issues": []
        }
        
        try:
            # 检查服务器是否运行
            response = requests.get("http://localhost:8001/", timeout=5)
            
            if response.status_code == 200:
                result["server_running"] = True
                print("  ✅ API 服务器运行中")
                
                # 检查关键端点
                endpoints = {
                    "/docs": "API 文档",
                    "/health": "健康检查",
                    "/api/auth/login": "登录接口"
                }
                
                for endpoint, desc in endpoints.items():
                    try:
                        endpoint_response = requests.get(f"http://localhost:8001{endpoint}", timeout=3)
                        result["endpoints"][endpoint] = {
                            "status_code": endpoint_response.status_code,
                            "accessible": endpoint_response.status_code < 500
                        }
                        
                        if endpoint_response.status_code < 500:
                            print(f"    ✅ {endpoint} ({desc}): HTTP {endpoint_response.status_code}")
                        else:
                            print(f"    ❌ {endpoint} ({desc}): HTTP {endpoint_response.status_code}")
                    except Exception as e:
                        result["endpoints"][endpoint] = {"error": str(e)}
                        print(f"    ❌ {endpoint} ({desc}): {e}")
                
                result["status"] = "success"
            else:
                result["issues"].append(f"服务器响应异常: HTTP {response.status_code}")
                result["status"] = "warning"
                print(f"  ⚠️  API 服务器响应异常: HTTP {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            result["issues"].append("API 服务器未运行")
            result["status"] = "warning"
            print("  ⚠️  API 服务器未运行（这是正常的，如果你还没启动服务器）")
        except Exception as e:
            result["issues"].append(f"检查服务器时出错: {str(e)}")
            result["status"] = "error"
            print(f"  ❌ 检查服务器时出错: {e}")
        
        return result

    def generate_summary(self):
        """生成检查总结"""
        print("\n" + "=" * 60)
        print("📊 后端环境检查总结")
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
                for issue in issues[:2]:  # 只显示前2个问题
                    print(f"    - {issue}")
                if len(issues) > 2:
                    print(f"    - ... 还有 {len(issues) - 2} 个问题")
        
        # 计算总体状态
        if status_counts["error"] > 0:
            overall_status = "error"
            status_emoji = "❌"
            message = "环境存在严重问题，需要修复后才能开始开发"
        elif status_counts["warning"] > 0:
            overall_status = "warning"
            status_emoji = "⚠️"
            message = "环境基本就绪，但存在一些警告项"
        else:
            overall_status = "success"
            status_emoji = "✅"
            message = "恭喜！后端开发环境完全就绪！"
        
        self.results["overall_status"] = overall_status
        
        print(f"\n🎯 总体状态: {status_emoji} {overall_status.upper()}")
        print(f"📈 检查统计: {status_counts['success']} 成功, {status_counts['warning']} 警告, {status_counts['error']} 错误")
        print(f"📋 问题总数: {total_issues}")
        print(f"\n💬 {message}")
        
        return overall_status

    def run_check(self):
        """运行完整检查"""
        print("🚀 开始后端开发环境检查\n")
        
        # 执行各项检查
        self.results["checks"]["Python环境"] = self.check_python_environment()
        self.results["checks"]["Python包"] = self.check_required_packages()
        self.results["checks"]["环境变量"] = self.check_environment_variables()
        self.results["checks"]["项目结构"] = self.check_backend_structure()
        self.results["checks"]["数据库连接"] = self.check_database_connection()
        self.results["checks"]["API服务器"] = self.check_api_server()
        
        # 生成总结
        overall_status = self.generate_summary()
        
        # 保存结果
        try:
            reports_dir = self.project_root / "reports"
            reports_dir.mkdir(exist_ok=True)
            
            report_file = reports_dir / f"backend_env_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            
            print(f"\n📄 详细报告已保存: {report_file}")
        except Exception as e:
            print(f"\n⚠️  保存报告失败: {e}")
        
        return self.results

if __name__ == "__main__":
    checker = BackendEnvironmentChecker()
    results = checker.run_check()
