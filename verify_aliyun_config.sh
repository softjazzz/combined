#!/bin/bash

echo "============================================================"
echo "🔍 验证阿里云 Supabase 配置"
echo "============================================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查前端配置
echo "📋 检查前端配置 (apps/medqc-web/.env)"
echo "------------------------------------------------------------"

FRONTEND_ENV="apps/medqc-web/.env"
if [ -f "$FRONTEND_ENV" ]; then
    FRONTEND_URL=$(grep "^VITE_SUPABASE_URL=" "$FRONTEND_ENV" | cut -d'=' -f2)
    
    if [[ "$FRONTEND_URL" == *"sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"* ]]; then
        echo -e "${GREEN}✅ 前端已配置为阿里云 Supabase${NC}"
        echo "   URL: $FRONTEND_URL"
    elif [[ "$FRONTEND_URL" == *"dgsdkdbjpucyawnyfbdu.supabase.co"* ]]; then
        echo -e "${RED}❌ 前端仍使用海外 Supabase${NC}"
        echo "   URL: $FRONTEND_URL"
    else
        echo -e "${YELLOW}⚠️  前端配置未知${NC}"
        echo "   URL: $FRONTEND_URL"
    fi
else
    echo -e "${RED}❌ 前端 .env 文件不存在${NC}"
fi

echo ""

# 检查后端配置
echo "📋 检查后端配置 (apps/medqc-web/backend/.env)"
echo "------------------------------------------------------------"

BACKEND_ENV="apps/medqc-web/backend/.env"
if [ -f "$BACKEND_ENV" ]; then
    BACKEND_URL=$(grep "^SUPABASE_URL=" "$BACKEND_ENV" | cut -d'=' -f2)
    
    if [[ "$BACKEND_URL" == *"sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"* ]]; then
        echo -e "${GREEN}✅ 后端已配置为阿里云 Supabase${NC}"
        echo "   URL: $BACKEND_URL"
    elif [[ "$BACKEND_URL" == *"dgsdkdbjpucyawnyfbdu.supabase.co"* ]]; then
        echo -e "${RED}❌ 后端仍使用海外 Supabase${NC}"
        echo "   URL: $BACKEND_URL"
    else
        echo -e "${YELLOW}⚠️  后端配置未知${NC}"
        echo "   URL: $BACKEND_URL"
    fi
else
    echo -e "${RED}❌ 后端 .env 文件不存在${NC}"
fi

echo ""
echo "============================================================"
echo "📊 配置总结"
echo "============================================================"

if [[ "$FRONTEND_URL" == *"sbp-a41klzf2d6lvsjoj"* ]] && [[ "$BACKEND_URL" == *"sbp-a41klzf2d6lvsjoj"* ]]; then
    echo -e "${GREEN}✅ 前端和后端都已配置为阿里云 Supabase${NC}"
    echo -e "${GREEN}✅ 可以开始测试了！${NC}"
    echo ""
    echo "🚀 启动步骤:"
    echo "  1. 启动后端: cd apps/medqc-web/backend && uvicorn app.main:app --reload"
    echo "  2. 启动前端: cd apps/medqc-web && pnpm dev"
    echo "  3. 访问应用: http://localhost:3000"
    echo ""
    echo "📝 测试页面:"
    echo "  - 病历列表: http://localhost:3000/medical-records"
    echo "  - 质控演示: http://localhost:3000/demo/qc-demo"
else
    echo -e "${RED}❌ 配置不一致或未完成迁移${NC}"
    echo ""
    echo "请检查以下文件:"
    echo "  - apps/medqc-web/.env"
    echo "  - apps/medqc-web/backend/.env"
fi

echo ""
echo "============================================================"

