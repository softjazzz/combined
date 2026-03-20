# 任务：从 OpenDRG webpack chunk 中提取可执行的 DRG 分组引擎

## 背景

[OpenDRG](https://github.com/OpenDRG) 是一个开源的 CHS-DRG 分组器平台。其在线演示站 https://opendrg.github.io/ 是一个纯前端 SPA，所有分组逻辑都编译在 webpack chunk JS 文件中。

我们已经将其静态站克隆到本地：`OpenDRG/opendrg.github.io/`

## 核心问题

我需要从四川省 DRG 方案的 webpack chunk 文件 `OpenDRG/opendrg.github.io/2002.js`（约 2MB）中，提取出 `group_record` 函数，使其能在我们的 Vue 3 前端页面中独立调用，**不依赖 webpack runtime**。

## 文件结构

```
OpenDRG/opendrg.github.io/
├── index.html          # SPA 入口
├── runtime.js          # webpack runtime (~10KB)
├── index.js            # 主程序：UI + 公共逻辑 (~500KB)
├── 2002.js             # ★ 四川方案 chunk（~2MB）— 包含完整分组引擎
└── *.js                # 其他方案的 chunk
```

## 2002.js 的内部结构

这个 webpack chunk 导出以下内容：

```javascript
// 导出映射（在文件开头附近）
x.d(S, {
  CC: () => h,           // CC（并发症）编码字典
  CCE: () => _,          // CCE（并发症排除）编码字典
  MCC: () => d,          // MCC（严重并发症）编码字典
  SS_VALID: () => f,     // 有效手术编码列表
  group_record: () => m, // ★ 核心分组函数
  group_record_str: () => w  // 字符串版本的分组函数
});
```

### 数据部分

- `_` (CCE): `JSON.parse('{ICD编码: MDC排除组号, ...}')` — 27143 条
- `d` (MCC): `JSON.parse('{ICD编码: MDC排除组号, ...}')` — 4477 条
- `h` (CC): `JSON.parse('{ICD编码: MDC排除组号, ...}')` — 8009 条
- `f` (SS_VALID): `JSON.parse('[手术编码, ...]')` — 9314 条

### 分组逻辑部分

- `Q` 类：包含所有 `XX19_group(x)`, `XX21_group(x)` 等函数（794 个 DRG 的条件判断）
- `m` 函数 (`group_record`)：主入口函数，按 MDC A→Z 顺序逐一匹配 ADRG

### group_record 函数签名

```javascript
// 输入参数 x 的结构：
x = {
  gender: "1" | "2",        // 性别：1=男，2=女
  age: 30,                  // 年龄
  zdList: ["K80.501", "K80.100x001", ...],  // 诊断编码列表（第一个是主诊断）
  ssList: ["51.8803", "51.8701", ...],      // 手术/操作编码列表
}

// 返回值结构（推测）：
result = {
  drg: "GY15",            // DRG 编码
  adrg: "GY",             // ADRG 编码
  mdc: "G",               // MDC 编码
  // ... 可能还有其他字段
}
```

### 分组逻辑伪代码

```
group_record(x):
  1. 校验输入（性别、诊断不能为空）
  2. 依次尝试 MDC A → Z：
     对每个 MDC：
       依次尝试每个 ADRG（如 AA、AB、AC...）：
         检查 x.ssList[0]（主手术）是否在该 ADRG 的手术编码列表中
         如果匹配 → 进入该 ADRG
           根据 MCC/CC/诊断数量等条件选择最终 DRG
           返回结果
  3. 无手术操作的病例 → 匹配内科 ADRG（如 GZ = 内科综合组）
  4. 所有 MDC 都不匹配 → 返回"未入组"
```

### CCE 的真正用途

CCE 值 **不是** ADRG 索引，而是 **MCC/CC 排除组标识**。用法：

```javascript
// 主诊断的 CCE 值
T = CCE[主诊断编码]  // 例如 K80.501 → "113"

// 判断其他诊断是否算 MCC：
if (MCC.hasOwnProperty(其他诊断) && MCC[其他诊断] !== T) {
  // 算 MCC（排除同组的）
}
```

## 需要完成的工作

### 方案 A：从 chunk 中提取 group_record 为独立模块（推荐）

1. 解析 `2002.js` 的 webpack chunk 格式
2. 提取模块代码（去掉 webpack 包装器）
3. 将其改写为一个**自包含的 ES Module**，导出 `group_record` 函数
4. 保存为 `apps/medqc-web/src/views/drg-grouper/sichuan2024Grouper.js`
5. 在我们的 Vue 组件中 `import { group_record } from './sichuan2024Grouper'` 调用

### 方案 B：通过 script 标签动态加载

1. 将 `2002.js` 复制到 `public/drg-rules/sichuan_2024/` 目录
2. 创建一个加载器，通过 `<script>` 标签加载并模拟 webpack runtime
3. 提取 `group_record` 函数供 Vue 调用

## 验证用例

胆总管结石病例：

```javascript
const input = {
  gender: "2",   // 女
  age: 30,
  zdList: ["K80.501", "K80.100x001", "K83.109", "K72.905", "E11.900"],
  ssList: ["51.8803", "51.8701", "51.2300"],
};

const result = group_record(input);
// 预期：MDC G（肝胆胰），ADRG GY 或类似，DRG 应该是 G 开头的编码
// 绝对不应该是 FF21（那是外周血管手术组）
```

## 现有 Vue 组件位置

- 分组器页面: `apps/medqc-web/src/views/drg-grouper/DrgGrouperView.vue`
- 分组引擎（需重写）: `apps/medqc-web/src/views/drg-grouper/drgGrouper.ts`

当前 `drgGrouper.ts` 中的 `performGrouping()` 函数需要改为调用从 chunk 中提取的 `group_record`。
