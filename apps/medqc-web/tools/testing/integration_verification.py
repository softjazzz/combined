#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医疗质控系统集成验证脚本
验证系统各组件的集成状态和功能完整性
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime

# 尝试导入 requests，如果没有则使用 urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.parse
    HAS_REQUESTS = False

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

class IntegrationVerifier:
    """集成验证器"""
    
    def __init__(self):
        self.project_root = project_root
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "database": {},
            "frontend": {},
            "backend": {},
            "integration": {},
            "tools": {},
            "overall_status": "unknown"
        }
        
        # 从环境变量或配置文件读取配置
        self.supabase_url = os.getenv('VITE_SUPABASE_URL', 'https://dgsdkdbjpucyawnyfbdu.supabase.co')
        self.supabase_key = os.getenv('VITE_SUPABASE_ANON_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw')
        
        print(f"🔍 医疗质控系统集成验证")
        print(f"📁 项目根目录: {self.project_root}")
        print(f"🌐 Supabase URL: {self.supabase_url}")
        print("=" * 60)

    def verify_database_structure(self) -> Dict[str, Any]:
        """验证数据库文件结构"""
        print("\n📊 1. 数据库结构验证")
        
        result = {
            "status": "success",
            "details": {},
            "errors": []
        }
        
        # 检查数据库目录结构
        db_dirs = {
            "setup": self.project_root / "database" / "setup",
            "fixes": self.project_root / "database" / "fixes", 
            "migrations": self.project_root / "database" / "migrations",
            "schemas": self.project_root / "database" / "schemas"
        }
        
        for dir_name, dir_path in db_dirs.items():
            if dir_path.exists():
                files = list(dir_path.glob("*.sql"))
                result["details"][f"{dir_name}_dir"] = {
                    "exists": True,
                    "file_count": len(files),
                    "files": [f.name for f in files]
                }
                print(f"  ✅ {dir_name}/ 目录: {len(files)} 个文件")
            else:
                result["details"][f"{dir_name}_dir"] = {"exists": False}
                result["errors"].append(f"{dir_name} 目录不存在")
                print(f"  ❌ {dir_name}/ 目录不存在")
        
        # 检查关键脚本文件
        key_scripts = [
            "database/setup/database_init_complete.sql",
            "database/setup/verify_database.sql",
            "database/fixes/database_simple_fix.sql"
        ]
        
        for script in key_scripts:
            script_path = self.project_root / script
            if script_path.exists():
                print(f"  ✅ {script}")
            else:
                result["errors"].append(f"缺少关键脚本: {script}")
                print(f"  ❌ {script}")
        
        if result["errors"]:
            result["status"] = "error"
        
        return result

    def test_database_connection(self) -> Dict[str, Any]:
        """测试数据库连接"""
        print("\n🔗 2. 数据库连接测试")
        
        result = {
            "status": "unknown",
            "connection": False,
            "tables": [],
            "views": [],
            "policies": [],
            "errors": []
        }
        
        try:
            # 使用 Supabase REST API 测试连接
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json"
            }

            # 测试基本连接
            if HAS_REQUESTS:
                response = requests.get(
                    f"{self.supabase_url}/rest/v1/departments?select=count",
                    headers=headers,
                    timeout=10
                )
                status_code = response.status_code
            else:
                # 使用 urllib 作为备选
                req = urllib.request.Request(
                    f"{self.supabase_url}/rest/v1/departments?select=count",
                    headers=headers
                )
                try:
                    response = urllib.request.urlopen(req, timeout=10)
                    status_code = response.getcode()
                except urllib.error.HTTPError as e:
                    status_code = e.code
            
            if status_code == 200:
                result["connection"] = True
                print("  ✅ 数据库连接成功")

                # 检查核心表
                core_tables = ["departments", "user_profiles", "medical_records", "qc_rules"]
                for table in core_tables:
                    try:
                        if HAS_REQUESTS:
                            table_response = requests.get(
                                f"{self.supabase_url}/rest/v1/{table}?select=*&limit=0",
                                headers=headers,
                                timeout=5
                            )
                            table_status = table_response.status_code
                        else:
                            table_req = urllib.request.Request(
                                f"{self.supabase_url}/rest/v1/{table}?select=*&limit=0",
                                headers=headers
                            )
                            try:
                                table_response = urllib.request.urlopen(table_req, timeout=5)
                                table_status = table_response.getcode()
                            except urllib.error.HTTPError as e:
                                table_status = e.code

                        if table_status == 200:
                            result["tables"].append(table)
                            print(f"    ✅ 表 {table} 存在")
                        else:
                            print(f"    ❌ 表 {table} 不存在或无法访问")
                    except Exception as e:
                        print(f"    ❌ 检查表 {table} 时出错: {e}")

                result["status"] = "success"

            else:
                result["errors"].append(f"连接失败: HTTP {status_code}")
                print(f"  ❌ 数据库连接失败: HTTP {status_code}")
                result["status"] = "error"
                
        except Exception as e:
            result["errors"].append(f"连接异常: {str(e)}")
            print(f"  ❌ 数据库连接异常: {e}")
            result["status"] = "error"
        
        return result

    def verify_frontend_setup(self) -> Dict[str, Any]:
        """验证前端设置"""
        print("\n🎨 3. 前端设置验证")
        
        result = {
            "status": "unknown",
            "package_json": False,
            "dependencies": {},
            "config_files": {},
            "errors": []
        }
        
        # 检查 package.json
        package_json_path = self.project_root / "package.json"
        if package_json_path.exists():
            result["package_json"] = True
            print("  ✅ package.json 存在")
            
            try:
                with open(package_json_path, 'r', encoding='utf-8') as f:
                    package_data = json.load(f)
                    
                # 检查关键依赖
                key_deps = ["vue", "@supabase/supabase-js", "ant-design-vue", "vite"]
                deps = {**package_data.get("dependencies", {}), **package_data.get("devDependencies", {})}
                
                for dep in key_deps:
                    if dep in deps:
                        result["dependencies"][dep] = deps[dep]
                        print(f"    ✅ {dep}: {deps[dep]}")
                    else:
                        result["errors"].append(f"缺少依赖: {dep}")
                        print(f"    ❌ 缺少依赖: {dep}")
                        
            except Exception as e:
                result["errors"].append(f"读取 package.json 失败: {e}")
                print(f"  ❌ 读取 package.json 失败: {e}")
        else:
            result["errors"].append("package.json 不存在")
            print("  ❌ package.json 不存在")
        
        # 检查配置文件
        config_files = {
            "vite.config.ts": self.project_root / "vite.config.ts",
            "tsconfig.json": self.project_root / "tsconfig.json",
            ".env": self.project_root / ".env"
        }
        
        for name, path in config_files.items():
            if path.exists():
                result["config_files"][name] = True
                print(f"  ✅ {name} 存在")
            else:
                result["config_files"][name] = False
                print(f"  ⚠️  {name} 不存在")
        
        # 检查源码目录
        src_path = self.project_root / "src"
        if src_path.exists():
            key_dirs = ["components", "views", "services", "stores"]
            for dir_name in key_dirs:
                dir_path = src_path / dir_name
                if dir_path.exists():
                    print(f"  ✅ src/{dir_name}/ 目录存在")
                else:
                    print(f"  ⚠️  src/{dir_name}/ 目录不存在")
        
        result["status"] = "success" if not result["errors"] else "warning"
        return result

    def verify_backend_setup(self) -> Dict[str, Any]:
        """验证后端设置"""
        print("\n🔧 4. 后端设置验证")
        
        result = {
            "status": "unknown",
            "requirements": False,
            "main_file": False,
            "api_structure": {},
            "errors": []
        }
        
        backend_path = self.project_root / "production_system"
        
        if not backend_path.exists():
            result["errors"].append("production_system 目录不存在")
            print("  ❌ production_system 目录不存在")
            result["status"] = "error"
            return result
        
        # 检查 requirements.txt
        req_path = backend_path / "requirements.txt"
        if req_path.exists():
            result["requirements"] = True
            print("  ✅ requirements.txt 存在")
        else:
            result["errors"].append("requirements.txt 不存在")
            print("  ❌ requirements.txt 不存在")
        
        # 检查主文件
        main_path = backend_path / "main.py"
        if main_path.exists():
            result["main_file"] = True
            print("  ✅ main.py 存在")
        else:
            result["errors"].append("main.py 不存在")
            print("  ❌ main.py 不存在")
        
        # 检查 API 结构
        api_dirs = ["api", "core", "services", "models"]
        for dir_name in api_dirs:
            dir_path = backend_path / dir_name
            if dir_path.exists():
                files = list(dir_path.glob("*.py"))
                result["api_structure"][dir_name] = len(files)
                print(f"  ✅ {dir_name}/ 目录: {len(files)} 个 Python 文件")
            else:
                result["api_structure"][dir_name] = 0
                print(f"  ⚠️  {dir_name}/ 目录不存在")
        
        result["status"] = "success" if not result["errors"] else "warning"
        return result

    def test_tools_scripts(self) -> Dict[str, Any]:
        """测试工具脚本"""
        print("\n🔧 5. 工具脚本验证")
        
        result = {
            "status": "unknown",
            "testing_tools": {},
            "deployment_tools": {},
            "errors": []
        }
        
        # 测试工具目录
        tools_path = self.project_root / "tools"
        
        if not tools_path.exists():
            result["errors"].append("tools 目录不存在")
            print("  ❌ tools 目录不存在")
            result["status"] = "error"
            return result
        
        # 检查测试工具
        testing_path = tools_path / "testing"
        if testing_path.exists():
            test_files = list(testing_path.glob("*"))
            result["testing_tools"]["file_count"] = len(test_files)
            result["testing_tools"]["files"] = [f.name for f in test_files]
            print(f"  ✅ testing/ 目录: {len(test_files)} 个文件")
            
            # 测试 Supabase 连接脚本
            supabase_test = testing_path / "test_new_supabase_connection.js"
            if supabase_test.exists():
                print("    ✅ Supabase 连接测试脚本存在")
            else:
                print("    ⚠️  Supabase 连接测试脚本不存在")
        else:
            result["errors"].append("tools/testing 目录不存在")
            print("  ❌ tools/testing 目录不存在")
        
        # 检查部署工具
        deployment_path = tools_path / "deployment"
        if deployment_path.exists():
            deploy_files = list(deployment_path.glob("*"))
            result["deployment_tools"]["file_count"] = len(deploy_files)
            result["deployment_tools"]["files"] = [f.name for f in deploy_files]
            print(f"  ✅ deployment/ 目录: {len(deploy_files)} 个文件")
        else:
            result["errors"].append("tools/deployment 目录不存在")
            print("  ❌ tools/deployment 目录不存在")
        
        result["status"] = "success" if not result["errors"] else "warning"
        return result

    def generate_report(self) -> str:
        """生成验证报告"""
        print("\n📋 生成集成验证报告...")
        
        # 计算总体状态
        statuses = [
            self.results["database"].get("status", "unknown"),
            self.results["frontend"].get("status", "unknown"),
            self.results["backend"].get("status", "unknown"),
            self.results["tools"].get("status", "unknown")
        ]
        
        if all(s == "success" for s in statuses):
            self.results["overall_status"] = "success"
        elif any(s == "error" for s in statuses):
            self.results["overall_status"] = "error"
        else:
            self.results["overall_status"] = "warning"
        
        # 保存报告
        report_path = self.project_root / "reports" / f"integration_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"📄 报告已保存: {report_path}")
        return str(report_path)

    def run_verification(self):
        """运行完整验证"""
        print("🚀 开始医疗质控系统集成验证\n")
        
        # 1. 数据库结构验证
        self.results["database"]["structure"] = self.verify_database_structure()
        
        # 2. 数据库连接测试
        self.results["database"]["connection"] = self.test_database_connection()
        
        # 合并数据库结果
        db_errors = (self.results["database"]["structure"].get("errors", []) + 
                    self.results["database"]["connection"].get("errors", []))
        self.results["database"]["status"] = "error" if db_errors else "success"
        self.results["database"]["errors"] = db_errors
        
        # 3. 前端验证
        self.results["frontend"] = self.verify_frontend_setup()
        
        # 4. 后端验证
        self.results["backend"] = self.verify_backend_setup()
        
        # 5. 工具脚本验证
        self.results["tools"] = self.test_tools_scripts()
        
        # 6. 生成报告
        report_path = self.generate_report()
        
        # 7. 显示总结
        self.print_summary()
        
        return self.results

    def print_summary(self):
        """打印验证总结"""
        print("\n" + "=" * 60)
        print("📊 集成验证总结")
        print("=" * 60)
        
        status_emoji = {
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "unknown": "❓"
        }
        
        components = [
            ("数据库", self.results["database"]["status"]),
            ("前端", self.results["frontend"]["status"]),
            ("后端", self.results["backend"]["status"]),
            ("工具", self.results["tools"]["status"])
        ]
        
        for name, status in components:
            emoji = status_emoji.get(status, "❓")
            print(f"{emoji} {name}: {status.upper()}")
        
        print(f"\n🎯 总体状态: {status_emoji.get(self.results['overall_status'], '❓')} {self.results['overall_status'].upper()}")
        
        if self.results["overall_status"] == "success":
            print("\n🎉 恭喜！医疗质控系统集成验证通过！")
        elif self.results["overall_status"] == "warning":
            print("\n⚠️  系统基本可用，但存在一些警告项需要关注。")
        else:
            print("\n❌ 系统存在严重问题，需要修复后才能正常使用。")

if __name__ == "__main__":
    verifier = IntegrationVerifier()
    results = verifier.run_verification()
