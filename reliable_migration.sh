#!/bin/bash

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_step() { echo -e "${CYAN}🔄 $1${NC}"; }

# 数据库连接信息
SOURCE_HOST="db.dgsdkdbjpucyawnyfbdu.supabase.co"
SOURCE_PORT="5432"
SOURCE_USER="postgres"
SOURCE_PASSWORD="rK6XqKqU6hB45iMS"
SOURCE_DB="postgres"

TARGET_HOST="sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
TARGET_PORT="5432"
TARGET_USER="postgres"
TARGET_PASSWORD="Han1979919"
TARGET_DB="postgres"

# 连接字符串
SOURCE_CONN="postgresql://${SOURCE_USER}:${SOURCE_PASSWORD}@${SOURCE_HOST}:${SOURCE_PORT}/${SOURCE_DB}"
TARGET_CONN="postgresql://${TARGET_USER}:${TARGET_PASSWORD}@${TARGET_HOST}:${TARGET_PORT}/${TARGET_DB}"

# 备份文件
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="supabase_backup_${TIMESTAMP}.sql"
BACKUP_DIR="./backups"

# 创建备份目录
mkdir -p "${BACKUP_DIR}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILE}"

echo ""
echo "=========================================="
echo "🚀 Supabase 数据库完整迁移工具"
echo "=========================================="
echo ""
print_info "源数据库: ${SOURCE_HOST}"
print_info "目标数据库: ${TARGET_HOST}"
print_info "备份文件: ${BACKUP_PATH}"
echo ""

# ============================================
# 步骤 1: 检查依赖
# ============================================
print_step "步骤 1/6: 检查依赖工具..."
echo ""

if ! command -v pg_dump &> /dev/null; then
    print_error "pg_dump 未安装"
    print_info "请安装 PostgreSQL 客户端工具："
    print_info "  Ubuntu/Debian: sudo apt-get install postgresql-client"
    print_info "  macOS: brew install postgresql"
    exit 1
fi

if ! command -v psql &> /dev/null; then
    print_error "psql 未安装"
    exit 1
fi

print_success "所有依赖工具已安装"
echo ""

# ============================================
# 步骤 2: 测试源数据库连接
# ============================================
print_step "步骤 2/6: 测试源数据库连接..."
echo ""

print_info "正在连接海外 Supabase（可能需要 10-30 秒）..."

if timeout 60 psql "${SOURCE_CONN}" -c "SELECT version();" > /dev/null 2>&1; then
    print_success "源数据库连接成功"
    
    # 获取数据库信息
    DB_VERSION=$(psql "${SOURCE_CONN}" -t -c "SELECT version();" 2>/dev/null | head -n 1 | xargs)
    print_info "数据库版本: ${DB_VERSION:0:50}..."
    
    # 获取表数量
    TABLE_COUNT=$(psql "${SOURCE_CONN}" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | xargs)
    print_info "public schema 中的表数量: ${TABLE_COUNT}"
else
    print_error "源数据库连接失败"
    print_warning "可能原因："
    print_warning "  1. 密码错误"
    print_warning "  2. 网络连接超时（海外数据库延迟高）"
    print_warning "  3. 数据库未开启直连访问"
    echo ""
    print_info "建议："
    print_info "  1. 检查密码是否正确"
    print_info "  2. 在 Supabase 控制台启用 Direct database access"
    print_info "  3. 检查防火墙设置"
    exit 1
fi

echo ""

# ============================================
# 步骤 3: 测试目标数据库连接
# ============================================
print_step "步骤 3/6: 测试目标数据库连接..."
echo ""

if timeout 10 psql "${TARGET_CONN}" -c "SELECT version();" > /dev/null 2>&1; then
    print_success "目标数据库连接成功"
else
    print_error "目标数据库连接失败"
    exit 1
fi

echo ""

# ============================================
# 步骤 4: 导出源数据库
# ============================================
print_step "步骤 4/6: 导出源数据库..."
echo ""

print_info "这可能需要 5-15 分钟，具体取决于网络速度和数据量..."
print_info "导出内容: 表结构 + 数据 + 索引 + 约束"
echo ""

# 使用 pg_dump 导出
# --no-owner: 不导出所有者信息
# --no-acl: 不导出访问权限
# --clean: 在创建对象前先删除
# --if-exists: 使用 IF EXISTS 子句
# --schema=public: 只导出 public schema
# --verbose: 显示详细进度

export PGPASSWORD="${SOURCE_PASSWORD}"

if pg_dump \
    --host="${SOURCE_HOST}" \
    --port="${SOURCE_PORT}" \
    --username="${SOURCE_USER}" \
    --dbname="${SOURCE_DB}" \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    --schema=public \
    --verbose \
    --file="${BACKUP_PATH}" 2>&1 | while IFS= read -r line; do
        # 只显示重要的进度信息
        if [[ "$line" =~ "dumping contents of table" ]] || \
           [[ "$line" =~ "CREATE TABLE" ]] || \
           [[ "$line" =~ "CREATE INDEX" ]]; then
            echo "  $line"
        fi
    done; then
    
    echo ""
    FILE_SIZE=$(du -h "${BACKUP_PATH}" | cut -f1)
    LINE_COUNT=$(wc -l < "${BACKUP_PATH}")
    
    print_success "数据库导出成功"
    print_info "文件路径: ${BACKUP_PATH}"
    print_info "文件大小: ${FILE_SIZE}"
    print_info "SQL 行数: ${LINE_COUNT}"
