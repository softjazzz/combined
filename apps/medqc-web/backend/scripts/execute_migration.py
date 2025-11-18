#!/usr/bin/env python3
"""
执行数据库迁移脚本
"""
import os
import sys

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("❌ 请先安装 psycopg2: pip install psycopg2-binary")
    sys.exit(1)


def run_migration():
    """执行迁移脚本"""
    # 数据库连接信息
    db_config = {
        "host": "sbp-a41klzf2d6lvsjoj.supabase.opentrust.net",
        "port": 5432,
        "database": "postgres",
        "user": "postgres.a41klzf2d6lvsjoj",
        "password": "Lx@2024",
    }
    
    # 读取迁移脚本
    migration_file = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "database",
        "migrations",
        "20250902_setup_qc_llm_config.sql"
    )
    
    print(f"📖 读取迁移脚本: {migration_file}")
    with open(migration_file, "r", encoding="utf-8") as f:
        sql_script = f.read()
    
    # 连接数据库
    print("🔌 连接数据库...")
    try:
        conn = psycopg2.connect(**db_config)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("🚀 执行迁移脚本...")
        cursor.execute(sql_script)
        
        print("✅ 迁移脚本执行成功！")
        
        # 验证表是否创建成功
        print("\n📊 验证表创建...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('llm_api_providers', 'llm_models', 'user_llm_configs')
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        
        if len(tables) == 3:
            print("✅ 所有表创建成功:")
            for table in tables:
                print(f"   - {table[0]}")
        else:
            print(f"⚠️ 只创建了 {len(tables)} 个表:")
            for table in tables:
                print(f"   - {table[0]}")
        
        # 查询配置
        print("\n📋 查询默认配置...")
        cursor.execute("""
            SELECT config_name, provider_id, model_id 
            FROM user_llm_configs 
            WHERE config_name = 'default' AND user_id IS NULL
        """)
        config = cursor.fetchone()
        
        if config:
            print(f"✅ 默认配置已创建: config_name={config[0]}")
        else:
            print("⚠️ 默认配置未创建")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)

