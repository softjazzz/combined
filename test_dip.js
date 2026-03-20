const fs = require('fs');
const f = fs.readFileSync('apps/medqc-web/src/views/drg-grouper/sichuan2024Grouper.js', 'utf8');
console.log('文件大小(KB):', (f.length / 1024).toFixed(1));

// 搜索导出和关键字段
const keywords = ['DRG_INFO', 'drg_name', 'DRG_NAME', 'RW', '权重', 'group_name', 'groupName', 'drg_info', 'drgInfo'];
keywords.forEach(kw => {
  const count = (f.match(new RegExp(kw, 'g')) || []).length;
  if (count > 0) console.log(`  ${kw}: ${count} 次`);
});

// 找exports
const exportMatch = f.match(/exports\.(\w+)/g);
if (exportMatch) {
  const uniq = [...new Set(exportMatch)];
  console.log('\n导出项:', uniq);
}

// 找 return 对象中可能的字段（分组结果）
const resultFields = f.match(/['"]?(status|mdc|adrg|drg|messages|rw|weight|name|drgName|groupInfo)['"]?\s*[=:]/gi);
if (resultFields) {
  const uniq = [...new Set(resultFields.map(s => s.toLowerCase()))];
  console.log('\n结果字段:', uniq);
}
