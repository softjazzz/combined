## Supabase 语义质控规则（qc_rules）增删改查操作指南

本文档说明如何在本项目中对 `qc_rules` 表进行新增、查询、更新、删除操作。覆盖三种常用方式：
- 前端/后端 API
- Supabase SQL（Web 控制台）
- 后端脚本（Python）

### 一、表结构要点
- 主键：`id (uuid)` 自动生成
- 唯一键：`rule_code (varchar)` 建议以来源前缀命名，例如 `SC-001`
- 约束枚举：
  - `category` ∈ `completeness | accuracy | timeliness | consistency | compliance`
  - `rule_type` ∈ `logical | semantic | hybrid`
  - `severity` ∈ `critical | major | minor`
- 非空：`rule_code`, `name`, `category`, `check_logic`, `created_by`

建议的最小字段集：
```json
{
  "rule_code": "SC-001",
  "name": "主诉与现病史一致性检查",
  "description": "描述……",
  "category": "consistency",
  "rule_type": "semantic",
  "severity": "minor",
  "check_logic": {},
  "is_active": true,
  "version": "1.0"
}
```

---

### 二、通过后端 API（推荐，已做字段映射与校验）
后端基础地址：`/api/semantic-rules`

1) 查询（分页/总数）
```bash
GET /api/semantic-rules?page=1&page_size=50
# 返回：{ success, rules: [...], count }
```

2) 批量导入/更新
```bash
POST /api/semantic-rules/import
Content-Type: application/json
{
  "rules": [ { 最小字段集… }, ... ]
}
# 后端会：
# - 自动做 category/rule_type/severity 的中英文映射
# - 若存在相同 rule_code 则更新；否则删除重插确保唯一
```

3) 单条创建 / 更新 / 删除
```bash
POST   /api/semantic-rules            # 创建
PUT    /api/semantic-rules/{rule_id}  # 按 id 或 rule_code 更新（内部已兼容）
DELETE /api/semantic-rules/{rule_id}  # 按 id 或 rule_code 删除（内部已兼容）
```

4) 导出
```bash
GET /api/semantic-rules/export
```

备注：开发环境通过 Vite 代理，无需写绝对地址；生产环境走 Nginx 反代。

---

### 三、通过 Supabase SQL（Web 控制台）

1) 查询总数与分布
```sql
-- 总数
select count(*) from public.qc_rules;

-- 四川规则
select count(*) from public.qc_rules where rule_code like 'SC-%';

-- 非四川（平台示例/其他来源）
select count(*) from public.qc_rules where rule_code not like 'SC-%';
```

2) 新增
```sql
insert into public.qc_rules (
  rule_code, name, description, category, rule_type, severity,
  check_logic, is_active, version, created_by
) values (
  'SC-999', '示例规则', '描述', 'consistency', 'semantic', 'minor',
  '{}'::jsonb, true, '1.0', '<某个 user_profiles.id>'
);
```

3) 更新
```sql
update public.qc_rules
set name = '新的名称', severity = 'major', updated_at = now()
where rule_code = 'SC-999';
```

4) 删除
```sql
delete from public.qc_rules where rule_code in ('COMP_001','CONS_001','TIME_001');
```

---

### 四、通过后端脚本（Python）
在 `apps/medqc-web/backend` 虚拟环境中执行：
```bash
cd apps/medqc-web/backend
. .venv/bin/activate
python - <<'PY'
import os, json
from app.core.supabase_client import get_supabase
sb = get_supabase()

rec = {
  'rule_code': 'SC-998',
  'name': '脚本插入示例',
  'description': '描述',
  'category': 'consistency',
  'rule_type': 'semantic',
  'severity': 'minor',
  'check_logic': {},
  'is_active': True,
  'version': '1.0'
}

# 如果存在则更新，否则插入
try:
  sb.table('qc_rules').update(rec).eq('rule_code', rec['rule_code']).execute()
except Exception:
  pass
sb.table('qc_rules').insert(rec).execute()
print('OK')
PY
```

---

### 五、常见问题（FAQ）
- 422/400 错误：多为 `page_size > 200` 或枚举不合法（category/rule_type/severity）。
- category 中文值：已在后端导入接口做映射（如“一致/语义”→`consistency`，“准确”→`accuracy`）。
- `check_logic` 为 NOT NULL：无具体逻辑时用 `{}` 占位。
- `created_by` 外键：可在 `user_profiles` 表中取任意 `id` 填充。

---

### 六、变更记录
- 2025-09-09：补充导入映射与前端统计逻辑，形成本文档。


