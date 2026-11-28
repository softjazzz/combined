#!/bin/bash
# 最终的PDF转换脚本 - 提供多种转换选项

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 定义目录路径（支持通过环境变量覆盖；转换、查看与清理共用同一组有效路径）
SOURCE_DIR="${PDF_SOURCE_DIR:-$SCRIPT_DIR/医保规则}"
VENV_DIR="${PDF_CONVERTER_VENV:-$SCRIPT_DIR/.venv}"
LOG_FILE="${PDF_LOG_FILE:-$SCRIPT_DIR/final_conversion.log}"
BASIC_OUTPUT_DIR="${PDF_BASIC_OUTPUT_DIR:-$SCRIPT_DIR/医保规则_basic}"
PRECISE_OUTPUT_DIR="${PDF_PRECISE_OUTPUT_DIR:-$SCRIPT_DIR/医保规则_precise}"
MD_OUTPUT_DIR="${PDF_OUTPUT_DIR:-$SCRIPT_DIR/医保规则_md}"
TABLE_OUTPUT_DIR="${PDF_TABLE_OUTPUT_DIR:-$SCRIPT_DIR/医保规则_table_format}"
IMPROVED_OUTPUT_DIR="${PDF_IMPROVED_OUTPUT_DIR:-$SCRIPT_DIR/医保规则_improved_md}"
MANIFEST_NAME=".final_converter_generated.manifest"
LOG_HEADER_PREFIX="PDF转换器日志 - "

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 日志函数
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ✗${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠${NC} $1" | tee -a "$LOG_FILE"
}

# 显示菜单
show_menu() {
    echo
    echo -e "${CYAN}PDF to Markdown 转换器${NC}"
    echo "=================================="
    echo
    echo "请选择转换方式："
    echo
    echo "1. 基础转换 (markitdown) - 快速转换，保留原始格式"
    echo "2. 精确表格转换 - 专门优化表格结构，适合医保规则文档"
    echo "3. 全部转换 - 同时使用两种方式转换"
    echo "4. 查看已转换文件"
    echo "5. 清理转换结果"
    echo "0. 退出"
    echo
}

# 登记由本工具生成的单个 Markdown 文件（按输出目录存放清单，避免误删无法确认归属的文件）
record_generated_file() {
    local output_dir="$1"
    local file_name="$2"
    local manifest_path="$output_dir/$MANIFEST_NAME"
    if [[ -z "$file_name" || "$file_name" == *"/"* || "$file_name" == *"\\"* || "$file_name" == "." || "$file_name" == ".." || "$file_name" != *.md ]]; then
        return 1
    fi
    touch "$manifest_path"
    if ! grep -Fxq -- "$file_name" "$manifest_path" 2>/dev/null; then
        printf '%s\n' "$file_name" >> "$manifest_path"
    fi
}

# 收集去重后的有效输出目录
collect_unique_output_dirs() {
    local raw_dirs=(
        "$BASIC_OUTPUT_DIR"
        "$PRECISE_OUTPUT_DIR"
        "$MD_OUTPUT_DIR"
        "$TABLE_OUTPUT_DIR"
        "$IMPROVED_OUTPUT_DIR"
    )
    local seen=$'\n'
    local dir
    UNIQUE_OUTPUT_DIRS=()
    for dir in "${raw_dirs[@]}"; do
        if [[ -n "$dir" && "$seen" != *$'\n'"$dir"$'\n'* ]]; then
            UNIQUE_OUTPUT_DIRS+=("$dir")
            seen+="$dir"$'\n'
        fi
    done
}

