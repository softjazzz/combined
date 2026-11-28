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
LOG_CREATED_BY_SESSION=0

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

# 计算文件 SHA-256 摘要（小写 64 位十六进制）
compute_file_sha256() {
    local file_path="$1"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -- "$file_path" | awk '{sub(/^\\/, "", $1); print tolower($1)}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 -- "$file_path" | awk '{print tolower($1)}'
    else
        local py_bin="python3"
        if [[ -x "$VENV_DIR/bin/python" ]]; then
            py_bin="$VENV_DIR/bin/python"
        fi
        "$py_bin" -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest().lower())' "$file_path"
    fi
}

# 校验清单中的单层 Markdown 文件名与 SHA-256 格式
is_valid_manifest_filename() {
    local file_name="$1"
    [[ -n "$file_name" && "$file_name" != *"/"* && "$file_name" != *"\\"* && "$file_name" != "." && "$file_name" != ".." && "$file_name" == *.md ]]
}

is_valid_sha256() {
    local digest="$1"
    [[ "$digest" =~ ^[0-9a-f]{64}$ ]]
}

# 检查目标文件是否为清单中登记且未经人工修改的工具产物
is_unmodified_manifest_entry() {
    local output_dir="$1"
    local file_name="$2"
    local manifest_path="$output_dir/$MANIFEST_NAME"
    local target_file="$output_dir/$file_name"
    if ! is_valid_manifest_filename "$file_name"; then
        return 1
    fi
    if [[ ! -f "$manifest_path" || -L "$manifest_path" || ! -f "$target_file" || -L "$target_file" ]]; then
        return 1
    fi
    local recorded_sha="" line_sha="" line_name=""
    while IFS=$'\t' read -r line_sha line_name || [[ -n "$line_sha" ]]; do
        line_name="${line_name%$'\r'}"
        if [[ "$line_name" == "$file_name" ]] && is_valid_sha256 "$line_sha"; then
            recorded_sha="$line_sha"
        fi
    done < "$manifest_path"
    if [[ -z "$recorded_sha" ]]; then
        return 1
    fi
    local actual_sha
    actual_sha=$(compute_file_sha256 "$target_file")
    [[ "$actual_sha" == "$recorded_sha" ]]
}

# 登记由本工具生成的单个 Markdown 文件及其 SHA-256 摘要（<sha256>\t<filename>）
record_generated_file() {
    local output_dir="$1"
    local file_name="$2"
    local digest="$3"
    local manifest_path="$output_dir/$MANIFEST_NAME"
    if ! is_valid_manifest_filename "$file_name" || ! is_valid_sha256 "$digest"; then
        return 1
    fi
    local tmp_manifest="$output_dir/.${MANIFEST_NAME}.tmp.$$"
    : > "$tmp_manifest"
    if [[ -f "$manifest_path" && ! -L "$manifest_path" ]]; then
        local line_sha="" line_name=""
        while IFS=$'\t' read -r line_sha line_name || [[ -n "$line_sha" ]]; do
            line_name="${line_name%$'\r'}"
            if [[ "$line_name" != "$file_name" ]] && is_valid_sha256 "$line_sha" && is_valid_manifest_filename "$line_name"; then
                printf '%s\t%s\n' "$line_sha" "$line_name" >> "$tmp_manifest"
            fi
        done < "$manifest_path"
    fi
    printf '%s\t%s\n' "$digest" "$file_name" >> "$tmp_manifest"
    mv -f -- "$tmp_manifest" "$manifest_path"
}

