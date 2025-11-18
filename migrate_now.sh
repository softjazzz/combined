#!/bin/bash

set -e

echo "🚀 开始 Supabase 数据迁移"
echo "================================"
echo ""

# 源数据库（海外 Supabase）
SOURCE_HOST="db.dgsdkdbjpucyawnyfbdu.supabase.co"
SOURCE_PORT="5432"
SOURCE_USER="postgres"
SOURCE_PASSWORD="postgres"
SOURCE_DB="postgres"
SOURCE_CONN="postgresql://${SOURCE_USER}:${SOURCE_PASSWORD}@${SOURCE_HOST}:${SOURCE_PORT}/${SOURCE_DB}"

# 目标数据库（阿里云 Supabase）
TARGET_HOST="sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
TARGET_PORT="5432"
TARGET_USER="postgres"
TARGET_PASSWORD="Han1979919"
TARGET_DB="postgres"
TARGET_CONN="postgresql://${TARGET_USER}:${TARGET_PASSWORD}@${TARGET_HOST}:${TARGET_PORT}/${TARGET_DB}"

# 备份文件
BACKUP_FILE="supabase_backup_$(date +%Y%m%d_%H%M%S).sql"

echo "📊 迁移配置:"
echo "  源数据库: ${SOURCE_HOST}"
echo "  目标数据库: ${TARGET_HOST}"
echo "  备份文件: ${BACKUP_FILE}"
echo ""

# 步骤 1: 测试源数据库连接
echo "🔄 步骤 1/4: 测试源数据库连接..."
if timeout 10 psql "${SOURCE_CONN}" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ 源数据库连接成功"
else
    echo "❌ 源数据库连接失败"
    exit 1
fi

# 步骤 2: 测试目标数据库连接
echo ""
echo "🔄 步骤 2/4: 测试目标数据库连接..."
if timeout 10 psql "${TARGET_CONN}" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ 目标数据库连接成功"
else
    echo "❌ 目标数据库连接失败"
    exit 1
fi

# 步骤 3: 导出源数据库
echo ""
echo "🔄 步骤 3/4: 导出源数据库..."
echo "这可能需要几分钟，请耐心等待..."
echo ""

if pg_dump "${SOURCE_CONN}" \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    -f "${BACKUP_FILE}"; then
    
    FILE_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "✅ 数据库导出成功"
    echo "   文件: ${BACKUP_FILE}"
    echo "   大小: ${FILE_SIZE}"
else
    echo "❌ 数据库导出失败"
    exit 1
fi

# 步骤 4: 导入到目标数据库
echo ""
echo "🔄 步骤 4/4: 导入到目标数据库..."
echo "这可能需要几分钟，请耐心等待..."
echo ""

if psql "${TARGET_CONN}" -f "${BACKUP_FILE}" 2>&1 | tee import.log; then
    echo ""
    echo "✅ 数据库导入完成"
else
    echo ""
    echo "⚠️  导入过程中可能有警告，请检查 import.log"
fi

# 验证迁移
echo ""
echo "🔍 验证迁移结果..."
echo ""

echo "源数据库表数量:"
psql "${SOURCE_CONN}" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null || echo "0"

echo "目标数据库表数量:"
psql "${TARGET_CONN}" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null || echo "0"

echo ""
echo "================================"
echo "🎉 迁移完成！"
echo "================================"
echo ""
echo "📝 后续步骤:"
echo "1. 更新 .env 文件中的 Supabase 配置"
echo "2. 重启后端服务"
echo "3. 测试应用功能"
echo ""
echo "备份文件: ${BACKUP_FILE}"
echo ""

