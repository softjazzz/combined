#!/bin/bash

# MedQC 服务启动脚本
# 用法: ./start-services.sh [frontend|backend|all]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目路径
PROJECT_ROOT="/home/ubuntu/coding/health-qc-monorepo"
MEDQC_ROOT="$PROJECT_ROOT/apps/medqc-web"
BACKEND_ROOT="$MEDQC_ROOT/backend"

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

# 检查端口是否被占用
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # 端口被占用
    else
        return 1  # 端口空闲
    fi
}

# 等待端口启动
wait_for_port() {
    local port=$1
    local service=$2
    local max_attempts=30
    local attempt=1
    
    log_info "等待 $service 在端口 $port 启动..."
    
    while [ $attempt -le $max_attempts ]; do
        if check_port $port; then
            log_success "$service 已在端口 $port 启动"
            return 0
        fi
        
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    
    log_error "$service 启动超时 (端口 $port)"
    return 1
}

# 启动前端服务
start_frontend() {
    log_info "启动前端服务..."
    
    # 检查端口是否被占用
    if check_port 3000; then
        log_warning "端口 3000 已被占用，尝试停止现有服务..."
        pkill -f "vite.*3000" 2>/dev/null || true
        sleep 2
    fi
    
    # 进入项目根目录
    cd "$PROJECT_ROOT"
    
    # 启动前端
    log_info "执行: pnpm dev:medqc"
    nohup pnpm dev:medqc > "$MEDQC_ROOT/frontend.log" 2>&1 &
    
    # 等待启动
    if wait_for_port 3000 "前端服务"; then
        log_success "前端服务启动成功"
        log_info "访问地址: http://localhost:3000"
        log_info "日志文件: $MEDQC_ROOT/frontend.log"
    else
        log_error "前端服务启动失败"
        return 1
    fi
}

# 启动后端服务
start_backend() {
    log_info "启动后端服务..."
    
    # 检查端口是否被占用
    if check_port 8001; then
        log_warning "端口 8001 已被占用，尝试停止现有服务..."
        pkill -f "uvicorn.*8001" 2>/dev/null || true
        sleep 2
    fi
    
    # 检查虚拟环境
    if [ ! -d "$BACKEND_ROOT/venv" ]; then
        log_error "虚拟环境不存在: $BACKEND_ROOT/venv"
        log_info "请先创建虚拟环境: python3 -m venv venv"
        return 1
    fi
    
    # 进入后端目录
    cd "$BACKEND_ROOT"
    
    # 激活虚拟环境并启动服务
    log_info "激活虚拟环境并启动后端服务..."
    nohup bash -c "
        source venv/bin/activate && \
        export JWT_SECRET=dev-secret && \
        uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
    " > "$BACKEND_ROOT/backend.log" 2>&1 &
    
    # 等待启动
    if wait_for_port 8001 "后端服务"; then
        log_success "后端服务启动成功"
        log_info "API地址: http://localhost:8001"
        log_info "API文档: http://localhost:8001/docs"
        log_info "健康检查: http://localhost:8001/api/health"
        log_info "日志文件: $BACKEND_ROOT/backend.log"
        
        # 测试健康检查
        sleep 2
        if curl -s http://localhost:8001/api/health >/dev/null 2>&1; then
            log_success "后端健康检查通过"
        else
            log_warning "后端健康检查失败，请查看日志"
        fi
    else
        log_error "后端服务启动失败"
        return 1
    fi
}

# 停止服务
stop_services() {
    log_info "停止所有服务..."
    
    # 停止前端
    if check_port 3000; then
        log_info "停止前端服务 (端口 3000)..."
        pkill -f "vite.*3000" 2>/dev/null || true
    fi
    
    # 停止后端
    if check_port 8001; then
        log_info "停止后端服务 (端口 8001)..."
        pkill -f "uvicorn.*8001" 2>/dev/null || true
    fi
    
    sleep 2
    log_success "服务已停止"
}

# 检查服务状态
check_status() {
    log_info "检查服务状态..."
    
    echo -e "\n${BLUE}=== 端口状态 ===${NC}"
    if check_port 3000; then
        echo -e "前端 (3000): ${GREEN}运行中${NC}"
    else
        echo -e "前端 (3000): ${RED}未运行${NC}"
    fi
    
    if check_port 8001; then
        echo -e "后端 (8001): ${GREEN}运行中${NC}"
    else
        echo -e "后端 (8001): ${RED}未运行${NC}"
    fi
    
    echo -e "\n${BLUE}=== 进程状态 ===${NC}"
    ps aux | grep -E "(vite.*3000|uvicorn.*8001)" | grep -v grep || echo "无相关进程运行"
    
    echo -e "\n${BLUE}=== 健康检查 ===${NC}"
    if check_port 3000; then
        if curl -s http://localhost:3000 >/dev/null 2>&1; then
            echo -e "前端健康检查: ${GREEN}通过${NC}"
        else
            echo -e "前端健康检查: ${RED}失败${NC}"
        fi
    fi
    
    if check_port 8001; then
        if curl -s http://localhost:8001/api/health >/dev/null 2>&1; then
            echo -e "后端健康检查: ${GREEN}通过${NC}"
        else
            echo -e "后端健康检查: ${RED}失败${NC}"
        fi
    fi
}

# 显示帮助信息
show_help() {
    echo "MedQC 服务启动脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  frontend    启动前端服务 (端口 3000)"
    echo "  backend     启动后端服务 (端口 8001)"
    echo "  all         启动所有服务 (默认)"
    echo "  stop        停止所有服务"
    echo "  status      检查服务状态"
    echo "  help        显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                # 启动所有服务"
    echo "  $0 frontend       # 仅启动前端"
    echo "  $0 backend        # 仅启动后端"
    echo "  $0 stop           # 停止所有服务"
    echo "  $0 status         # 检查状态"
}

# 主函数
main() {
    local command=${1:-all}
    
    case $command in
        "frontend")
            start_frontend
            ;;
        "backend")
            start_backend
            ;;
        "all")
            log_info "启动所有服务..."
            start_backend
            sleep 3
            start_frontend
            echo ""
            log_success "所有服务启动完成"
            check_status
            ;;
        "stop")
            stop_services
            ;;
        "status")
            check_status
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "未知选项: $command"
            show_help
            exit 1
            ;;
    esac
}

# 检查必要的命令
check_dependencies() {
    local missing_deps=()
    
    if ! command -v pnpm >/dev/null 2>&1; then
        missing_deps+=("pnpm")
    fi
    
    if ! command -v python3 >/dev/null 2>&1; then
        missing_deps+=("python3")
    fi
    
    if ! command -v curl >/dev/null 2>&1; then
        missing_deps+=("curl")
    fi
    
    if ! command -v lsof >/dev/null 2>&1; then
        missing_deps+=("lsof")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "缺少必要的依赖: ${missing_deps[*]}"
        log_info "请安装缺少的依赖后重试"
        exit 1
    fi
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    check_dependencies
    main "$@"
fi
