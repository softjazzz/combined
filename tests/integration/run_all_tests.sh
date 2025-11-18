#!/bin/bash

# ============================================================================
# 科室级质控规则 - 集成测试执行脚本
# ============================================================================
#
# 用途：自动执行所有集成测试和性能测试
#
# 使用方法：
#   chmod +x run_all_tests.sh
#   ./run_all_tests.sh
#
# ============================================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/apps/medqc-web/backend"
REPORT_DIR="$SCRIPT_DIR/reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# 创建报告目录
mkdir -p "$REPORT_DIR"

# ============================================================================
# 辅助函数
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_header() {
    echo ""
    echo "========================================"
    echo "$1"
    echo "========================================"
    echo ""
}

# ============================================================================
# 前置检查
# ============================================================================

check_prerequisites() {
    print_header "前置条件检查"
    
    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 未安装"
        exit 1
    fi
    log_success "Python 3: $(python3 --version)"
    
    # 检查 psql
    if ! command -v psql &> /dev/null; then
        log_warning "psql 未安装，跳过数据库性能测试"
    else
        log_success "PostgreSQL: $(psql --version)"
    fi
    
    # 检查后端服务是否运行
    if curl -s http://localhost:8001/api/health > /dev/null 2>&1; then
        log_success "后端 API 服务正在运行"
    else
        log_error "后端 API 服务未运行，请先启动后端服务"
        log_info "启动命令: cd $BACKEND_DIR && python -m uvicorn app.main:app --reload --port 8001"
        exit 1
    fi
    
    # 检查 Python 依赖
    if ! python3 -c "import requests" 2>/dev/null; then
        log_warning "requests 库未安装，正在安装..."
        pip3 install requests
    fi
    
    log_success "前置条件检查通过"
}

# ============================================================================
# 测试执行
# ============================================================================

run_database_setup() {
    print_header "步骤 1: 准备测试数据"
    
    if command -v psql &> /dev/null; then
        log_info "执行测试数据准备脚本..."
        
        # 从环境变量获取数据库连接信息
        DB_HOST="${DB_HOST:-localhost}"
        DB_PORT="${DB_PORT:-5432}"
        DB_NAME="${DB_NAME:-postgres}"
        DB_USER="${DB_USER:-postgres}"
        
        if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -f "$SCRIPT_DIR/prepare_test_data.sql" > "$REPORT_DIR/db_setup_$TIMESTAMP.log" 2>&1; then
            log_success "测试数据准备完成"
        else
            log_error "测试数据准备失败，查看日志: $REPORT_DIR/db_setup_$TIMESTAMP.log"
            return 1
        fi
    else
        log_warning "跳过数据库测试数据准备（psql 未安装）"
    fi
}

run_e2e_tests() {
    print_header "步骤 2: 端到端测试"
    
    log_info "执行端到端测试..."
    
    if python3 "$SCRIPT_DIR/test_department_rules_e2e.py" > "$REPORT_DIR/e2e_test_$TIMESTAMP.log" 2>&1; then
        log_success "端到端测试通过"
        cat "$REPORT_DIR/e2e_test_$TIMESTAMP.log"
        return 0
    else
        log_error "端到端测试失败"
        cat "$REPORT_DIR/e2e_test_$TIMESTAMP.log"
        return 1
    fi
}

run_performance_tests() {
    print_header "步骤 3: 性能测试"
    
    log_info "执行性能测试..."
    
    if python3 "$SCRIPT_DIR/test_performance.py" > "$REPORT_DIR/performance_test_$TIMESTAMP.log" 2>&1; then
        log_success "性能测试通过"
        cat "$REPORT_DIR/performance_test_$TIMESTAMP.log"
        return 0
    else
        log_warning "性能测试未达标"
        cat "$REPORT_DIR/performance_test_$TIMESTAMP.log"
        return 1
    fi
}

