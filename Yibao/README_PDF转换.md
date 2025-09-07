# PDF to Markdown 转换器

这个工具可以将 `/home/ubuntu/Yibao/医保规则` 目录中的所有 PDF 文件批量转换为 Markdown 格式。

## 🚀 快速开始

**推荐使用最新的交互式转换器：**

```bash
cd /home/ubuntu/Yibao
./final_converter.sh
```

## 📁 文件说明

### 核心脚本
- `final_converter.sh` - **交互式转换器**（推荐使用）
- `precise_table_converter.py` - **精确表格转换器**（专门优化表格结构）
- `convert_pdfs.sh` - 基础转换脚本
- `pdf_to_md_converter.py` - Python 转换脚本

### 配置文件
- `requirements.txt` - Python 依赖包列表

## 🎯 转换方式对比

| 转换方式 | 适用场景 | 优点 | 缺点 |
|---------|---------|------|------|
| **精确表格转换** | 医保规则、表格文档 | 表格结构清晰，易于阅读 | 处理时间较长 |
| 基础转换 | 一般文档 | 速度快，保留原始格式 | 表格格式可能混乱 |

## 使用方法

### 方法一：交互式转换器（推荐）

```bash
# 进入项目目录
cd /home/ubuntu/Yibao

# 运行交互式转换器
./final_converter.sh
```

选择转换方式：
- **选项1**: 基础转换 - 快速转换，适合一般文档
- **选项2**: 精确表格转换 - 专门优化表格结构，适合医保规则文档
- **选项3**: 全部转换 - 同时使用两种方式

### 方法二：直接使用精确转换器

```bash
# 进入项目目录
cd /home/ubuntu/Yibao

# 激活虚拟环境
source pdf_converter_venv/bin/activate

# 运行精确表格转换器
python precise_table_converter.py
```

### 方法三：使用基础转换脚本

```bash
# 进入项目目录
cd /home/ubuntu/Yibao

# 运行转换脚本（会自动安装依赖并转换）
./convert_pdfs.sh
```

其他选项：

```bash
# 仅安装依赖包
./convert_pdfs.sh --install

# 仅进行转换（跳过依赖安装）
./convert_pdfs.sh --convert

# 显示帮助信息
./convert_pdfs.sh --help
```

### 方法二：使用 Python 脚本

```bash
# 安装依赖包
pip3 install -r requirements.txt

# 运行 Python 脚本
python3 pdf_to_md_converter.py
```

## 输出结果

转换后的 Markdown 文件将保存在 `/home/ubuntu/Yibao/医保规则_md` 目录中。

每个 PDF 文件会生成对应的 `.md` 文件，例如：
- `第一批-1.药品区分性别使用.pdf` → `第一批-1.药品区分性别使用.md`

## 转换工具

脚本会按优先级尝试以下转换工具：

1. **markitdown** - 微软开源的转换工具（推荐，效果最好）
2. **pymupdf** - 基于 MuPDF 的 Python 库
3. **pdfplumber** - 专门用于 PDF 文本提取的库

## 日志文件

转换过程中的详细日志会保存在 `/home/ubuntu/Yibao/conversion.log` 文件中。

## 故障排除

### 如果转换失败

1. 检查 PDF 文件是否损坏
2. 查看日志文件了解具体错误信息
3. 尝试手动安装依赖包：
   ```bash
   pip3 install markitdown pymupdf pdfplumber
   ```

### 如果依赖安装失败

```bash
# 更新 pip
python3 -m pip install --upgrade pip

# 安装依赖
pip3 install markitdown pymupdf pdfplumber
```

### 权限问题

如果遇到权限问题，可以尝试：

```bash
# 给脚本添加执行权限
chmod +x convert_pdfs.sh

# 或者使用 sudo 运行
sudo ./convert_pdfs.sh
```

## 当前 PDF 文件列表

源目录中包含以下 PDF 文件：

- 第一批-1.药品区分性别使用.pdf
- 第一批-2.医疗服务项目区分性别使用.pdf
- 第一批-3.药品儿童专用.pdf
- 第一批-4.药品限儿童使用.pdf
- 第一批-5.医疗服务项目儿童专用.pdf
- 第三批-1 药品限工伤保险.pdf
- 第三批-2 药品限生育保险.pdf
- 第二批 "手术项目未按规定折价收费"规则对应知识点明细.pdf
- 第五批 药品限医疗机构级别.pdf
- 第六批 药品限支付疗程.pdf
- 第四批 药品限就医方式.pdf

总共 11 个 PDF 文件将被转换为 Markdown 格式。
