#!/bin/bash

# 医疗质控系统快速部署脚本
# 版本: 2.0.0
# 创建时间: 2024-12-25

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo -e "${BLUE}🚀 医疗质控系统快速部署脚本${NC}"
echo -e "${BLUE}📁 项目目录: ${PROJECT_ROOT}${NC}"
echo "=============================================="

# 检查系统环境
check_environment() {
    echo -e "\n${YELLOW}🔍 检查系统环境...${NC}"
    
    # 检查 Node.js
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version)
        echo -e "✅ Node.js: ${NODE_VERSION}"
    else
        echo -e "${RED}❌ Node.js 未安装，请先安装 Node.js >= 18.0.0${NC}"
        exit 1
    fi
    
    # 检查 Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version)
        echo -e "✅ Python: ${PYTHON_VERSION}"
    elif command -v python &> /dev/null; then
        PYTHON_VERSION=$(python --version)
        echo -e "✅ Python: ${PYTHON_VERSION}"
    else
        echo -e "${RED}❌ Python 未安装，请先安装 Python >= 3.10${NC}"
        exit 1
    fi
    
    # 检查包管理器
    if command -v pnpm &> /dev/null; then
        PNPM_VERSION=$(pnpm --version)
        echo -e "✅ pnpm: ${PNPM_VERSION}"
        PACKAGE_MANAGER="pnpm"
    elif command -v npm &> /dev/null; then
        NPM_VERSION=$(npm --version)
        echo -e "✅ npm: ${NPM_VERSION}"
        PACKAGE_MANAGER="npm"
    else
        echo -e "${RED}❌ 未找到包管理器，请先安装 npm 或 pnpm${NC}"
        exit 1
    fi
}

# 检查项目结构
check_project_structure() {
    echo -e "\n${YELLOW}📂 检查项目结构...${NC}"
    
    # 检查关键目录
    REQUIRED_DIRS=("src" "production_system" "database" "docs" "tools")
    for dir in "${REQUIRED_DIRS[@]}"; do
        if [ -d "${PROJECT_ROOT}/${dir}" ]; then
            echo -e "✅ ${dir}/ 目录存在"
        else
            echo -e "${RED}❌ ${dir}/ 目录不存在${NC}"
            exit 1
        fi
    done
    
    # 检查关键文件
    REQUIRED_FILES=("package.json" "production_system/main.py" "production_system/requirements.txt")
    for file in "${REQUIRED_FILES[@]}"; do
        if [ -f "${PROJECT_ROOT}/${file}" ]; then
            echo -e "✅ ${file} 文件存在"
        else
            echo -e "${RED}❌ ${file} 文件不存在${NC}"
            exit 1
        fi
    done
}

# 安装前端依赖
install_frontend_dependencies() {
    echo -e "\n${YELLOW}📦 安装前端依赖...${NC}"
    
    cd "${PROJECT_ROOT}"
    
    if [ "$PACKAGE_MANAGER" = "pnpm" ]; then
        echo -e "使用 pnpm 安装依赖..."
        pnpm install
    else
        echo -e "使用 npm 安装依赖..."
        npm install
    fi
    
    echo -e "${GREEN}✅ 前端依赖安装完成${NC}"
}

# 安装后端依赖
install_backend_dependencies() {
    echo -e "\n${YELLOW}🔧 安装后端依赖...${NC}"
    
    cd "${PROJECT_ROOT}/production_system"
    
    # 检查是否在虚拟环境中
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        echo -e "✅ 检测到虚拟环境: $VIRTUAL_ENV"
    else
        echo -e "${YELLOW}⚠️  未检测到虚拟环境，建议使用虚拟环境${NC}"
    fi
    
    # 安装依赖
    if command -v pip3 &> /dev/null; then
        pip3 install -r requirements.txt
    else
        pip install -r requirements.txt
    fi
    
    echo -e "${GREEN}✅ 后端依赖安装完成${NC}"
}

# 检查环境变量配置
check_environment_config() {
    echo -e "\n${YELLOW}⚙️  检查环境变量配置...${NC}"
    
    ENV_FILE="${PROJECT_ROOT}/.env"
    
    if [ -f "$ENV_FILE" ]; then
        echo -e "✅ .env 文件存在"
        
        # 检查关键配置
        if grep -q "VITE_SUPABASE_URL" "$ENV_FILE"; then
            echo -e "✅ Supabase URL 已配置"
        else
            echo -e "${YELLOW}⚠️  VITE_SUPABASE_URL 未配置${NC}"
        fi
        
        if grep -q "VITE_SUPABASE_ANON_KEY" "$ENV_FILE"; then
            echo -e "✅ Supabase Key 已配置"
        else
            echo -e "${YELLOW}⚠️  VITE_SUPABASE_ANON_KEY 未配置${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  .env 文件不存在，将创建示例文件${NC}"
        
        cat > "$ENV_FILE" << EOF
# Supabase 配置
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key

# OpenAI 配置 (可选，用于 AI 功能)
OPENAI_API_KEY=your-openai-key

# 开发环境配置
NODE_ENV=development
EOF
        
        echo -e "${GREEN}✅ 已创建 .env 示例文件，请填入正确的配置${NC}"
    fi
}

