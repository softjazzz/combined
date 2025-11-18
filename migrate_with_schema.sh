#!/bin/bash

set -e

echo "🚀 Supabase 完整迁移（包含表结构和数据）"
echo "=========================================="
echo ""

# 源数据库（海外 Supabase）
SOURCE_HOST="db.dgsdkdbjpucyawnyfbdu.supabase.co"
SOURCE_PORT="5432"
SOURCE_USER="postgres"
SOURCE_DB="postgres"

# 目标数据库（阿里云 Supabase）
TARGET_HOST="sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
TARGET_PORT="5432"
TARGET_USER="postgres"
TARGET_PASSWORD="Han1979919"
TARGET_DB="postgres"
TARGET_CONN="postgresql://${TARGET_USER}:${TARGET_PASSWORD}@${TARGET_HOST}:${TARGET_PORT}/${TARGET_DB}"

echo "📋 迁移配置:"
echo "  目标数据库: ${TARGET_HOST}"
echo ""

# 提示用户输入源数据库密码
echo "⚠️  需要海外 Supabase 数据库密码"
echo "请访问 https://app.supabase.com/project/dgsdkdbjpucyawnyfbdu/settings/database"
echo "查看 Database password"
echo ""
read -sp "请输入海外 Supabase 数据库密码: " SOURCE_PASSWORD
echo ""
echo ""

SOURCE_CONN="postgresql://${SOURCE_USER}:${SOURCE_PASSWORD}@${SOURCE_HOST}:${SOURCE_PORT}/${SOURCE_DB}"

# 备份文件
BACKUP_FILE="supabase_full_backup_$(date +%Y%m%d_%H%M%S).sql"

# 步骤 1: 测试源数据库连接
echo "🔄 步骤 1/5: 测试源数据库连接..."
if timeout 30 psql "${SOURCE_CONN}" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ 源数据库连接成功"
else
    echo "❌ 源数据库连接失败"
    echo "可能原因："
    echo "1. 密码错误"
    echo "2. 网络连接问题（海外数据库可能需要较长时间）"
    echo "3. 数据库未开启直连访问"
    exit 1
fi

# 步骤 2: 测试目标数据库连接
echo ""
echo "🔄 步骤 2/5: 测试目标数据库连接..."
if timeout 10 psql "${TARGET_CONN}" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ 目标数据库连接成功"
else
    echo "❌ 目标数据库连接失败"
    exit 1
fi

# 步骤 3: 导出源数据库（包含表结构和数据）
echo ""
echo "🔄 步骤 3/5: 导出源数据库..."
echo "这可能需要几分钟，请耐心等待..."
echo ""

# 只导出 public schema 中的特定表
TABLES="medical_records_test medical_documents_test document_categories_test document_types_test qc_rules"

if pg_dump "${SOURCE_CONN}" \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    --schema=public \
    -t medical_records_test \
    -t medical_documents_test \
    -t document_categories_test \
    -t document_types_test \
    -t qc_rules \
    -f "${BACKUP_FILE}"; then
    
    FILE_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "✅ 数据库导出成功"
    echo "   文件: ${BACKUP_FILE}"
    echo "   大小: ${FILE_SIZE}"
else
    echo "❌ 数据库导出失败"
    exit 1
fi

# 步骤 4: 检查备份文件
echo ""
echo "🔄 步骤 4/5: 检查备份文件..."
if [ -s "${BACKUP_FILE}" ]; then
    LINE_COUNT=$(wc -l < "${BACKUP_FILE}")
    echo "✅ 备份文件有效 (${LINE_COUNT} 行)"
    
    # 显示文件中的表
    echo "   包含的表:"
    grep "CREATE TABLE" "${BACKUP_FILE}" | sed 's/CREATE TABLE /  - /' || echo "  （未找到 CREATE TABLE 语句）"
else
    echo "❌ 备份文件为空"
    exit 1
fi

# 步骤 5: 导入到目标数据库
echo ""
echo "🔄 步骤 5/5: 导入到目标数据库..."
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

for table in $TABLES; do
    COUNT=$(psql "${TARGET_CONN}" -t -c "SELECT COUNT(*) FROM ${table};" 2>/dev/null | tr -d ' ' || echo "0")
    if [ "$COUNT" -gt 0 ]; then
        echo "  ✅ ${table}: ${COUNT} 条记录"
    else
        echo "  ⚠️  ${table}: 0 条记录（可能为空表）"
    fi
done

echo ""
echo "=========================================="
echo "🎉 迁移完成！"
echo "=========================================="
echo ""
echo "📝 后续步骤:"
echo "1. 环境变量已更新（.env 文件）"
echo "2. 重启后端服务（会自动重新加载）"
echo "3. 刷新前端页面测试"
echo ""
echo "备份文件: ${BACKUP_FILE}"
echo "导入日志: import.log"
echo ""

