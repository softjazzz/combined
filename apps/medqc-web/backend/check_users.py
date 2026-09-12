import os
"""查询并修复用户名乱码"""
import psycopg2

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

# 查看 sys.sys_users 表的所有用户
print("=== sys.sys_users ===")
cur.execute("SELECT id, email, display_name, role FROM sys.sys_users")
for row in cur.fetchall():
    print(f"  id={row[0]}, email={row[1]}, display_name={repr(row[2])}, role={row[3]}")

# 查看 public.user_profiles 表
print("\n=== public.user_profiles ===")
cur.execute("SELECT * FROM public.user_profiles LIMIT 10")
cols = [d[0] for d in cur.description]
print(f"  columns: {cols}")
for row in cur.fetchall():
    print(f"  {row}")

conn.close()
