#!/bin/bash
# PDF to Markdown 转换脚本
# 将源目录中的 PDF 文件转换为 Markdown 格式（默认使用脚本同级目录与可重建虚拟环境）

set -e  # 遇到错误时退出

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 定义目录路径（支持通过环境变量覆盖）
SOURCE_DIR="${PDF_SOURCE_DIR:-$SCRIPT_DIR/医保规则}"
OUTPUT_DIR="${PDF_OUTPUT_DIR:-$SCRIPT_DIR/医保规则_md}"
LOG_FILE="${PDF_LOG_FILE:-$SCRIPT_DIR/conversion.log}"
VENV_DIR="${PDF_CONVERTER_VENV:-$SCRIPT_DIR/.venv}"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 检查 Python 是否安装
check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装，请先安装 Python3"
        exit 1
    fi
    log_success "Python3 已安装"
}

# 安装 Python 依赖
install_dependencies() {
    log "正在安装 Python 依赖包..."
    
    local venv_dir="$VENV_DIR"
    
    # 创建虚拟环境
    if [[ ! -d "$venv_dir" ]]; then
        log "创建 Python 虚拟环境: $venv_dir"
        if python3 -m venv "$venv_dir" &>> "$LOG_FILE"; then
            log_success "虚拟环境创建成功"
        else
            log_error "虚拟环境创建失败"
            return 1
        fi
    fi
    
    # 激活虚拟环境
    # shellcheck disable=SC1091
    source "$venv_dir/bin/activate"
    
    # 升级 pip
    pip install --upgrade pip &>> "$LOG_FILE"
    
    if [[ -f "$REQUIREMENTS_FILE" ]]; then
        if pip install -r "$REQUIREMENTS_FILE" &>> "$LOG_FILE"; then
            log_success "requirements.txt 依赖安装成功"
            return 0
        else
            log_warning "requirements.txt 批量安装失败，尝试逐项安装"
        fi
    fi
    
    # 逐项安装兜底
    for pkg in markitdown pymupdf pdfplumber pandas tabulate; do
        if pip install "$pkg" &>> "$LOG_FILE"; then
            log_success "$pkg 安装成功"
        else
            log_warning "$pkg 安装失败"
        fi
    done
}

# 使用 markitdown 转换单个文件
convert_with_markitdown() {
    local pdf_file="$1"
    local md_file="$2"
    local venv_dir="$VENV_DIR"
    
    # 检查虚拟环境中的 markitdown
    if [[ -x "$venv_dir/bin/markitdown" ]]; then
        if "$venv_dir/bin/markitdown" "$pdf_file" > "$md_file" 2>> "$LOG_FILE"; then
            return 0
        fi
    elif command -v markitdown &> /dev/null; then
        if markitdown "$pdf_file" > "$md_file" 2>> "$LOG_FILE"; then
            return 0
        fi
    fi
    return 1
}

# 使用 Python 脚本转换
convert_with_python() {
    local pdf_file="$1"
    local md_file="$2"
    local py_bin="python3"
    if [[ -x "$VENV_DIR/bin/python" ]]; then
        py_bin="$VENV_DIR/bin/python"
    fi
    
    "$py_bin" - "$pdf_file" "$md_file" <<'PY' 2>> "$LOG_FILE"
import sys
from pathlib import Path
try:
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(sys.argv[1])
    Path(sys.argv[2]).write_text(result.text_content, encoding="utf-8")
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
PY
}

# 转换单个 PDF 文件
convert_single_pdf() {
    local pdf_path="$1"
    local pdf_name=$(basename "$pdf_path")
    local md_name="${pdf_name%.pdf}.md"
    local md_path="$OUTPUT_DIR/$md_name"
    
    log "转换: $pdf_name -> $md_name"
    
    # 尝试使用 markitdown 命令行工具
    log "尝试使用 markitdown 命令行工具..."
    if convert_with_markitdown "$pdf_path" "$md_path"; then
        log_success "使用 markitdown 转换成功: $pdf_name"
        return 0
    fi
    
    # 尝试使用 Python markitdown 库
    log "尝试使用 Python markitdown 库..."
    if convert_with_python "$pdf_path" "$md_path"; then
        log_success "使用 Python markitdown 转换成功: $pdf_name"
        return 0
    fi
    
    log_error "转换失败: $pdf_name"
    return 1
}

# 主转换函数
convert_all_pdfs() {
    local success_count=0
    local total_count=0
    local failed_files=()
    
    # 检查源目录是否存在
    if [[ ! -d "$SOURCE_DIR" ]]; then
        log_error "源目录不存在: $SOURCE_DIR"
        exit 1
    fi
    
    # 创建输出目录
    mkdir -p "$OUTPUT_DIR"
    
    # 查找所有 PDF 文件
    log "在 $SOURCE_DIR 中查找 PDF 文件..."
    
    # 使用数组存储 PDF 文件路径
    mapfile -t pdf_files < <(find "$SOURCE_DIR" -maxdepth 1 -name "*.pdf" -print)
    
    if [[ ${#pdf_files[@]} -eq 0 ]]; then
        log_warning "没有找到 PDF 文件"
        return
    fi
    
    log "找到 ${#pdf_files[@]} 个 PDF 文件"
    
    # 转换每个文件
    for pdf_file in "${pdf_files[@]}"; do
        ((total_count++))
        if convert_single_pdf "$pdf_file"; then
            ((success_count++))
        else
            failed_files+=("$(basename "$pdf_file")")
        fi
    done
    
    # 输出转换结果
    echo
    log "转换完成!"
    log "成功转换: $success_count/$total_count 个文件"
    
    if [[ ${#failed_files[@]} -gt 0 ]]; then
        log_warning "转换失败的文件:"
        for file in "${failed_files[@]}"; do
            log_warning "  - $file"
        done
    fi
    
    log "输出目录: $OUTPUT_DIR"
    log "日志文件: $LOG_FILE"
}

# 显示帮助信息
show_help() {
    echo "PDF to Markdown 转换脚本"
    echo
    echo "用法: $0 [选项]"
    echo
    echo "选项:"
    echo "  -h, --help     显示此帮助信息"
    echo "  -i, --install  仅安装依赖包"
    echo "  -c, --convert  仅进行转换（跳过依赖安装）"
    echo
    echo "默认行为: 安装依赖并进行转换"
    echo
    echo "源目录: $SOURCE_DIR"
    echo "输出目录: $OUTPUT_DIR"
}

# 主函数
main() {
    local install_only=false
    local convert_only=false
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -i|--install)
                install_only=true
                shift
                ;;
            -c|--convert)
                convert_only=true
                shift
                ;;
            *)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 初始化日志文件
    echo "PDF to Markdown 转换日志 - $(date)" > "$LOG_FILE"
    
    log "PDF to Markdown 转换器启动"
    log "源目录: $SOURCE_DIR"
    log "输出目录: $OUTPUT_DIR"
    echo
    
    # 检查 Python
    check_python
    
    # 安装依赖（除非指定了 --convert）
    if [[ "$convert_only" != true ]]; then
        install_dependencies
        echo
    fi
    
    # 进行转换（除非指定了 --install）
    if [[ "$install_only" != true ]]; then
        convert_all_pdfs
    fi
    
    log "脚本执行完成"
}

# 运行主函数
main "$@"
