#!/bin/bash

# 安全检查脚本 - Auto模式前后对比
# 用于验证系统状态和文件完整性

PROJECT_DIR="/home/ubuntu/KAG/kag/examples/002medqc/MedQC0817"
BACKUP_DIR="$PROJECT_DIR/safety_backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

cd "$PROJECT_DIR"

echo "🛡️ 安全检查脚本"
echo "================="

# 创建备份目录
mkdir -p "$BACKUP_DIR"

case "$1" in
    "before")
        echo "📋 执行Auto模式前的安全检查..."
        
        # 1. 检查Git状态
        echo "🔍 检查Git状态..."
        if ! git status --porcelain | grep -q .; then
            echo "✅ Git工作区干净"
        else
            echo "⚠️ Git工作区有未提交的更改:"
            git status --short
            echo "建议先提交更改: git add . && git commit -m 'Auto模式前保存'"
        fi
        
        # 2. 创建文件清单
        echo "📝 创建文件清单..."
        find . -type f \( -name "*.js" -o -name "*.ts" -o -name "*.vue" -o -name "*.py" -o -name "*.json" -o -name "*.md" -o -name "*.yaml" -o -name "*.yml" \) \
            -not -path "./node_modules/*" -not -path "./.git/*" \
            | sort > "$BACKUP_DIR/file_list_before_$TIMESTAMP.txt"
        
        # 3. 备份关键配置文件
        echo "💾 备份关键配置文件..."
        critical_files=("package.json" "requirements.txt" "config.yaml" ".env" "tsconfig.json" "vite.config.ts")
        for file in "${critical_files[@]}"; do
            if [[ -f "$file" ]]; then
                cp "$file" "$BACKUP_DIR/${file}_backup_$TIMESTAMP"
                echo "✅ 备份: $file"
            fi
        done
        
        # 4. 计算文件哈希
        echo "🔐 计算文件哈希..."
        find . -type f \( -name "*.js" -o -name "*.ts" -o -name "*.vue" -o -name "*.py" -o -name "*.json" -o -name "*.md" \) \
            -not -path "./node_modules/*" -not -path "./.git/*" \
            -exec sha256sum {} \; | sort > "$BACKUP_DIR/file_hashes_before_$TIMESTAMP.txt"
        
        # 5. 记录项目结构
        echo "🏗️ 记录项目结构..."
        tree -I 'node_modules|.git' > "$BACKUP_DIR/project_structure_before_$TIMESTAMP.txt" 2>/dev/null || \
        find . -type d -not -path "./node_modules/*" -not -path "./.git/*" | sort > "$BACKUP_DIR/project_structure_before_$TIMESTAMP.txt"
        
        # 6. 创建Git快照
        echo "📸 创建Git快照..."
        git log --oneline -20 > "$BACKUP_DIR/git_log_before_$TIMESTAMP.txt"
        git stash push -m "Auto模式前安全备份 - $TIMESTAMP" --include-untracked 2>/dev/null || true
        
        echo "✅ Auto模式前安全检查完成"
        echo "备份文件保存在: $BACKUP_DIR"
        echo ""
        echo "🚀 现在可以安全启用Auto模式"
        echo "监控命令: bash monitor_auto_mode.sh"
        ;;
        
    "after")
        echo "🔍 执行Auto模式后的安全检查..."
        
        # 查找最新的before备份
        latest_before=$(ls -t "$BACKUP_DIR"/file_list_before_*.txt 2>/dev/null | head -1)
        if [[ -z "$latest_before" ]]; then
            echo "❌ 未找到Auto模式前的备份文件"
            echo "请先运行: bash safety_check.sh before"
            exit 1
        fi
        
        before_timestamp=$(basename "$latest_before" | sed 's/file_list_before_\(.*\)\.txt/\1/')
        echo "📋 对比基准时间: $before_timestamp"
        
        # 1. 检查文件完整性
        echo "🔍 检查文件完整性..."
        find . -type f \( -name "*.js" -o -name "*.ts" -o -name "*.vue" -o -name "*.py" -o -name "*.json" -o -name "*.md" -o -name "*.yaml" -o -name "*.yml" \) \
            -not -path "./node_modules/*" -not -path "./.git/*" \
            | sort > "$BACKUP_DIR/file_list_after_$TIMESTAMP.txt"
        
        # 对比文件列表
        if diff "$BACKUP_DIR/file_list_before_$before_timestamp.txt" "$BACKUP_DIR/file_list_after_$TIMESTAMP.txt" > "$BACKUP_DIR/file_diff_$TIMESTAMP.txt"; then
            echo "✅ 文件列表无变化"
        else
            echo "📝 文件列表变化:"
            cat "$BACKUP_DIR/file_diff_$TIMESTAMP.txt"
        fi
        
        # 2. 检查关键配置文件
        echo "🔍 检查关键配置文件..."
        critical_files=("package.json" "requirements.txt" "config.yaml" ".env" "tsconfig.json" "vite.config.ts")
        for file in "${critical_files[@]}"; do
            if [[ -f "$file" ]] && [[ -f "$BACKUP_DIR/${file}_backup_$before_timestamp" ]]; then
                if diff "$file" "$BACKUP_DIR/${file}_backup_$before_timestamp" > /dev/null; then
                    echo "✅ $file 未变更"
                else
                    echo "⚠️ $file 已变更:"
                    diff "$BACKUP_DIR/${file}_backup_$before_timestamp" "$file" | head -20
                fi
            fi
        done
        
        # 3. 检查文件哈希
        echo "🔐 检查文件完整性..."
        find . -type f \( -name "*.js" -o -name "*.ts" -o -name "*.vue" -o -name "*.py" -o -name "*.json" -o -name "*.md" \) \
            -not -path "./node_modules/*" -not -path "./.git/*" \
            -exec sha256sum {} \; | sort > "$BACKUP_DIR/file_hashes_after_$TIMESTAMP.txt"
        
        changed_files=$(comm -13 "$BACKUP_DIR/file_hashes_before_$before_timestamp.txt" "$BACKUP_DIR/file_hashes_after_$TIMESTAMP.txt" | wc -l)
        if [[ $changed_files -eq 0 ]]; then
            echo "✅ 所有文件哈希验证通过"
        else
            echo "📝 $changed_files 个文件已修改"
            echo "详细变更:"
            comm -13 "$BACKUP_DIR/file_hashes_before_$before_timestamp.txt" "$BACKUP_DIR/file_hashes_after_$TIMESTAMP.txt" | head -10
        fi
        
        # 4. Git状态检查
        echo "🔍 检查Git状态..."
        if git status --porcelain | grep -q .; then
            echo "📝 Git工作区变更:"
            git status --short
            echo ""
            echo "变更统计:"
            git diff --stat
        else
            echo "✅ Git工作区干净"
        fi
        
        # 5. 生成安全报告
        echo "📋 生成安全报告..."
        {
            echo "Auto模式安全检查报告"
            echo "===================="
            echo "检查时间: $(date)"
            echo "基准时间: $before_timestamp"
            echo ""
            echo "文件变更统计:"
            echo "- 文件列表变化: $(wc -l < "$BACKUP_DIR/file_diff_$TIMESTAMP.txt") 行"
            echo "- 文件内容变化: $changed_files 个文件"
            echo ""
            echo "Git状态:"
            git status --short
            echo ""
            echo "最近提交:"
            git log --oneline -5
        } > "$BACKUP_DIR/safety_report_$TIMESTAMP.txt"
        
        echo "✅ Auto模式后安全检查完成"
        echo "报告保存在: $BACKUP_DIR/safety_report_$TIMESTAMP.txt"
        ;;
        
    "restore")
        echo "🔄 恢复到Auto模式前状态..."
        
        # 查找最新的Git stash
        if git stash list | grep -q "Auto模式前安全备份"; then
            echo "📦 恢复Git stash..."
            git stash pop
            echo "✅ 已恢复到Auto模式前状态"
        else
            echo "❌ 未找到Auto模式前的Git备份"
        fi
        ;;
        
    *)
        echo "用法: $0 {before|after|restore}"
        echo ""
        echo "命令说明:"
        echo "  before  - Auto模式前执行安全检查和备份"
        echo "  after   - Auto模式后执行安全验证"
        echo "  restore - 恢复到Auto模式前的状态"
        echo ""
        echo "推荐流程:"
        echo "1. bash safety_check.sh before"
        echo "2. [启用Auto模式]"
        echo "3. bash safety_check.sh after"
        echo "4. 如需恢复: bash safety_check.sh restore"
        exit 1
        ;;
esac
