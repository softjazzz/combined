#!/usr/bin/env python3
"""
Supabase 数据库迁移工具
用途：从海外 Supabase 迁移到阿里云 Supabase
使用方法：python migrate_supabase.py
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
import getpass

# 颜色定义
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_colored(text, color):
    """打印彩色文本"""
    print(f"{color}{text}{Colors.NC}")

def print_header(text):
    """打印标题"""
    print("\n" + "=" * 60)
    print_colored(text, Colors.BLUE)
    print("=" * 60 + "\n")

def check_dependencies():
    """检查依赖工具是否安装"""
    print_colored("🔍 检查依赖工具...", Colors.BLUE)
    
    required_tools = ['pg_dump', 'psql']
    missing_tools = []
    
    for tool in required_tools:
        try:
            subprocess.run([tool, '--version'], 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE, 
                         check=True)
            print_colored(f"  ✅ {tool} 已安装", Colors.GREEN)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing_tools.append(tool)
            print_colored(f"  ❌ {tool} 未安装", Colors.RED)
    
    if missing_tools:
        print_colored("\n请安装 PostgreSQL 客户端工具：", Colors.YELLOW)
        print("  Ubuntu/Debian: sudo apt-get install postgresql-client")
        print("  macOS: brew install postgresql")
        print("  CentOS/RHEL: sudo yum install postgresql")
        sys.exit(1)
    
    print_colored("\n✅ 所有依赖工具已安装\n", Colors.GREEN)

def get_database_config(db_type):
    """获取数据库配置"""
    print_header(f"📋 请输入{db_type}数据库信息")
    
    if db_type == "源":
        print("提示：在 Supabase 项目设置 -> Database -> Connection string 中查看")
        print("示例主机: db.dgsdkdbjpucyawnyfbdu.supabase.co\n")
    
    host = input(f"{db_type}数据库主机: ").strip()
    port = input(f"{db_type}数据库端口 (默认: 5432): ").strip() or "5432"
    user = input(f"{db_type}数据库用户名 (默认: postgres): ").strip() or "postgres"
    password = getpass.getpass(f"{db_type}数据库密码: ")
    database = input(f"{db_type}数据库名称 (默认: postgres): ").strip() or "postgres"
    
    return {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'database': database,
        'conn_string': f"postgresql://{user}:{password}@{host}:{port}/{database}"
    }

def test_connection(config, db_type):
    """测试数据库连接"""
    print_colored(f"\n🔄 测试{db_type}数据库连接...", Colors.BLUE)
    
    try:
        result = subprocess.run(
            ['psql', config['conn_string'], '-c', 'SELECT version();'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10
        )
        
        if result.returncode == 0:
            print_colored(f"✅ {db_type}数据库连接成功", Colors.GREEN)
            return True
        else:
            print_colored(f"❌ {db_type}数据库连接失败", Colors.RED)
            print(f"错误信息: {result.stderr.decode()}")
            return False
    except subprocess.TimeoutExpired:
        print_colored(f"❌ {db_type}数据库连接超时", Colors.RED)
        return False
    except Exception as e:
        print_colored(f"❌ {db_type}数据库连接失败: {e}", Colors.RED)
        return False

def export_database(source_config, backup_file):
    """导出数据库"""
    print_colored("\n🔄 导出源数据库...", Colors.BLUE)
    print("这可能需要几分钟，请耐心等待...\n")
    
    try:
        result = subprocess.run(
            [
                'pg_dump',
                source_config['conn_string'],
                '--no-owner',
                '--no-acl',
                '--clean',
                '--if-exists',
                '-f', backup_file
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        if result.returncode == 0:
            file_size = os.path.getsize(backup_file)
            size_mb = file_size / (1024 * 1024)
            print_colored(f"✅ 数据库导出成功: {backup_file}", Colors.GREEN)
            print(f"   文件大小: {size_mb:.2f} MB")
            return True
        else:
            print_colored("❌ 数据库导出失败", Colors.RED)
            print(f"错误信息: {result.stderr.decode()}")
            return False
    except Exception as e:
        print_colored(f"❌ 数据库导出失败: {e}", Colors.RED)
        return False

def import_database(target_config, backup_file):
    """导入数据库"""
    print_colored("\n🔄 导入到目标数据库...", Colors.BLUE)
    print("这可能需要几分钟，请耐心等待...\n")
    
    try:
        with open(backup_file, 'r') as f:
            result = subprocess.run(
                ['psql', target_config['conn_string']],
                stdin=f,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        
        if result.returncode == 0:
            print_colored("✅ 数据库导入成功", Colors.GREEN)
            return True
        else:
            # 即使有警告，也可能导入成功
            stderr = result.stderr.decode()
            if 'ERROR' in stderr:
                print_colored("❌ 数据库导入失败", Colors.RED)
                print(f"错误信息: {stderr}")
                return False
            else:
                print_colored("⚠️  导入过程中有警告，但数据已导入", Colors.YELLOW)
                return True
    except Exception as e:
        print_colored(f"❌ 数据库导入失败: {e}", Colors.RED)
        return False

def print_next_steps(backup_file):
    """打印后续步骤"""
    print_header("🎉 迁移完成！")
    
    print_colored("📝 后续步骤：\n", Colors.BLUE)
    
    print("1. 更新 .env 文件中的 Supabase 配置：")
    print_colored("   SUPABASE_URL=https://[your-aliyun-project].supabase.co", Colors.YELLOW)
    print_colored("   SUPABASE_KEY=[your-new-anon-key]", Colors.YELLOW)
    print_colored("   SUPABASE_SERVICE_ROLE_KEY=[your-new-service-role-key]", Colors.YELLOW)
    
    print("\n2. 重启后端服务")
    
    print("\n3. 测试应用功能")
    
    print(f"\n4. 备份文件已保存: {backup_file}")
    print("   建议保留此文件作为备份")
    
    print("\n" + "=" * 60 + "\n")

def main():
    """主函数"""
    print_header("🚀 Supabase 数据库迁移工具")
    
    # 检查依赖
    check_dependencies()
    
    # 获取源数据库配置
    source_config = get_database_config("源")
    
    # 获取目标数据库配置
    target_config = get_database_config("目标")
    
    # 生成备份文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"supabase_backup_{timestamp}.sql"
    
    # 显示配置摘要
    print_header("📊 迁移配置摘要")
    print(f"源数据库: {source_config['host']}:{source_config['port']}/{source_config['database']}")
    print(f"目标数据库: {target_config['host']}:{target_config['port']}/{target_config['database']}")
    print(f"备份文件: {backup_file}")
    
    # 确认
    confirm = input("\n确认开始迁移？(y/n): ").strip().lower()
    if confirm != 'y':
        print_colored("❌ 迁移已取消", Colors.RED)
        sys.exit(0)
    
    # 测试源数据库连接
    if not test_connection(source_config, "源"):
        sys.exit(1)
    
    # 测试目标数据库连接
    if not test_connection(target_config, "目标"):
        sys.exit(1)
    
    # 导出数据库
    if not export_database(source_config, backup_file):
        sys.exit(1)
    
    # 导入数据库
    if not import_database(target_config, backup_file):
        sys.exit(1)
    
    # 打印后续步骤
    print_next_steps(backup_file)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_colored("\n\n❌ 迁移已取消", Colors.RED)
        sys.exit(1)
    except Exception as e:
        print_colored(f"\n\n❌ 发生错误: {e}", Colors.RED)
        sys.exit(1)

