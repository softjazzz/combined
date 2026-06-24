#!/bin/bash

# Auto模式监控脚本
# 用于监控项目文件变更和系统状态

PROJECT_DIR="/home/ubuntu/KAG/kag/examples/002medqc/MedQC0817"
LOG_DIR="$PROJECT_DIR/auto_mode_logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 创建日志目录
mkdir -p "$LOG_DIR"

echo "🛡️ Auto模式监控启动 - $TIMESTAMP"
echo "项目目录: $PROJECT_DIR"
echo "日志目录: $LOG_DIR"

# 1. 记录初始状态
echo "📊 记录初始状态..."
cd "$PROJECT_DIR"

# 文件列表快照
find . -type f -name "*.js" -o -name "*.ts" -o -name "*.vue" -o -name "*.py" -o -name "*.json" -o -name "*.md" \
  | sort > "$LOG_DIR/initial_files_$TIMESTAMP.txt"

# Git状态快照
git status --porcelain > "$LOG_DIR/initial_git_status_$TIMESTAMP.txt"
git log --oneline -20 > "$LOG_DIR/initial_git_log_$TIMESTAMP.txt"

# 2. 启动文件监控
echo "👀 启动文件变更监控..."
if command -v inotifywait &> /dev/null; then
    inotifywait -m -r -e modify,create,delete,move "$PROJECT_DIR" \
      --format '%T %w%f %e' --timefmt '%Y-%m-%d %H:%M:%S' \
      --exclude '\.git|node_modules|\.log$' \
      > "$LOG_DIR/file_changes_$TIMESTAMP.log" &
    INOTIFY_PID=$!
    echo "文件监控PID: $INOTIFY_PID"
else
    echo "⚠️ inotifywait未安装，跳过实时文件监控"
fi

# 3. 定期状态检查函数
check_status() {
    local check_time=$(date +%Y%m%d_%H%M%S)
    echo "🔍 状态检查 - $check_time"
    
    cd "$PROJECT_DIR"
    
    # 检查Git状态
    if git status --porcelain | grep -q .; then
        echo "📝 检测到文件变更:"
        git status --short
        git status --porcelain > "$LOG_DIR/git_status_$check_time.txt"
    fi
    
    # 检查关键文件
    local critical_files=("package.json" "requirements.txt" "config.yaml" ".env")
    for file in "${critical_files[@]}"; do
        if [[ -f "$file" ]]; then
            if ! git diff --quiet HEAD -- "$file" 2>/dev/null; then
                echo "⚠️ 关键文件变更: $file"
                git diff HEAD -- "$file" > "$LOG_DIR/critical_change_${file}_$check_time.diff"
            fi
        fi
    done
    
    # 检查文件数量变化
    local current_count=$(find . -type f -name "*.js" -o -name "*.ts" -o -name "*.vue" -o -name "*.py" -o -name "*.json" -o -name "*.md" | wc -l)
    local initial_count=$(wc -l < "$LOG_DIR/initial_files_$TIMESTAMP.txt")
    
    if [[ $current_count -ne $initial_count ]]; then
        echo "📊 文件数量变化: $initial_count -> $current_count"
        find . -type f -name "*.js" -o -name "*.ts" -o -name "*.vue" -o -name "*.py" -o -name "*.json" -o -name "*.md" \
          | sort > "$LOG_DIR/current_files_$check_time.txt"
        diff "$LOG_DIR/initial_files_$TIMESTAMP.txt" "$LOG_DIR/current_files_$check_time.txt" \
          > "$LOG_DIR/file_diff_$check_time.txt"
    fi
}

# 4. 清理函数
cleanup() {
    echo "🛑 停止监控..."
    if [[ -n "$INOTIFY_PID" ]]; then
        kill $INOTIFY_PID 2>/dev/null
    fi
    
    # 生成最终报告
    echo "📋 生成最终报告..."
    {
        echo "Auto模式监控报告"
        echo "=================="
        echo "开始时间: $TIMESTAMP"
        echo "结束时间: $(date +%Y%m%d_%H%M%S)"
        echo ""
        echo "文件变更日志:"
        if [[ -f "$LOG_DIR/file_changes_$TIMESTAMP.log" ]]; then
            tail -50 "$LOG_DIR/file_changes_$TIMESTAMP.log"
        fi
        echo ""
        echo "最终Git状态:"
        cd "$PROJECT_DIR"
        git status
    } > "$LOG_DIR/final_report_$(date +%Y%m%d_%H%M%S).txt"
    
    echo "✅ 监控结束，报告保存在: $LOG_DIR"
    exit 0
}

# 5. 设置信号处理
trap cleanup SIGINT SIGTERM

# 6. 主监控循环
echo "🚀 开始监控循环 (每30秒检查一次)"
echo "按 Ctrl+C 停止监控"

while true; do
    check_status
    sleep 30
done
