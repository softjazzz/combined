# Deprecated Scripts (废弃脚本)

本目录包含已废弃的质控规则 Prompt 生成脚本。

## 废弃日期
2025-10-28

## 废弃原因

这些脚本在设计阶段用于批量生成单规则的 prompt 模板，但存在以下问题：

### 1. JSON 结构不匹配
- **脚本生成的模板使用**: `violation` / `reason` / `suggestion`
- **运行时期望的结构**: `is_compliant` / `findings` / `evidence` / `location` / `suggestion` / `confidence`
- **影响**: 生成的模板无法被运行时系统解析，导致开发工作浪费

### 2. prompt_template 字段未被使用
- 脚本将生成的模板写入数据库的 `prompt_template` 字段
- 但运行时的 `sichuan_qc_service.py` 中的 `_build_prompt()` 方法完全不读取该字段
- 实际使用的是运行时动态构建的 Prompt 模板

### 3. 维护成本高
- 需要同时维护两套 Prompt 模板系统（脚本生成 + 运行时模板）
- 规则的 `description` 字段已经过优化，可以直接用于运行时 Prompt 构建
- 统一使用运行时模板可以降低维护复杂度

## 当前解决方案

**采用方案A：废弃脚本生成，统一使用运行时模板**

- 运行时 Prompt 构建位于: `app/services/sichuan_qc_service.py::_build_prompt()`
- 规则配置数据源: `app/data/sichuan_rules_146.json`
- 规则的 `description` 字段用于 Prompt 中的规则说明

## 未来方案（如需恢复）

如果未来需要支持规则级别的特殊 Prompt 定制，需要：

1. **升级脚本的 JSON 结构**，使其与运行时一致
2. **修改运行时代码**，支持读取 `prompt_template` 字段
3. **更新现有数据库记录**，将旧模板转换为新结构

## 文件清单

- `generate_prompt_templates.py` - 批量生成单规则 Prompt 模板
- `build_prompts_from_rest.py` - 基于 REST API 构建 Prompt 模板

## 相关优化（2025-10-28）

在废弃这些脚本的同时，运行时 Prompt 系统进行了以下优化：

### P3: 规则ID映射传递
- ✅ 在规则清单中显示 `rule_id`
- ✅ 添加独立的"规则ID映射"段落
- ✅ 支持多字段兜底 (`rule_id` / `id` / `rule_code`)

### P4: 智能内容截断
- ✅ 实现 `_smart_truncate()` 方法
- ✅ 优先保留完整段落和句子
- ✅ 添加截断提示信息

### P5: 输出约束强化
- ✅ 添加"硬性约束"要求（数量、顺序、rule_id）
- ✅ 添加"自检清单"提示 LLM 验证输出

详见: `app/services/sichuan_qc_service.py` (2025-10-28 优化版本)

---

**注意**: 如需引用这些脚本的逻辑，请查看本目录下的源文件，但不建议直接使用。
