#!/bin/bash

# 医疗质控系统 Monorepo - 开发环境管理脚本
# 使用方法: ./dev-env.sh [command]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 端口配置
MEDQC_PORT=3000
YIBAO_PORT=3008
MEDQC_API_PORT=8001
YIBAO_API_PORT=8008

# 项目路径
MEDQC_PATH="./apps/medqc-web"
YIBAO_PATH="./apps/yibao-web"

# 日志函数
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# 检查端口是否被占用
check_port() {
    local port=$1
    if lsof -ti:$port > /dev/null 2>&1; then
        return 0  # 端口被占用
    else
        return 1  # 端口可用
    fi
}

# 杀死占用端口的进程
kill_port() {
    local port=$1
    if check_port $port; then
        warn "端口 $port 被占用，正在清理..."
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
        sleep 1
        if check_port $port; then
            error "无法清理端口 $port"
            return 1
        else
            log "端口 $port 已清理"
        fi
    fi
}

# 检查项目依赖
check_dependencies() {
    log "检查项目依赖..."

    if ! command -v node &> /dev/null; then
        error "Node.js 未安装"
        exit 1
    fi

    if ! command -v pnpm &> /dev/null; then
        error "pnpm 未安装，请运行: npm install -g pnpm"
        exit 1
    fi

    log "依赖检查完成"
}

# 安装依赖
install_deps() {
    log "安装项目依赖..."
    pnpm install
    log "依赖安装完成"
}

# 初始化环境配置
init_env() {
    log "初始化环境配置..."

    # 为 medqc-web 创建 .env 文件
    if [ ! -f "$MEDQC_PATH/.env" ]; then
        if [ -f "$MEDQC_PATH/.env.template" ]; then
            cp "$MEDQC_PATH/.env.template" "$MEDQC_PATH/.env"
            log "已为 medqc-web 创建 .env 文件"
        else
            warn "medqc-web .env.template 不存在"
        fi
    fi

    # 为 yibao-web 创建 .env 文件
    if [ ! -f "$YIBAO_PATH/.env" ]; then
        if [ -f "$YIBAO_PATH/.env.template" ]; then
            cp "$YIBAO_PATH/.env.template" "$YIBAO_PATH/.env"
            log "已为 yibao-web 创建 .env 文件"
        else
            warn "yibao-web .env.template 不存在"
        fi
    fi

    log "环境配置初始化完成"
}

# 清理所有项目端口
clean_ports() {
    log "清理项目端口..."
    kill_port $MEDQC_PORT
    kill_port $YIBAO_PORT
    kill_port $MEDQC_API_PORT
    kill_port $YIBAO_API_PORT
    log "端口清理完成"
}

# 检查服务状态
check_status() {
    log "检查服务状态..."

    printf "%-20s %-10s %-20s\n" "服务" "端口" "状态"
    printf "%-20s %-10s %-20s\n" "----" "----" "----"

    if check_port $MEDQC_PORT; then
        printf "%-20s %-10s %-20s\n" "medqc-web" "$MEDQC_PORT" "🟢 运行中"
    else
        printf "%-20s %-10s %-20s\n" "medqc-web" "$MEDQC_PORT" "🔴 未运行"
    fi

    if check_port $YIBAO_PORT; then
        printf "%-20s %-10s %-20s\n" "yibao-web" "$YIBAO_PORT" "🟢 运行中"
    else
        printf "%-20s %-10s %-20s\n" "yibao-web" "$YIBAO_PORT" "🔴 未运行"
    fi

    if check_port $MEDQC_API_PORT; then
        printf "%-20s %-10s %-20s\n" "medqc-api" "$MEDQC_API_PORT" "🟢 运行中"
    else
        printf "%-20s %-10s %-20s\n" "medqc-api" "$MEDQC_API_PORT" "🔴 未运行"
    fi

    if check_port $YIBAO_API_PORT; then
        printf "%-20s %-10s %-20s\n" "yibao-api" "$YIBAO_API_PORT" "🟢 运行中"
    else
        printf "%-20s %-10s %-20s\n" "yibao-api" "$YIBAO_API_PORT" "🔴 未运行"
    fi
}

# 启动 medqc-web
start_medqc() {
    log "启动 medqc-web..."
    kill_port $MEDQC_PORT
    cd $MEDQC_PATH
    pnpm dev &
    cd - > /dev/null
    sleep 3
    if check_port $MEDQC_PORT; then
        log "medqc-web 已启动: http://localhost:$MEDQC_PORT"
    else
        error "medqc-web 启动失败"
    fi
}

# 启动 yibao-web
start_yibao() {
    log "启动 yibao-web..."
    kill_port $YIBAO_PORT
    cd $YIBAO_PATH
    pnpm dev &
    cd - > /dev/null
    sleep 3
    if check_port $YIBAO_PORT; then
        log "yibao-web 已启动: http://localhost:$YIBAO_PORT"
    else
        error "yibao-web 启动失败"
    fi
}

# 启动所有前端服务
start_all() {
    log "启动所有前端服务..."
    start_medqc
    start_yibao
    log "所有服务已启动"
    check_status
}

# 停止所有服务
stop_all() {
    log "停止所有服务..."
    clean_ports
    log "所有服务已停止"
}

# 重启所有服务
restart_all() {
    log "重启所有服务..."
    stop_all
    sleep 2
    start_all
}

# 显示帮助信息
show_help() {
    echo "医疗质控系统 Monorepo - 开发环境管理脚本"
    echo ""
    echo "使用方法:"
    echo "  $0 [command]"
    echo ""
    echo "可用命令:"
    echo "  check-deps     检查项目依赖"
    echo "  install        安装项目依赖"
    echo "  init           初始化环境配置"
    echo "  status         检查服务状态"
    echo "  clean          清理端口"
    echo "  start-medqc    启动 medqc-web"
    echo "  start-yibao    启动 yibao-web"
    echo "  start-all      启动所有前端服务"
    echo "  stop           停止所有服务"
    echo "  restart        重启所有服务"
    echo "  help           显示此帮助信息"
    echo ""
    echo "端口分配:"
    echo "  medqc-web:     http://localhost:$MEDQC_PORT"
    echo "  yibao-web:     http://localhost:$YIBAO_PORT"
    echo "  medqc-api:     http://localhost:$MEDQC_API_PORT"
    echo "  yibao-api:     http://localhost:$YIBAO_API_PORT"
}

# 主程序逻辑
main() {
    case "$1" in
        "check-deps")
            check_dependencies
            ;;
        "install")
            check_dependencies
            install_deps
            ;;
        "init")
            init_env
            ;;
        "status")
            check_status
            ;;
        "clean")
            clean_ports
            ;;
        "start-medqc")
            start_medqc
            ;;
        "start-yibao")
            start_yibao
            ;;
        "start-all"|"start")
            check_dependencies
            start_all
            ;;
        "stop")
            stop_all
            ;;
        "restart")
            restart_all
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        "")
            log "启动所有服务..."
            check_dependencies
            start_all
            ;;
        *)
            error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

# 执行主程序
main "$@"