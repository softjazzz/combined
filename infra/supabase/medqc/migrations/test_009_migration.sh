#!/bin/bash

# test_009_migration.sh
# 测试 Migration 009 的执行和回滚
#
# 使用方法：
# chmod +x test_009_migration.sh
# ./test_009_migration.sh
#
# 版本: 2.0
# 创建日期: 2025-10-12

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 数据库连接信息（根据实际情况修改）
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-54322}"
DB_NAME="${DB_NAME:-postgres}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 执行 SQL 文件
execute_sql_file() {
    local sql_file=$1
    local description=$2
    
    log_info "$description"
    
    if [ ! -f "$sql_file" ]; then
        log_error "SQL file not found: $sql_file"
        return 1
    fi
    
    PGPASSWORD=$DB_PASSWORD psql \
        -h $DB_HOST \
        -p $DB_PORT \
        -U $DB_USER \
        -d $DB_NAME \
        -f "$sql_file" \
        2>&1 | tee /tmp/migration_009_output.log
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        log_success "$description completed"
        return 0
    else
        log_error "$description failed"
        return 1
    fi
}

# 执行 SQL 查询
execute_sql_query() {
    local query=$1
    
    PGPASSWORD=$DB_PASSWORD psql \
        -h $DB_HOST \
        -p $DB_PORT \
        -U $DB_USER \
        -d $DB_NAME \
        -t -A \
        -c "$query"
}

# 检查数据库连接
check_db_connection() {
    log_info "Checking database connection..."
    
    if PGPASSWORD=$DB_PASSWORD psql \
        -h $DB_HOST \
        -p $DB_PORT \
        -U $DB_USER \
        -d $DB_NAME \
        -c "SELECT 1" > /dev/null 2>&1; then
        log_success "Database connection successful"
        return 0
    else
        log_error "Cannot connect to database"
        log_error "Host: $DB_HOST:$DB_PORT, Database: $DB_NAME, User: $DB_USER"
        return 1
    fi
}

# 备份数据
backup_data() {
    log_info "Creating backup..."
    
    local backup_file="/tmp/qc_rules_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    PGPASSWORD=$DB_PASSWORD pg_dump \
        -h $DB_HOST \
        -p $DB_PORT \
        -U $DB_USER \
        -d $DB_NAME \
        -t qc_rules \
        -f "$backup_file" 2>&1
    
    if [ $? -eq 0 ]; then
        log_success "Backup created: $backup_file"
        echo "$backup_file"
        return 0
    else
        log_warning "Backup failed (table may not exist yet)"
        return 1
    fi
}

# 主测试流程
main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  Testing Migration 009: Department QC Rules                ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    
    # 1. 检查数据库连接
    if ! check_db_connection; then
        log_error "Please check your database connection settings"
        exit 1
    fi
    
    # 2. 备份数据
    BACKUP_FILE=$(backup_data)
    
    # 3. 执行迁移
    echo ""
    log_info "Step 1: Executing migration..."
    if ! execute_sql_file "$SCRIPT_DIR/009_department_qc_rules.sql" "Migration 009"; then
        log_error "Migration failed. Please check the output above."
        exit 1
    fi
    
    # 4. 验证迁移
    echo ""
    log_info "Step 2: Verifying migration..."
    if ! execute_sql_file "$SCRIPT_DIR/verify_009.sql" "Verification"; then
        log_error "Verification failed. Please check the output above."
        exit 1
    fi
    
    # 5. 测试 RPC 函数
    echo ""
    log_info "Step 3: Testing RPC function..."
    
    local dept_id=$(execute_sql_query "SELECT id FROM departments LIMIT 1")
    if [ -n "$dept_id" ]; then
        local rule_count=$(execute_sql_query "SELECT COUNT(*) FROM get_applicable_qc_rules('$dept_id', NULL, NOW())")
        log_success "RPC function returned $rule_count rules"
    else
        log_warning "No departments found, skipping RPC test"
    fi
    
    # 6. 询问是否测试回滚
    echo ""
    read -p "Do you want to test rollback? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Step 4: Testing rollback..."
        if ! execute_sql_file "$SCRIPT_DIR/009_department_qc_rules_rollback.sql" "Rollback"; then
            log_error "Rollback failed. Please check the output above."
            exit 1
        fi
        
        # 验证回滚
        echo ""
        log_info "Verifying rollback..."
        
        local column_count=$(execute_sql_query "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'qc_rules' AND column_name IN ('scope', 'department_id', 'parent_rule_id')")
        
        if [ "$column_count" -eq "0" ]; then
            log_success "Rollback verified: columns removed"
        else
            log_error "Rollback verification failed: $column_count columns still exist"
        fi
        
        # 询问是否重新执行迁移
        echo ""
        read -p "Do you want to re-apply the migration? (y/N): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Re-applying migration..."
            if ! execute_sql_file "$SCRIPT_DIR/009_department_qc_rules.sql" "Migration 009 (re-apply)"; then
                log_error "Re-apply failed. Please check the output above."
                exit 1
            fi
            log_success "Migration re-applied successfully"
        fi
    fi
    
    # 7. 总结
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  ✅ Testing Completed Successfully!                       ║"
    echo "╠════════════════════════════════════════════════════════════╣"
    echo "║  Summary:                                                  ║"
    echo "║  • Migration executed successfully                         ║"
    echo "║  • Verification passed                                     ║"
    echo "║  • RPC function tested                                     ║"
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "║  • Rollback tested                                         ║"
    fi
    echo "╠════════════════════════════════════════════════════════════╣"
    echo "║  Next Steps:                                               ║"
    echo "║  1. Review the migration output above                      ║"
    echo "║  2. Check /tmp/migration_009_output.log for details        ║"
    if [ -n "$BACKUP_FILE" ]; then
        echo "║  3. Backup file: $BACKUP_FILE"
    fi
    echo "║  4. Proceed to backend API development                     ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
}

# 执行主流程
main "$@"