# 数据库初始化提示
database_setup_guide() {
    echo -e "\n${YELLOW}🗄️  数据库设置指南${NC}"
    echo -e "请在 Supabase SQL Editor 中按顺序执行以下脚本："
    echo -e "1. ${BLUE}database/setup/database_init_complete.sql${NC}"
    echo -e "2. ${BLUE}database/setup/database_init_part2.sql${NC}"
    echo -e "3. ${BLUE}database/setup/database_init_part3.sql${NC}"
    echo -e "4. ${BLUE}database/setup/verify_database.sql${NC}"
    echo -e "\n如果遇到问题，可以执行修复脚本："
    echo -e "- ${BLUE}database/fixes/database_simple_fix.sql${NC}"
    echo -e "- ${BLUE}database/fixes/database_complete_setup.sql${NC}"
}

# 启动服务
start_services() {
    echo -e "\n${YELLOW}🚀 准备启动服务...${NC}"
    
    # 询问用户是否要启动服务
    read -p "是否现在启动前端和后端服务？(y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "\n${GREEN}🎉 启动服务中...${NC}"
        
        # 创建启动脚本
        cat > "${PROJECT_ROOT}/start_dev.sh" << EOF
#!/bin/bash

# 启动开发服务器脚本

echo "🚀 启动医疗质控系统开发服务器"

# 启动后端服务 (后台运行)
echo "📡 启动后端服务..."
cd "${PROJECT_ROOT}/production_system"
python main.py &
BACKEND_PID=\$!

# 等待后端启动
sleep 3

# 启动前端服务
echo "🎨 启动前端服务..."
cd "${PROJECT_ROOT}"
if command -v pnpm &> /dev/null; then
    pnpm dev
else
    npm run dev
fi

# 清理后台进程
kill \$BACKEND_PID 2>/dev/null || true
EOF
        
        chmod +x "${PROJECT_ROOT}/start_dev.sh"
        
        echo -e "${GREEN}✅ 已创建启动脚本: start_dev.sh${NC}"
        echo -e "${BLUE}💡 使用 ./start_dev.sh 启动开发服务器${NC}"
        
        # 显示访问地址
        echo -e "\n${GREEN}🌐 服务访问地址:${NC}"
        echo -e "前端: ${BLUE}http://localhost:5173${NC}"
        echo -e "后端: ${BLUE}http://localhost:8001${NC}"
        echo -e "API 文档: ${BLUE}http://localhost:8001/docs${NC}"
    else
        echo -e "${BLUE}💡 稍后可以手动启动服务${NC}"
    fi
}

# 显示部署总结
show_deployment_summary() {
    echo -e "\n=============================================="
    echo -e "${GREEN}🎉 部署完成！${NC}"
    echo -e "=============================================="
    
    echo -e "\n${YELLOW}📋 部署总结:${NC}"
    echo -e "✅ 系统环境检查完成"
    echo -e "✅ 项目结构验证通过"
    echo -e "✅ 前端依赖安装完成"
    echo -e "✅ 后端依赖安装完成"
    echo -e "✅ 环境配置检查完成"
    
    echo -e "\n${YELLOW}📝 下一步操作:${NC}"
    echo -e "1. 配置 .env 文件中的 Supabase 连接信息"
    echo -e "2. 在 Supabase 中执行数据库初始化脚本"
    echo -e "3. 运行 ./start_dev.sh 启动开发服务器"
    
    echo -e "\n${YELLOW}📚 相关文档:${NC}"
    echo -e "- 部署指南: ${BLUE}docs/deployment/NEW_SUPABASE_DEPLOYMENT_GUIDE.md${NC}"
    echo -e "- 集成验证报告: ${BLUE}INTEGRATION_VERIFICATION_REPORT.md${NC}"
    echo -e "- 项目结构说明: ${BLUE}PROJECT_STRUCTURE.md${NC}"
    
    echo -e "\n${GREEN}🚀 系统已准备就绪，可以开始使用！${NC}"
}

# 主函数
main() {
    cd "$PROJECT_ROOT"
    
    check_environment
    check_project_structure
    install_frontend_dependencies
    install_backend_dependencies
    check_environment_config
    database_setup_guide
    start_services
    show_deployment_summary
}

# 错误处理
trap 'echo -e "\n${RED}❌ 部署过程中发生错误，请检查上面的错误信息${NC}"; exit 1' ERR

# 运行主函数
main "$@"
