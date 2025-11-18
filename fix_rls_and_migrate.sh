#!/bin/bash

set -e

echo "🔧 修复 RLS 并重新迁移数据"
echo "================================"
echo ""

# 数据库连接信息
DB_HOST="sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
DB_PORT="5432"
DB_USER="postgres"
DB_PASSWORD="Han1979919"
DB_NAME="postgres"
CONN_STRING="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

echo "📋 数据库: ${DB_HOST}"
echo ""

# 步骤 1: 禁用 RLS
echo "🔄 步骤 1/2: 禁用 RLS (Row Level Security)..."
echo ""

psql "${CONN_STRING}" << 'EOF'
-- 禁用所有表的 RLS
ALTER TABLE IF EXISTS public.medical_records_test DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.medical_documents_test DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.document_categories_test DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.document_types_test DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.qc_rules DISABLE ROW LEVEL SECURITY;

-- 授予 anon 角色完全权限
GRANT ALL ON public.medical_records_test TO anon;
GRANT ALL ON public.medical_documents_test TO anon;
GRANT ALL ON public.document_categories_test TO anon;
GRANT ALL ON public.document_types_test TO anon;
GRANT ALL ON public.qc_rules TO anon;

-- 授予 authenticated 角色完全权限
GRANT ALL ON public.medical_records_test TO authenticated;
GRANT ALL ON public.medical_documents_test TO authenticated;
GRANT ALL ON public.document_categories_test TO authenticated;
GRANT ALL ON public.document_types_test TO authenticated;
GRANT ALL ON public.qc_rules TO authenticated;

SELECT 'RLS 已禁用，权限已授予' AS status;
EOF

if [ $? -eq 0 ]; then
    echo "✅ RLS 禁用成功"
else
    echo "❌ RLS 禁用失败"
    exit 1
fi

# 步骤 2: 重新运行数据迁移
echo ""
echo "🔄 步骤 2/2: 重新迁移数据..."
echo ""

python3 migrate_via_api.py

echo ""
echo "================================"
echo "✅ 完成！"
echo "================================"
echo ""

