
from sqlalchemy import text
from app.database.connection import engine

def check_table_schema(table_name):
    print(f"检查表 {table_name} 的约束和列信息...")
    with engine.connect() as conn:
        result = conn.execute(text(f"""
            SELECT column_name, is_nullable, column_default, data_type
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position;
        """))
        for row in result:
            print(f"列: {row.column_name:25} | 可空: {row.is_nullable:5} | 默认值: {str(row.column_default):20} | 类型: {row.data_type}")

if __name__ == "__main__":
    check_table_schema("mr")
    print("-" * 50)
    check_table_schema("admission_record")
