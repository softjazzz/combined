#!/bin/bash

# 测试阿里云 Supabase 数据库直连

echo "🔍 测试阿里云 Supabase 数据库连接..."
echo ""

# 可能的主机地址
HOSTS=(
    "db.sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
    "sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
    "aws-0-ap-southeast-1.pooler.supabase.com"
)

PASSWORD="Han1979919"
PORT="5432"
USER="postgres"
DATABASE="postgres"

for HOST in "${HOSTS[@]}"; do
    echo "尝试连接: $HOST"
    
    CONN_STRING="postgresql://${USER}:${PASSWORD}@${HOST}:${PORT}/${DATABASE}"
    
    if timeout 10 psql "$CONN_STRING" -c "SELECT version();" 2>/dev/null | grep -q "PostgreSQL"; then
        echo "✅ 连接成功！"
        echo "主机地址: $HOST"
        echo "连接字符串: postgresql://${USER}:****@${HOST}:${PORT}/${DATABASE}"
        echo ""
        
        # 测试查询表
        echo "📊 检查现有表..."
        psql "$CONN_STRING" -c "\dt" 2>/dev/null || echo "数据库为空（正常）"
        
        exit 0
    else
        echo "❌ 连接失败"
        echo ""
    fi
done

echo "⚠️  所有主机地址都无法连接"
echo "请检查："
echo "1. 数据库密码是否正确"
echo "2. 网络连接是否正常"
echo "3. 防火墙是否允许 5432 端口"

