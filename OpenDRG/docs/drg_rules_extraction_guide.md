# OpenDRG 演示平台 DRG 分组规则提取指南

## 背景

OpenDRG 的**源码仓库**（DRG_Python、DRG_JavaScript 等）仅包含较早版本的分组规则（CHS-DRG 1.0），
但其**演示平台** [opendrg.github.io](https://opendrg.github.io) 已支持 39 个地方方案（含 CHS-DRG 2.0 及各省市 2024/2025 年版本）。

这些新方案的规则数据嵌入在编译后的 webpack chunk JS 文件中，本文档说明如何从中提取可用数据。

## 演示平台文件结构

```
opendrg.github.io/
├── index.html          # 入口页面
├── index.js            # 主路由 + 支付规则 + 方案映射表
├── 1735.js             # chs_drg_20（CHS-DRG 2.0）
├── 7231.js             # beijing_2024（北京 2024版）
├── 4077.js             # shanghai_2023（上海 2023版）
├── ...                 # 其他方案的 chunk 文件
└── (其他静态资源)
```

### 方案与 chunk 文件映射

在 `index.js` 中可以找到完整映射：

```javascript
"./chs_drg_20.js": [1735, 1735]    // → 1735.js
"./beijing_2024.js": [7231, 7231]  // → 7231.js
"./shanghai_2023.js": [4077, 4077] // → 4077.js
// ... 共 39 个方案
```

## 每个 chunk 文件包含的数据

每个方案 chunk 文件导出 6 个核心对象：

| 导出名 | JS变量 | 数据类型 | 说明 |
|--------|--------|----------|------|
| `CCE` | `d` | `{ICD编码: MDC分组号}` | ICD诊断编码 → MDC 分组映射 |
| `MCC` | `h` | `{ICD编码: MDC分组号}` | 严重并发症/合并症编码列表 |
| `CC` | `f` | `{ICD编码: MDC分组号}` | 并发症/合并症编码列表 |
| `SS_VALID` | `z` | `[手术编码数组]` | 有效手术/操作编码列表 |
| `group_record` | `V` | `function` | 分组入口函数（接收病案对象） |
| `group_record_str` | `m` | `function` | 分组入口函数（接收 CSV 字符串） |

> **注意**：不同方案文件中变量名可能不同（如 CCE 可能不总是 `d`），
> 但导出名 `CCE`/`MCC`/`CC`/`SS_VALID` 是一致的。

## 数据存储格式

数据以 `JSON.parse('...')` 方式内联在 JS 代码中：

```javascript
const d = JSON.parse('{"A00.000x001":"1","A00.100x001":"1",...}')  // CCE
,h = JSON.parse('{"A00.100x001":"1","A02.100":"1",...}')           // MCC  
,f = JSON.parse('{"A01.200":"1","A02.000":"1",...}')               // CC
,z = JSON.parse('["00.2400x001","00.5000x001",...]')              // SS_VALID
```

## 提取方法

### 方法一：使用提取脚本（推荐）

项目中已提供 Python 提取脚本 `extract_drg_rules.py`：

```bash
cd OpenDRG
python extract_drg_rules.py
```

默认提取 CHS-DRG 2.0（`1735.js`），结果保存到 `extracted_rules/chs_drg_20/`。

修改脚本中的 `JS_FILE` 和 `OUTPUT_DIR` 变量即可提取其他方案：

```python
JS_FILE = Path(__file__).parent / "opendrg.github.io" / "7231.js"       # 北京2024版
OUTPUT_DIR = Path(__file__).parent / "extracted_rules" / "beijing_2024"
```

### 方法二：手动提取

1. 打开 chunk JS 文件
2. 搜索 `JSON.parse('` 定位数据段
3. 提取单引号之间的 JSON 字符串
4. 用 `json.loads()` 解析

### 方法三：浏览器控制台提取

```javascript
// 在 opendrg.github.io 页面的开发者控制台中执行
// 先选择一个方案（如 CHS-DRG 2.0），等页面加载完成

// 获取当前方案的模块
const mod = await import('./chs_drg_20.js');
console.log('CCE:', JSON.stringify(mod.CCE));
console.log('MCC:', JSON.stringify(mod.MCC));
console.log('CC:', JSON.stringify(mod.CC));
console.log('SS_VALID:', JSON.stringify(mod.SS_VALID));
```

## 提取结果（CHS-DRG 2.0 示例）

```
extracted_rules/chs_drg_20/
├── cce_icd_to_mdc.json          # 27,143 条 ICD→MDC 映射
├── mcc_major_complications.json  #  4,477 条 MCC 编码
├── cc_complications.json         #  8,009 条 CC 编码
├── ss_valid_procedures.json      #  9,376 条有效手术编码
└── drg_groups.json               # 252 ADRG / 634 DRG 分组定义
```

## 数据用途说明

### CCE — 主诊断分组

```
主诊断 ICD 编码 → 查 CCE → 得到 MDC 分组号 → 进入对应 MDC 的分组逻辑
```

### MCC / CC — 并发症升组

```
其他诊断中是否存在 MCC 编码 → 升至 MCC 组 (后缀 11/21/31)
其他诊断中是否存在 CC 编码  → 升至 CC 组  (后缀 13/23/33)
均不存在                     → 无并发症组  (后缀 15/25/35)
```

### SS_VALID — 手术有效性判断

```
患者手术编码是否在 SS_VALID 列表中 → 决定是否进入手术 ADRG
```

### DRG 编码规则

```
DRG 编码 = 4位字符，如 "BB11"
  第1位 = MDC 标识字母 (A-Z)
  第2位 = ADRG 标识字母
  第3-4位 = 分组后缀
    19/29/39 = 独立组（不区分 CC/MCC）
    11/21/31 = MCC 组
    13/23/33 = CC/MCC 组  
    15/25/35 = 无并发症组
```

## 注意事项

> [!WARNING]
> 不同变量名映射可能随版本变化，提取前需先确认导出映射关系（搜索 `:\(\)=>`）。

> [!IMPORTANT]
> 分组逻辑函数中的**编码数组**（用于 ADRG 入组判断的诊断/手术编码列表）
> 嵌入在代码逻辑中而非独立数据结构，需要更深入的解析才能完整提取。
