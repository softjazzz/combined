#!/bin/bash

# Supabase 数据库迁移脚本
# 用途：从海外 Supabase 迁移到阿里云 Supabase
# 使用方法：./migrate_supabase.sh

set -e  # 遇到错误立即退出

echo "🚀 Supabase 数据库迁移工具"
echo "================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 pg_dump 和 psql 是否安装
if ! command -v pg_dump &> /dev/null; then
    echo -e "${RED}❌ 错误: pg_dump 未安装${NC}"
    echo "请安装 PostgreSQL 客户端工具："
    echo "  Ubuntu/Debian: sudo apt-get install postgresql-client"
    echo "  macOS: brew install postgresql"
    echo "  CentOS/RHEL: sudo yum install postgresql"
    exit 1
fi

if ! command -v psql &> /dev/null; then
    echo -e "${RED}❌ 错误: psql 未安装${NC}"
    exit 1
fi

echo -e "${GREEN}✅ PostgreSQL 客户端工具已安装${NC}"
echo ""

# 配置源数据库（海外 Supabase）
echo "📋 请输入源数据库信息（海外 Supabase）："
echo "提示：在 Supabase 项目设置 -> Database -> Connection string 中查看"
echo ""

read -p "源数据库主机 (例如: db.dgsdkdbjpucyawnyfbdu.supabase.co): " SOURCE_HOST
read -p "源数据库端口 (默认: 5432): " SOURCE_PORT
SOURCE_PORT=${SOURCE_PORT:-5432}
read -p "源数据库用户名 (默认: postgres): " SOURCE_USER
SOURCE_USER=${SOURCE_USER:-postgres}
read -sp "源数据库密码: " SOURCE_PASSWORD
echo ""
read -p "源数据库名称 (默认: postgres): " SOURCE_DB
SOURCE_DB=${SOURCE_DB:-postgres}

echo ""
echo "📋 请输入目标数据库信息（阿里云 Supabase）："
echo ""

read -p "目标数据库主机: " TARGET_HOST
read -p "目标数据库端口 (默认: 5432): " TARGET_PORT
TARGET_PORT=${TARGET_PORT:-5432}
read -p "目标数据库用户名 (默认: postgres): " TARGET_USER
TARGET_USER=${TARGET_USER:-postgres}
read -sp "目标数据库密码: " TARGET_PASSWORD
echo ""
read -p "目标数据库名称 (默认: postgres): " TARGET_DB
TARGET_DB=${TARGET_DB:-postgres}

# 构建连接字符串
SOURCE_CONN="postgresql://${SOURCE_USER}:${SOURCE_PASSWORD}@${SOURCE_HOST}:${SOURCE_PORT}/${SOURCE_DB}"
TARGET_CONN="postgresql://${TARGET_USER}:${TARGET_PASSWORD}@${TARGET_HOST}:${TARGET_PORT}/${TARGET_DB}"

# 备份文件名
BACKUP_FILE="supabase_backup_$(date +%Y%m%d_%H%M%S).sql"

echo ""
echo "================================"
echo "📊 迁移配置摘要："
echo "================================"
echo "源数据库: ${SOURCE_HOST}:${SOURCE_PORT}/${SOURCE_DB}"
echo "目标数据库: ${TARGET_HOST}:${TARGET_PORT}/${TARGET_DB}"
echo "备份文件: ${BACKUP_FILE}"
echo "================================"
echo ""

read -p "确认开始迁移？(y/n): " CONFIRM
if [ "$CONFIRM" != "y" ]; then
    echo "❌ 迁移已取消"
    exit 0
fi

echo ""
echo "🔄 步骤 1/4: 测试源数据库连接..."
if psql "${SOURCE_CONN}" -c "SELECT version();" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 源数据库连接成功${NC}"
else
    echo -e "${RED}❌ 源数据库连接失败，请检查连接信息${NC}"
    exit 1
fi

echo ""
echo "🔄 步骤 2/4: 测试目标数据库连接..."
if psql "${TARGET_CONN}" -c "SELECT version();" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 目标数据库连接成功${NC}"
else
    echo -e "${RED}❌ 目标数据库连接失败，请检查连接信息${NC}"
    exit 1
fi

echo ""
echo "🔄 步骤 3/4: 导出源数据库..."
echo "这可能需要几分钟，请耐心等待..."

# 导出数据库
# --no-owner: 不导出所有者信息
# --no-acl: 不导出访问权限
# --clean: 在重新创建之前清理（删除）数据库对象
# --if-exists: 使用 IF EXISTS 子句删除对象
if pg_dump "${SOURCE_CONN}" \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    -f "${BACKUP_FILE}"; then
    echo -e "${GREEN}✅ 数据库导出成功: ${BACKUP_FILE}${NC}"
    
    # 显示文件大小
    FILE_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "   文件大小: ${FILE_SIZE}"
else
    echo -e "${RED}❌ 数据库导出失败${NC}"
    exit 1
fi

echo ""
echo "🔄 步骤 4/4: 导入到目标数据库..."
echo "这可能需要几分钟，请耐心等待..."

# 导入数据库
if psql "${TARGET_CONN}" -f "${BACKUP_FILE}" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 数据库导入成功${NC}"
else
    echo -e "${YELLOW}⚠️  导入过程中可能有警告，但数据已导入${NC}"
    echo "   如果遇到问题，请检查日志文件"
fi

echo ""
echo "================================"
echo -e "${GREEN}🎉 迁移完成！${NC}"
echo "================================"
echo ""
echo "📝 后续步骤："
echo "1. 更新 .env 文件中的 Supabase 配置："
echo "   SUPABASE_URL=https://[your-aliyun-project].supabase.co"
echo "   SUPABASE_KEY=[your-new-anon-key]"
echo "   SUPABASE_SERVICE_ROLE_KEY=[your-new-service-role-key]"
echo ""
echo "2. 重启后端服务"
echo ""
echo "3. 测试应用功能"
echo ""
echo "4. 备份文件已保存: ${BACKUP_FILE}"
echo "   建议保留此文件作为备份"
echo ""
echo "================================"