# 基础转换
basic_conversion() {
    log "开始基础转换..."
    if [[ -f "$VENV_DIR/bin/activate" ]]; then
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
    fi
    
    local output_dir="$BASIC_OUTPUT_DIR"
    mkdir -p "$output_dir"
    
    local success_count=0
    local total_count=0
    
    for pdf_file in "$SOURCE_DIR"/*.pdf; do
        if [[ -f "$pdf_file" ]]; then
            total_count=$((total_count + 1))
            local pdf_name
            pdf_name=$(basename "$pdf_file")
            local md_name="${pdf_name%.pdf}_basic.md"
            local md_path="$output_dir/$md_name"
            local tmp_path="$output_dir/.${md_name}.tmp.$$"
            
            log "转换: $pdf_name"
            
            if markitdown "$pdf_file" > "$tmp_path" 2>> "$LOG_FILE"; then
                mv -f -- "$tmp_path" "$md_path"
                record_generated_file "$output_dir" "$md_name"
                log_success "转换成功: $pdf_name"
                success_count=$((success_count + 1))
            else
                rm -f -- "$tmp_path"
                log_error "转换失败: $pdf_name"
            fi
        fi
    done
    
    log "基础转换完成: $success_count/$total_count 个文件"
    log "输出目录: $output_dir"
}

# 精确表格转换
precise_conversion() {
    log "开始精确表格转换..."
    local py_bin="python3"
    if [[ -x "$VENV_DIR/bin/python" ]]; then
        py_bin="$VENV_DIR/bin/python"
    fi
    
    "$py_bin" "$SCRIPT_DIR/precise_table_converter.py" \
        --source-dir "$SOURCE_DIR" \
        --output-dir "$PRECISE_OUTPUT_DIR" \
        --manifest-file "$PRECISE_OUTPUT_DIR/$MANIFEST_NAME"
}

# 查看转换结果
show_results() {
    echo
    echo -e "${CYAN}转换结果概览：${NC}"
    echo
    
    collect_unique_output_dirs
    for dir in "${UNIQUE_OUTPUT_DIRS[@]}"; do
        if [[ -d "$dir" ]]; then
            local dir_name
            dir_name=$(basename "$dir")
            local file_count
            file_count=$(find "$dir" -name "*.md" | wc -l)
            echo "📁 $dir_name ($dir): $file_count 个文件"
            
            if [[ $file_count -gt 0 ]]; then
                echo "   最新文件："
                find "$dir" -name "*.md" -printf "   - %f (%TY-%Tm-%Td %TH:%TM)\n" | sort -k3 -r | head -3
            fi
            echo
        fi
    done
}

# 清理转换结果（仅删除清单中确认由本工具生成的文件，保留所有原有及无法确认归属的文件和目录）
cleanup_results() {
    collect_unique_output_dirs
    local files_to_delete=()
    local manifests_to_delete=()
    local seen_files=$'\n'
    local dir manifest_path entry target_file

    for dir in "${UNIQUE_OUTPUT_DIRS[@]}"; do
        manifest_path="$dir/$MANIFEST_NAME"
        if [[ -f "$manifest_path" && ! -L "$manifest_path" ]]; then
            manifests_to_delete+=("$manifest_path")
            while IFS= read -r entry || [[ -n "$entry" ]]; do
                entry="${entry%$'\r'}"
                if [[ -z "$entry" || "$entry" == *"/"* || "$entry" == *"\\"* || "$entry" == "." || "$entry" == ".." || "$entry" != *.md ]]; then
                    continue
                fi
                target_file="$dir/$entry"
                if [[ -f "$target_file" && ! -L "$target_file" ]]; then
                    if [[ "$seen_files" != *$'\n'"$target_file"$'\n'* ]]; then
                        files_to_delete+=("$target_file")
                        seen_files+="$target_file"$'\n'
                    fi
                fi
            done < "$manifest_path"
        fi
    done

    local log_to_delete=""
    if [[ -f "$LOG_FILE" && ! -L "$LOG_FILE" ]]; then
        local first_log_line=""
        IFS= read -r first_log_line < "$LOG_FILE" || true
        first_log_line="${first_log_line%$'\r'}"
        if [[ "$first_log_line" == "${LOG_HEADER_PREFIX}"* ]]; then
            log_to_delete="$LOG_FILE"
        fi
    fi

    if [[ ${#files_to_delete[@]} -eq 0 && -z "$log_to_delete" ]]; then
        echo
        echo "未发现可确认由本工具生成的转换结果（原有文件及无法确认归属的文件将保持保留）。"
        return 0
    fi

    echo
    echo -e "${YELLOW}警告：仅删除以下可确认由本工具生成的转换结果文件（无法确认归属的文件与目录将保持保留）：${NC}"
    for target_file in "${files_to_delete[@]}"; do
        echo "  - $target_file"
    done
    if [[ -n "$log_to_delete" ]]; then
        echo "  - $log_to_delete (工具日志)"
    fi
    read -p "确定要继续吗？(y/N): " confirm
    
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        for target_file in "${files_to_delete[@]}"; do
            if [[ -f "$target_file" && ! -L "$target_file" ]]; then
                rm -f -- "$target_file"
                echo -e "${GREEN}✓ 已删除生成文件: $target_file${NC}"
            fi
        done

        for manifest_path in "${manifests_to_delete[@]}"; do
            if [[ -f "$manifest_path" && ! -L "$manifest_path" ]]; then
                rm -f -- "$manifest_path"
            fi
        done
        
        if [[ -n "$log_to_delete" && -f "$log_to_delete" && ! -L "$log_to_delete" ]]; then
            rm -f -- "$log_to_delete"
            echo -e "${GREEN}✓ 已清理日志文件: $log_to_delete${NC}"
        fi
        
        echo "清理完成！（仅删除确认由工具生成的文件，其余文件已保留）"
    else
        echo "取消清理操作"
    fi
}

# 检查环境
check_environment() {
    if [[ ! -d "$SOURCE_DIR" ]]; then
        log_error "源目录不存在: $SOURCE_DIR"
        exit 1
    fi
    
    if [[ ! -d "$VENV_DIR" ]] && ! command -v markitdown &> /dev/null; then
        log_error "虚拟环境不存在: $VENV_DIR"
        log "请先运行 ./convert_pdfs.sh --install 或执行: python3 -m venv \"$VENV_DIR\" && \"$VENV_DIR/bin/pip\" install -r \"$SCRIPT_DIR/requirements.txt\""
        exit 1
    fi
    
    local pdf_count=$(find "$SOURCE_DIR" -name "*.pdf" | wc -l)
    if [[ $pdf_count -eq 0 ]]; then
        log_warning "源目录中没有找到PDF文件"
        exit 1
    fi
    
    log_success "环境检查通过，找到 $pdf_count 个PDF文件"
}

# 主函数
main() {
    # 初始化日志
    echo "${LOG_HEADER_PREFIX}$(date)" > "$LOG_FILE"
    
    log "PDF to Markdown 转换器启动"
    
    # 检查环境
    check_environment
    
    while true; do
        show_menu
        read -p "请选择 (0-5): " choice
        
        case $choice in
            1)
                basic_conversion
                ;;
            2)
                precise_conversion
                ;;
            3)
                basic_conversion
                echo
                precise_conversion
                ;;
            4)
                show_results
                ;;
            5)
                cleanup_results
                ;;
            0)
                log "退出程序"
                echo "再见！"
                exit 0
                ;;
            *)
                echo -e "${RED}无效选择，请重试${NC}"
                ;;
        esac
        
        echo
        read -p "按回车键继续..."
    done
}

# 运行主函数
main "$@"