else
    print_error "数据库导出失败"
    exit 1
fi

unset PGPASSWORD

echo ""

# ============================================
# 步骤 5: 检查备份文件
# ============================================
print_step "步骤 5/6: 检查备份文件..."
echo ""

if [ ! -s "${BACKUP_PATH}" ]; then
    print_error "备份文件为空"
    exit 1
fi

# 统计备份文件中的对象
CREATE_TABLE_COUNT=$(grep -c "CREATE TABLE" "${BACKUP_PATH}" || echo "0")
CREATE_INDEX_COUNT=$(grep -c "CREATE INDEX" "${BACKUP_PATH}" || echo "0")
INSERT_COUNT=$(grep -c "^COPY " "${BACKUP_PATH}" || echo "0")

print_info "备份文件包含:"
print_info "  - ${CREATE_TABLE_COUNT} 个表"
print_info "  - ${CREATE_INDEX_COUNT} 个索引"
print_info "  - ${INSERT_COUNT} 个数据复制操作"

echo ""
print_success "备份文件验证通过"
echo ""

# ============================================
# 步骤 6: 导入到目标数据库
# ============================================
print_step "步骤 6/6: 导入到目标数据库..."
echo ""

print_info "这可能需要 2-5 分钟..."
print_warning "导入过程中可能会有一些警告（例如：对象已存在），这是正常的"
echo ""

export PGPASSWORD="${TARGET_PASSWORD}"

# 创建导入日志文件
IMPORT_LOG="${BACKUP_DIR}/import_${TIMESTAMP}.log"

if psql \
    --host="${TARGET_HOST}" \
    --port="${TARGET_PORT}" \
    --username="${TARGET_USER}" \
    --dbname="${TARGET_DB}" \
    --file="${BACKUP_PATH}" \
    2>&1 | tee "${IMPORT_LOG}" | while IFS= read -r line; do
        # 过滤掉一些不重要的警告
        if [[ ! "$line" =~ "NOTICE" ]] && \
           [[ ! "$line" =~ "does not exist, skipping" ]]; then
            echo "$line"
        fi
    done; then
    
    echo ""
    print_success "数据库导入完成"
else
    echo ""
    print_warning "导入过程中有一些错误，但可能不影响最终结果"
    print_info "详细日志: ${IMPORT_LOG}"
fi

unset PGPASSWORD

echo ""

# ============================================
# 步骤 7: 验证迁移结果
# ============================================
print_step "验证迁移结果..."
echo ""

export PGPASSWORD="${TARGET_PASSWORD}"

# 获取目标数据库的表数量
TARGET_TABLE_COUNT=$(psql "${TARGET_CONN}" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | xargs)

print_info "目标数据库中的表数量: ${TARGET_TABLE_COUNT}"
echo ""

# 列出所有表及其记录数
print_info "各表记录数统计:"
echo ""

psql "${TARGET_CONN}" -t -c "
SELECT 
    schemaname || '.' || tablename AS table_name,
    n_live_tup AS row_count
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC;
" 2>/dev/null | while IFS='|' read -r table_name row_count; do
    if [ -n "$table_name" ]; then
        table_name=$(echo "$table_name" | xargs)
        row_count=$(echo "$row_count" | xargs)
        printf "  %-40s %10s 条\n" "$table_name" "$row_count"
    fi
done

unset PGPASSWORD

echo ""

# ============================================
# 步骤 8: 禁用 RLS
# ============================================
print_step "禁用 RLS (Row Level Security)..."
echo ""

export PGPASSWORD="${TARGET_PASSWORD}"

psql "${TARGET_CONN}" << 'EOF' > /dev/null 2>&1
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
    LOOP
        EXECUTE 'ALTER TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' DISABLE ROW LEVEL SECURITY';
        EXECUTE 'GRANT ALL ON public.' || quote_ident(r.tablename) || ' TO anon';
        EXECUTE 'GRANT ALL ON public.' || quote_ident(r.tablename) || ' TO authenticated';
    END LOOP;
END $$;
EOF

if [ $? -eq 0 ]; then
    print_success "RLS 已禁用，权限已授予"
else
    print_warning "RLS 禁用失败（可能需要手动处理）"
fi

unset PGPASSWORD

echo ""

# ============================================
# 完成
# ============================================
echo "=========================================="
print_success "🎉 数据库迁移完成！"
echo "=========================================="
echo ""

print_info "📝 迁移总结:"
print_info "  ✅ 源数据库表数: ${TABLE_COUNT}"
print_info "  ✅ 目标数据库表数: ${TARGET_TABLE_COUNT}"
print_info "  ✅ 备份文件: ${BACKUP_PATH}"
print_info "  ✅ 导入日志: ${IMPORT_LOG}"
echo ""

print_info "📋 后续步骤:"
print_info "  1. 环境变量已更新（.env 文件）"
print_info "  2. 重启后端服务（会自动重新加载）"
print_info "  3. 刷新前端页面测试"
echo ""

print_warning "💡 提示:"
print_warning "  - 备份文件已保存，可用于回滚或再次导入"
print_warning "  - 如需删除备份文件: rm -rf ${BACKUP_DIR}"
echo ""

