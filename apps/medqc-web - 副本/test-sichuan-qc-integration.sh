#!/bin/bash

# 测试四川质控 API 集成
# 用途：验证新版演示页面能否正确调用四川质控引擎

set -e

echo "========================================="
echo "四川质控 API 集成测试"
echo "========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 检查后端服务
echo "1️⃣  检查后端服务..."
HEALTH_RESPONSE=$(curl -s http://localhost:8001/api/v1/health)
if echo "$HEALTH_RESPONSE" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ 后端服务正常运行${NC}"
    echo "   响应: $(echo $HEALTH_RESPONSE | jq -r '.data.status')"
else
    echo -e "${RED}❌ 后端服务异常${NC}"
    exit 1
fi
echo ""

# 2. 检查前端服务
echo "2️⃣  检查前端服务..."
if curl -s http://localhost:3000 | grep -q "病案质控系统"; then
    echo -e "${GREEN}✅ 前端服务正常运行${NC}"
else
    echo -e "${RED}❌ 前端服务异常${NC}"
    exit 1
fi
echo ""

# 3. 登录获取 token
echo "3️⃣  登录系统..."
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@medqc.com",
    "password": "admin123"
  }')

# 检查两种可能的响应格式
if echo "$LOGIN_RESPONSE" | grep -q '"access_token"'; then
    # 直接返回 token 的格式
    TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
    echo -e "${GREEN}✅ 登录成功${NC}"
    echo "   Token: ${TOKEN:0:20}..."
elif echo "$LOGIN_RESPONSE" | grep -q '"success":true'; then
    # 包装在 success/data 中的格式
    TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.data.access_token')
    echo -e "${GREEN}✅ 登录成功${NC}"
    echo "   Token: ${TOKEN:0:20}..."
else
    echo -e "${RED}❌ 登录失败${NC}"
    echo "   响应: $LOGIN_RESPONSE"
    exit 1
fi
echo ""

# 4. 测试四川质控 API
echo "4️⃣  测试四川质控 API..."
QC_RESPONSE=$(curl -s -X POST http://localhost:8001/api/v1/qc/sichuan/evaluate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "document_id": "test-doc-001",
    "document_content": "患者张三，男，45岁，因\"胸痛3小时\"入院。现病史：患者于3小时前无明显诱因出现胸痛，呈压榨性，伴大汗，持续不缓解，遂来我院急诊。既往史：高血压病史5年，规律服药。否认糖尿病、冠心病史。个人史：吸烟20年，每日1包。查体：T 36.5℃，P 88次/分，R 18次/分，BP 145/90mmHg。神志清，精神可，心肺腹查体未见明显异常。辅助检查：心电图示：V1-V4导联ST段抬高0.2-0.3mV。初步诊断：急性心肌梗死。",
    "document_type": "首次病程记录",
    "persist": false
  }')

echo "   响应长度: $(echo $QC_RESPONSE | wc -c) 字节"

# 检查响应是否成功
if echo "$QC_RESPONSE" | grep -q '"document_id"'; then
    echo -e "${GREEN}✅ 四川质控 API 调用成功${NC}"
    
    # 提取关键信息
    TOTAL_RULES=$(echo $QC_RESPONSE | jq -r '.evaluation_summary.total_rules // "N/A"')
    COMPLIANT_RULES=$(echo $QC_RESPONSE | jq -r '.evaluation_summary.compliant_rules // "N/A"')
    COMPLIANCE_RATE=$(echo $QC_RESPONSE | jq -r '.evaluation_summary.compliance_rate // "N/A"')
    OVERALL_GRADE=$(echo $QC_RESPONSE | jq -r '.evaluation_summary.overall_grade // "N/A"')
    PROCESSING_TIME=$(echo $QC_RESPONSE | jq -r '.performance_metrics.processing_time // "N/A"')
    TOKEN_USAGE=$(echo $QC_RESPONSE | jq -r '.performance_metrics.token_usage // "N/A"')
    
    echo ""
    echo "   📊 质控结果摘要:"
    echo "   ├─ 总规则数: $TOTAL_RULES"
    echo "   ├─ 合规规则数: $COMPLIANT_RULES"
    echo "   ├─ 合规率: $COMPLIANCE_RATE%"
    echo "   ├─ 总体等级: $OVERALL_GRADE"
    echo "   ├─ 处理时间: ${PROCESSING_TIME}s"
    echo "   └─ Token 使用: $TOKEN_USAGE"
    
    # 检查是否是 Mock 数据
    if echo "$QC_RESPONSE" | grep -q '"_mock":true'; then
        echo ""
        echo -e "${YELLOW}⚠️  警告: 返回的是 Mock 数据（LLM API 未配置）${NC}"
    else
        echo ""
        echo -e "${GREEN}✅ 返回的是真实 LLM 分析结果${NC}"
    fi
else
    echo -e "${RED}❌ 四川质控 API 调用失败${NC}"
    echo "   响应: $QC_RESPONSE"
    exit 1
fi
echo ""

# 5. 保存完整响应到文件
echo "5️⃣  保存测试结果..."
RESULT_FILE="test-sichuan-qc-result-$(date +%Y%m%d-%H%M%S).json"
echo "$QC_RESPONSE" | jq '.' > "$RESULT_FILE"
echo -e "${GREEN}✅ 测试结果已保存到: $RESULT_FILE${NC}"
echo ""

# 6. 总结
echo "========================================="
echo "测试总结"
echo "========================================="
echo -e "${GREEN}✅ 所有测试通过！${NC}"
echo ""
echo "📝 下一步操作:"
echo "   1. 打开浏览器访问: http://localhost:3000"
echo "   2. 登录系统 (admin@medqc.com / admin123)"
echo "   3. 进入 \"演示与工具\" → \"LLM质控演示新版（测试）\""
echo "   4. 选择病历和文书"
echo "   5. 选择质控规则"
echo "   6. 点击 \"开始演示\" 按钮"
echo "   7. 等待分析完成（20-30秒）"
echo "   8. 查看分析结果"
echo ""
echo "📖 详细测试指南: docs/新版演示页面-四川质控API集成测试指南.md"
echo ""