run_database_performance_analysis() {
    print_header "步骤 4: 数据库性能分析"
    
    if command -v psql &> /dev/null; then
        log_info "执行数据库性能分析..."
        
        DB_HOST="${DB_HOST:-localhost}"
        DB_PORT="${DB_PORT:-5432}"
        DB_NAME="${DB_NAME:-postgres}"
        DB_USER="${DB_USER:-postgres}"
        
        if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -f "$SCRIPT_DIR/analyze_db_performance.sql" > "$REPORT_DIR/db_performance_$TIMESTAMP.log" 2>&1; then
            log_success "数据库性能分析完成"
            cat "$REPORT_DIR/db_performance_$TIMESTAMP.log"
        else
            log_warning "数据库性能分析失败"
        fi
    else
        log_warning "跳过数据库性能分析（psql 未安装）"
    fi
}

# ============================================================================
# 生成测试报告
# ============================================================================

generate_report() {
    print_header "步骤 5: 生成测试报告"
    
    REPORT_FILE="$REPORT_DIR/integration_test_report_$TIMESTAMP.md"
    
    cat > "$REPORT_FILE" << EOF
# 科室级质控规则 - 集成测试报告

**测试时间**: $(date +"%Y-%m-%d %H:%M:%S")  
**测试环境**: 
- 后端 API: http://localhost:8001
- 数据库: ${DB_HOST:-localhost}:${DB_PORT:-5432}

---

## 测试结果总结

| 测试类型 | 状态 | 详细日志 |
|---------|------|---------|
| 端到端测试 | $E2E_STATUS | [查看日志](e2e_test_$TIMESTAMP.log) |
| 性能测试 | $PERF_STATUS | [查看日志](performance_test_$TIMESTAMP.log) |
| 数据库性能分析 | $DB_PERF_STATUS | [查看日志](db_performance_$TIMESTAMP.log) |

---

## 端到端测试详情

\`\`\`
$(cat "$REPORT_DIR/e2e_test_$TIMESTAMP.log" 2>/dev/null || echo "测试日志不可用")
\`\`\`

---

## 性能测试详情

\`\`\`
$(cat "$REPORT_DIR/performance_test_$TIMESTAMP.log" 2>/dev/null || echo "测试日志不可用")
\`\`\`

---

## 数据库性能分析

\`\`\`
$(cat "$REPORT_DIR/db_performance_$TIMESTAMP.log" 2>/dev/null || echo "分析日志不可用")
\`\`\`

---

## 发现的问题

<!-- 在这里记录测试中发现的问题 -->

---

## 优化建议

<!-- 在这里记录性能优化建议 -->

---

**报告生成时间**: $(date +"%Y-%m-%d %H:%M:%S")
EOF
    
    log_success "测试报告已生成: $REPORT_FILE"
}

# ============================================================================
# 主函数
# ============================================================================

main() {
    print_header "科室级质控规则 - 集成测试"
    
    # 前置检查
    check_prerequisites
    
    # 初始化状态变量
    E2E_STATUS="❌ 失败"
    PERF_STATUS="❌ 失败"
    DB_PERF_STATUS="⚠️ 跳过"
    
    # 执行测试
    if run_database_setup; then
        DB_SETUP_STATUS="✅ 成功"
    fi
    
    if run_e2e_tests; then
        E2E_STATUS="✅ 通过"
    fi
    
    if run_performance_tests; then
        PERF_STATUS="✅ 通过"
    else
        PERF_STATUS="⚠️ 未达标"
    fi
    
    if run_database_performance_analysis; then
        DB_PERF_STATUS="✅ 完成"
    fi
    
    # 生成报告
    generate_report
    
    # 打印总结
    print_header "测试完成"
    
    log_info "测试报告: $REPORT_FILE"
    log_info "日志目录: $REPORT_DIR"
    
    echo ""
    echo "测试结果:"
    echo "  - 端到端测试: $E2E_STATUS"
    echo "  - 性能测试: $PERF_STATUS"
    echo "  - 数据库性能分析: $DB_PERF_STATUS"
    echo ""
    
    # 返回退出码
    if [[ "$E2E_STATUS" == "✅ 通过" ]]; then
        exit 0
    else
        exit 1
    fi
}

# 执行主函数
main "$@"