# 初始化日志：已有日志采用追加写入并在清理时保留，仅新建日志标记为本次会话产物
init_log_file() {
    mkdir -p "$(dirname "$LOG_FILE")"
    if [[ -e "$LOG_FILE" || -L "$LOG_FILE" ]]; then
        LOG_CREATED_BY_SESSION=0
        echo "${LOG_HEADER_PREFIX}$(date)" >> "$LOG_FILE"
    else
        echo "${LOG_HEADER_PREFIX}$(date)" > "$LOG_FILE"
        LOG_CREATED_BY_SESSION=1
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
    local skipped_count=0
    local total_count=0
    
    for pdf_file in "$SOURCE_DIR"/*.pdf; do
        if [[ -f "$pdf_file" ]]; then
            total_count=$((total_count + 1))
            local pdf_name
            pdf_name=$(basename "$pdf_file")
            local md_name="${pdf_name%.pdf}_basic.md"
            local md_path="$output_dir/$md_name"
            local tmp_path="$output_dir/.${md_name}.tmp.$$"

            if [[ -e "$md_path" || -L "$md_path" ]] && ! is_unmodified_manifest_entry "$output_dir" "$md_name"; then
                log_warning "跳过已存在且归属无法确认或已被修改的目标文件: $md_path"
                skipped_count=$((skipped_count + 1))
                continue
            fi
            
            log "转换: $pdf_name"
            
            if markitdown "$pdf_file" > "$tmp_path" 2>> "$LOG_FILE"; then
                local md_sha
                md_sha=$(compute_file_sha256 "$tmp_path")
                mv -f -- "$tmp_path" "$md_path"
                record_generated_file "$output_dir" "$md_name" "$md_sha"
                log_success "转换成功: $pdf_name"
                success_count=$((success_count + 1))
            else
                rm -f -- "$tmp_path"
                log_error "转换失败: $pdf_name"
            fi
        fi
    done
    
    log "基础转换完成: 成功 $success_count/$total_count 个文件，跳过 $skipped_count 个已有目标文件"
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

# 清理转换结果（仅删除清单中确认由本工具生成且内容摘要未变更的文件；已修改、未登记及已有自定义日志均保留）
cleanup_results() {
    collect_unique_output_dirs
    local files_to_delete=()
    local files_to_delete_sha=()
    local preserved_modified_files=()
    local manifests_to_delete=()
    local seen_files=$'\n'
    local seen_modified=$'\n'
    local dir manifest_path recorded_sha entry target_file actual_sha

    for dir in "${UNIQUE_OUTPUT_DIRS[@]}"; do
        manifest_path="$dir/$MANIFEST_NAME"
        if [[ -f "$manifest_path" && ! -L "$manifest_path" ]]; then
            manifests_to_delete+=("$manifest_path")
            while IFS=$'\t' read -r recorded_sha entry || [[ -n "$recorded_sha" ]]; do
                entry="${entry%$'\r'}"
                if ! is_valid_sha256 "$recorded_sha" || ! is_valid_manifest_filename "$entry"; then
                    continue
                fi
                target_file="$dir/$entry"
                if [[ -f "$target_file" && ! -L "$target_file" ]]; then
                    actual_sha=""
                    if actual_sha=$(compute_file_sha256 "$target_file" 2>/dev/null) && is_valid_sha256 "$actual_sha" && [[ "$actual_sha" == "$recorded_sha" ]]; then
                        if [[ "$seen_files" != *$'\n'"$target_file"$'\n'* ]]; then
                            files_to_delete+=("$target_file")
                            files_to_delete_sha+=("$recorded_sha")
                            seen_files+="$target_file"$'\n'
                        fi
                    else
                        if [[ "$seen_modified" != *$'\n'"$target_file"$'\n'* ]]; then
                            preserved_modified_files+=("$target_file")
                            seen_modified+="$target_file"$'\n'
                        fi
                    fi
                fi
            done < "$manifest_path"
        fi
    done

    local log_to_delete=""
    if [[ "$LOG_CREATED_BY_SESSION" -eq 1 && -f "$LOG_FILE" && ! -L "$LOG_FILE" ]]; then
        log_to_delete="$LOG_FILE"
    fi

    if [[ ${#preserved_modified_files[@]} -gt 0 ]]; then
        echo
        echo -e "${YELLOW}提示：以下文件生成后内容已被修改或无法读取，已自动保留，不会删除：${NC}"
        for target_file in "${preserved_modified_files[@]}"; do
            echo "  - $target_file"
        done
    fi

    if [[ ${#files_to_delete[@]} -eq 0 && -z "$log_to_delete" ]]; then
        echo
        echo "未发现可确认由本工具生成且未经修改的转换结果（原有文件、已修改文件及已有日志将保持保留）。"
        return 0
    fi

    echo
    echo -e "${YELLOW}警告：仅删除以下可确认由本工具生成且未经修改的转换结果文件（其余文件与目录将保持保留）：${NC}"
    for target_file in "${files_to_delete[@]}"; do
        echo "  - $target_file"
    done
    if [[ -n "$log_to_delete" ]]; then
        echo "  - $log_to_delete (本次新建的工具日志)"
    fi
    read -p "确定要继续吗？(y/N): " confirm
    
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        local idx expected_sha recheck_sha
        for idx in "${!files_to_delete[@]}"; do
            target_file="${files_to_delete[$idx]}"
            expected_sha="${files_to_delete_sha[$idx]}"
            if [[ ! -f "$target_file" || -L "$target_file" ]]; then
                echo -e "${YELLOW}⚠ 跳过并保留（预览后已变更或已不存在）: $target_file${NC}"
                continue
            fi
            recheck_sha=""
            if ! recheck_sha=$(compute_file_sha256 "$target_file" 2>/dev/null) || ! is_valid_sha256 "$recheck_sha" || [[ "$recheck_sha" != "$expected_sha" ]]; then
                echo -e "${YELLOW}⚠ 跳过并保留（预览后已变更或无法读取）: $target_file${NC}"
                continue
            fi
            rm -f -- "$target_file"
            echo -e "${GREEN}✓ 已删除生成文件: $target_file${NC}"
        done

        for manifest_path in "${manifests_to_delete[@]}"; do
            if [[ -f "$manifest_path" && ! -L "$manifest_path" ]]; then
                rm -f -- "$manifest_path"
            fi
        done
        
        if [[ -n "$log_to_delete" && -f "$log_to_delete" && ! -L "$log_to_delete" ]]; then
            rm -f -- "$log_to_delete"
            LOG_CREATED_BY_SESSION=0
            echo -e "${GREEN}✓ 已清理本次新建日志文件: $log_to_delete${NC}"
        fi
        
        echo "清理完成！（仅删除确认由工具生成且未经修改的文件，其余文件已保留）"
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
    init_log_file
    
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
                if [[ -f "$LOG_FILE" ]]; then
                    log "退出程序"
                fi
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
