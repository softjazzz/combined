#!/bin/bash

# 权限测试脚本
# 测试 RBAC 权限系统的各种场景

BASE_URL="http://localhost:8001"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "MedQC RBAC 权限系统测试"
echo "========================================="
echo ""

# 测试计数器
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 测试函数
test_endpoint() {
    local test_name="$1"
    local method="$2"
    local endpoint="$3"
    local token="$4"
    local expected_status="$5"
    local data="$6"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    echo -n "测试 $TOTAL_TESTS: $test_name ... "
    
    if [ -z "$token" ]; then
        # 未认证请求
        if [ "$method" = "GET" ]; then
            response=$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL$endpoint")
        elif [ "$method" = "POST" ]; then
            response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL$endpoint" \
                -H "Content-Type: application/json" \
                -d "$data")
        elif [ "$method" = "DELETE" ]; then
            response=$(curl -s -w "\n%{http_code}" -X DELETE "$BASE_URL$endpoint")
        fi
    else
        # 认证请求
        if [ "$method" = "GET" ]; then
            response=$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL$endpoint" \
                -H "Authorization: Bearer $token")
        elif [ "$method" = "POST" ]; then
            response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL$endpoint" \
                -H "Authorization: Bearer $token" \
                -H "Content-Type: application/json" \
                -d "$data")
        elif [ "$method" = "DELETE" ]; then
            response=$(curl -s -w "\n%{http_code}" -X DELETE "$BASE_URL$endpoint" \
                -H "Authorization: Bearer $token")
        fi
    fi
    
    # 提取状态码
    status_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$status_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASSED${NC} (状态码: $status_code)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}✗ FAILED${NC} (期望: $expected_status, 实际: $status_code)"
        echo "  响应: $body"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

# 获取登录 token
get_token() {
    local email="$1"
    local password="$2"
    
    response=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\": \"$email\", \"password\": \"$password\"}")
    
    token=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
    echo "$token"
}

echo "========================================="
echo "第一部分：获取测试用户 Token"
echo "========================================="
echo ""

echo "登录 admin 用户..."
ADMIN_TOKEN=$(get_token "admin@medqc.com" "admin123")
echo "Admin Token: ${ADMIN_TOKEN:0:50}..."
echo ""

echo "登录 qc_manager 用户..."
QC_MANAGER_TOKEN=$(get_token "qc@medqc.com" "qc123456")
echo "QC Manager Token: ${QC_MANAGER_TOKEN:0:50}..."
echo ""

echo "登录 doctor 用户..."
DOCTOR_TOKEN=$(get_token "doctor@medqc.com" "doctor123")
echo "Doctor Token: ${DOCTOR_TOKEN:0:50}..."
echo ""

echo "========================================="
echo "第二部分：未认证访问测试"
echo "========================================="
echo ""

test_endpoint "未认证访问医疗记录列表" "GET" "/api/v1/records" "" "403"
test_endpoint "未认证访问质控规则列表" "GET" "/api/v1/qc/rules" "" "403"
test_endpoint "未认证访问质控结果" "GET" "/api/v1/qc/result/test-id" "" "403"

echo ""
echo "========================================="
echo "第三部分：医疗记录权限测试"
echo "========================================="
echo ""

# Admin 用户测试
echo "--- Admin 用户 (应该有所有权限) ---"
test_endpoint "Admin 查看医疗记录列表" "GET" "/api/v1/records" "$ADMIN_TOKEN" "200"
test_endpoint "Admin 删除医疗记录" "DELETE" "/api/v1/records/test-id" "$ADMIN_TOKEN" "404"  # 404 因为记录不存在，但权限通过

# QC Manager 用户测试
echo ""
echo "--- QC Manager 用户 (应该有读取权限，无删除权限) ---"
test_endpoint "QC Manager 查看医疗记录列表" "GET" "/api/v1/records" "$QC_MANAGER_TOKEN" "200"
test_endpoint "QC Manager 删除医疗记录" "DELETE" "/api/v1/records/test-id" "$QC_MANAGER_TOKEN" "403"  # 应该被拒绝

# Doctor 用户测试
echo ""
echo "--- Doctor 用户 (应该有读取权限，无删除权限) ---"
test_endpoint "Doctor 查看医疗记录列表" "GET" "/api/v1/records" "$DOCTOR_TOKEN" "200"  # Doctor 有读取权限
test_endpoint "Doctor 删除医疗记录" "DELETE" "/api/v1/records/test-id" "$DOCTOR_TOKEN" "403"  # 应该被拒绝

echo ""
echo "========================================="
echo "第四部分：质控规则权限测试"
echo "========================================="
echo ""

# Admin 用户测试
echo "--- Admin 用户 (应该有所有权限) ---"
test_endpoint "Admin 查看质控规则列表" "GET" "/api/v1/qc/rules" "$ADMIN_TOKEN" "200"
test_endpoint "Admin 删除质控规则" "DELETE" "/api/v1/qc/rules/test-id" "$ADMIN_TOKEN" "404"  # 404 因为规则不存在，但权限通过

# QC Manager 用户测试
echo ""
echo "--- QC Manager 用户 (应该有创建/更新权限，无删除权限) ---"
test_endpoint "QC Manager 查看质控规则列表" "GET" "/api/v1/qc/rules" "$QC_MANAGER_TOKEN" "200"
test_endpoint "QC Manager 删除质控规则" "DELETE" "/api/v1/qc/rules/test-id" "$QC_MANAGER_TOKEN" "403"  # 应该被拒绝

# Doctor 用户测试
echo ""
echo "--- Doctor 用户 (应该有读取权限，无创建/删除权限) ---"
test_endpoint "Doctor 查看质控规则列表" "GET" "/api/v1/qc/rules" "$DOCTOR_TOKEN" "200"
test_endpoint "Doctor 删除质控规则" "DELETE" "/api/v1/qc/rules/test-id" "$DOCTOR_TOKEN" "403"  # 应该被拒绝

echo ""
echo "========================================="
echo "第五部分：质控执行权限测试"
echo "========================================="
echo ""

# Admin 用户测试
echo "--- Admin 用户 (应该有分析权限) ---"
test_endpoint "Admin 执行质控分析" "POST" "/api/v1/qc/analyze/test-record" "$ADMIN_TOKEN" "200" "{}"

# QC Manager 用户测试
echo ""
echo "--- QC Manager 用户 (应该有分析权限) ---"
test_endpoint "QC Manager 执行质控分析" "POST" "/api/v1/qc/analyze/test-record" "$QC_MANAGER_TOKEN" "200" "{}"

# Doctor 用户测试
echo ""
echo "--- Doctor 用户 (应该无分析权限) ---"
test_endpoint "Doctor 执行质控分析" "POST" "/api/v1/qc/analyze/test-record" "$DOCTOR_TOKEN" "403" "{}"  # 应该被拒绝

echo ""
echo "========================================="
echo "测试总结"
echo "========================================="
echo ""
echo "总测试数: $TOTAL_TESTS"
echo -e "${GREEN}通过: $PASSED_TESTS${NC}"
echo -e "${RED}失败: $FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ 所有测试通过！${NC}"
    exit 0
else
    echo -e "${RED}✗ 有测试失败，请检查权限配置${NC}"
    exit 1
fi

