#!/bin/bash

# 人工审核模块演示启动脚本
# 用于快速启动和演示审核模块功能

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="/home/ubuntu/KAG/kag/examples/002medqc/MedQC0817"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  人工审核模块演示启动脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查项目目录
if [ ! -d "$PROJECT_ROOT" ]; then
    echo -e "${RED}错误: 项目目录不存在: $PROJECT_ROOT${NC}"
    exit 1
fi

cd "$PROJECT_ROOT"

# 检查必要文件
echo -e "${YELLOW}检查项目文件...${NC}"

required_files=(
    "src/types/audit-module.ts"
    "src/services/audit-task-service.ts"
    "src/services/audit-result-service.ts"
    "src/services/notification-service.ts"
    "src/components/audit/MultiLevelAuditTabs.vue"
    "src/components/notification/NotificationCenter.vue"
    "src/views/AuditModuleDemo.vue"
    "database/migrations/20241224_create_audit_tables.sql"
)

missing_files=()
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        missing_files+=("$file")
    fi
done

if [ ${#missing_files[@]} -gt 0 ]; then
    echo -e "${RED}错误: 以下必要文件缺失:${NC}"
    for file in "${missing_files[@]}"; do
        echo -e "${RED}  - $file${NC}"
    done
    exit 1
fi

echo -e "${GREEN}✓ 所有必要文件检查通过${NC}"

# 检查依赖
echo -e "${YELLOW}检查项目依赖...${NC}"

if [ ! -f "package.json" ]; then
    echo -e "${RED}错误: package.json 文件不存在${NC}"
    exit 1
fi

if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}安装项目依赖...${NC}"
    npm install
    if [ $? -ne 0 ]; then
        echo -e "${RED}错误: 依赖安装失败${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ 项目依赖检查通过${NC}"

# 检查数据库连接
echo -e "${YELLOW}检查数据库连接...${NC}"

# 检查环境变量
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_ANON_KEY" ]; then
    echo -e "${YELLOW}警告: Supabase环境变量未设置${NC}"
    echo -e "${YELLOW}请确保设置以下环境变量:${NC}"
    echo -e "${YELLOW}  - SUPABASE_URL${NC}"
    echo -e "${YELLOW}  - SUPABASE_ANON_KEY${NC}"
    echo ""
    echo -e "${YELLOW}或者在 .env 文件中配置这些变量${NC}"
    echo ""
fi

# 数据库初始化选项
echo -e "${YELLOW}是否需要初始化数据库表结构? (y/n)${NC}"
read -r init_db

if [ "$init_db" = "y" ] || [ "$init_db" = "Y" ]; then
    echo -e "${YELLOW}初始化数据库表结构...${NC}"
    
    # 检查是否有psql命令
    if command -v psql &> /dev/null; then
        echo -e "${BLUE}请手动执行以下SQL脚本:${NC}"
        echo -e "${BLUE}  psql -h <your-host> -U <your-user> -d <your-db> -f database/migrations/20241224_create_audit_tables.sql${NC}"
    else
        echo -e "${BLUE}请在Supabase控制台的SQL编辑器中执行以下文件:${NC}"
        echo -e "${BLUE}  database/migrations/20241224_create_audit_tables.sql${NC}"
    fi
    
    echo -e "${YELLOW}按任意键继续...${NC}"
    read -r
fi

# 构建项目
echo -e "${YELLOW}构建项目...${NC}"

if [ -f "vite.config.ts" ] || [ -f "vite.config.js" ]; then
    npm run build
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}警告: 构建失败，但将继续启动开发服务器${NC}"
    fi
else
    echo -e "${YELLOW}未找到Vite配置文件，跳过构建步骤${NC}"
fi

# 运行测试
echo -e "${YELLOW}是否运行测试? (y/n)${NC}"
read -r run_tests

if [ "$run_tests" = "y" ] || [ "$run_tests" = "Y" ]; then
    echo -e "${YELLOW}运行审核模块测试...${NC}"
    
    if [ -f "tests/audit-module.test.ts" ]; then
        npm run test tests/audit-module.test.ts 2>/dev/null || {
            echo -e "${YELLOW}测试命令失败，可能需要配置测试环境${NC}"
        }
    else
        echo -e "${YELLOW}测试文件不存在，跳过测试${NC}"
    fi
fi

# 启动开发服务器
echo -e "${YELLOW}启动开发服务器...${NC}"

# 检查端口是否被占用
PORT=3000
if command -v lsof &> /dev/null; then
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
        echo -e "${YELLOW}端口 $PORT 已被占用，尝试使用其他端口...${NC}"
        PORT=3001
    fi
fi

# 显示启动信息
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  审核模块演示即将启动${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}功能特性:${NC}"
echo -e "${GREEN}  ✓ 审核任务管理系统${NC}"
echo -e "${GREEN}  ✓ 智能抽样算法${NC}"
echo -e "${GREEN}  ✓ 多级审核流程${NC}"
echo -e "${GREEN}  ✓ AI辅助缺陷识别${NC}"
echo -e "${GREEN}  ✓ 实时消息通知${NC}"
echo -e "${GREEN}  ✓ LLM集成质控${NC}"
echo ""
echo -e "${GREEN}访问地址:${NC}"
echo -e "${GREEN}  主页: http://localhost:$PORT${NC}"
echo -e "${GREEN}  演示页面: http://localhost:$PORT/audit-module-demo${NC}"
echo ""
echo -e "${YELLOW}启动中...${NC}"

# 启动服务器
if [ -f "package.json" ]; then
    # 检查是否有dev脚本
    if npm run | grep -q "dev"; then
        npm run dev -- --port $PORT
    elif npm run | grep -q "serve"; then
        npm run serve -- --port $PORT
    else
        echo -e "${RED}错误: 未找到开发服务器启动脚本${NC}"
        echo -e "${YELLOW}请手动启动开发服务器${NC}"
        exit 1
    fi
else
    echo -e "${RED}错误: package.json 文件不存在${NC}"
    exit 1
fi

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}正在关闭服务器...${NC}"
    # 这里可以添加清理逻辑
    echo -e "${GREEN}服务器已关闭${NC}"
    exit 0
}

# 捕获中断信号
trap cleanup SIGINT SIGTERM

# 等待用户中断
wait
