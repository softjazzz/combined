#!/bin/bash

# 医疗文书分类数据库迁移执行脚本
# 使用方法: ./execute-migration.sh [environment]
# 环境: development | staging | production

set -e  # 遇到错误立即退出

ENVIRONMENT=${1:-development}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 开始执行医疗文书分类数据库迁移..."
echo "📍 环境: $ENVIRONMENT"
echo "📁 项目目录: $PROJECT_DIR"

# 检查必要文件
MIGRATION_FILES=(
    "$PROJECT_DIR/database/migrations/20250901_add_document_classification.sql"
    "$PROJECT_DIR/database/migrations/20250901_update_qc_rules_for_documents.sql"
)

echo "🔍 检查迁移文件..."
for file in "${MIGRATION_FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "❌ 错误: 迁移文件不存在: $file"
        exit 1
    fi
    echo "✅ 找到: $(basename "$file")"
done

# 设置环境变量
case $ENVIRONMENT in
    development)
        export NODE_ENV=development
        ;;
    staging)
        export NODE_ENV=staging
        ;;
    production)
        export NODE_ENV=production
        echo "⚠️  警告: 正在生产环境执行迁移，请确认操作！"
        read -p "继续执行? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "❌ 迁移已取消"
            exit 1
        fi
        ;;
    *)
        echo "❌ 错误: 未知环境 '$ENVIRONMENT'"
        echo "支持的环境: development, staging, production"
        exit 1
        ;;
esac

# 检查Node.js和依赖
echo "🔍 检查运行环境..."
if ! command -v node &> /dev/null; then
    echo "❌ 错误: Node.js 未安装"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ 错误: npm 未安装"
    exit 1
fi

# 安装依赖（如果需要）
if [[ ! -d "$PROJECT_DIR/node_modules" ]]; then
    echo "📦 安装项目依赖..."
    cd "$PROJECT_DIR"
    npm install
fi

# 编译TypeScript（如果需要）
echo "🔨 编译TypeScript..."
cd "$PROJECT_DIR"
if [[ -f "tsconfig.json" ]]; then
    npx tsc --noEmit  # 只检查类型，不生成文件
fi

# 执行迁移
echo "🗄️  执行数据库迁移..."
cd "$PROJECT_DIR"

# 方法1: 使用TypeScript直接执行
if [[ -f "scripts/migrate-document-classification.ts" ]]; then
    echo "📝 使用TypeScript迁移脚本..."
    npx ts-node scripts/migrate-document-classification.ts
else
    echo "❌ 错误: 迁移脚本不存在"
    exit 1
fi

# 验证迁移结果
echo "🔍 验证迁移结果..."

# 创建验证脚本
cat > /tmp/verify-migration.js << 'EOF'
const { createClient } = require('@supabase/supabase-js');

const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://dgsdkdbjpucyawnyfbdu.supabase.co';
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw';

const supabase = createClient(supabaseUrl, supabaseKey);

async function verifyTables() {
    const tables = [
        'document_categories',
        'document_types', 
        'medical_documents',
        'qc_templates',
        'document_qc_results'
    ];
    
    console.log('🔍 验证表结构...');
    
    for (const table of tables) {
        try {
            const { data, error } = await supabase
                .from(table)
                .select('*')
                .limit(1);
            
            if (error) {
                console.log(`❌ 表 ${table}: ${error.message}`);
            } else {
                console.log(`✅ 表 ${table}: 存在且可访问`);
            }
        } catch (err) {
            console.log(`❌ 表 ${table}: ${err.message}`);
        }
    }
    
    // 检查数据
    console.log('\n📊 检查基础数据...');
    
    try {
        const { data: categories } = await supabase
            .from('document_categories')
            .select('category_code, category_name');
        
        console.log(`✅ 文书分类: ${categories?.length || 0} 条记录`);
        
        const { data: types } = await supabase
            .from('document_types')
            .select('type_code, type_name')
            .limit(5);
        
        console.log(`✅ 文书类型: ${types?.length || 0}+ 条记录`);
        
    } catch (err) {
        console.log(`❌ 数据检查失败: ${err.message}`);
    }
}

verifyTables().then(() => {
    console.log('\n🎉 迁移验证完成！');
    process.exit(0);
}).catch(err => {
    console.error('❌ 验证失败:', err);
    process.exit(1);
});
EOF

# 执行验证
echo "🔍 运行验证脚本..."
node /tmp/verify-migration.js

# 清理临时文件
rm -f /tmp/verify-migration.js

echo ""
echo "🎉 数据库迁移执行完成！"
echo ""
echo "📋 下一步操作："
echo "1. 检查迁移日志确认无错误"
echo "2. 在数据库管理界面验证表结构"
echo "3. 运行后端服务测试"
echo "4. 执行分类功能测试"
echo ""
echo "🔧 如果遇到问题："
echo "- 检查数据库连接配置"
echo "- 确认Supabase权限设置"
echo "- 查看详细错误日志"
echo ""
