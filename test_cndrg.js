/**
 * 寻找不依赖 ICU 的 CHS-DRG vs CN-DRG 差异
 */
const fs = require('fs');
const path = require('path');

function loadEngine(file) {
  const code = fs.readFileSync(path.join(__dirname, 'apps/medqc-web/src/views/drg-grouper', file), 'utf8');
  const start = code.indexOf('(()=>{');
  const end = code.lastIndexOf('return S})()');
  return eval(code.substring(start, end + 'return S})()'.length));
}
const chs = loadEngine('sichuan2024Grouper.js');
const cn = loadEngine('cnDrg2023Grouper.js');

function groupWith(engine, zdList, ssList, gender, age, days) {
  const cce = engine.CCE[zdList[0]] ? String(engine.CCE[zdList[0]]) : '';
  const mccList = [], ccList = [];
  for (const zd of zdList) {
    if (engine.MCC[zd] && (cce === '' || String(engine.MCC[zd]) !== cce)) { mccList.push(zd); continue; }
    if (engine.CC[zd] && (cce === '' || String(engine.CC[zd]) !== cce)) { ccList.push(zd); }
  }
  const ssValidList = ssList.filter(s => engine.SS_VALID.includes(s));
  return engine.group_record({
    Index: 'TEST', gender, age, ageDay: 0, weight: 0,
    dept: '', inHospitalTime: days, leavingType: '1',
    zdList, ssList, remark: '', icu: '',
    cce, mccList, ccList, ssValidList,
  });
}

// 大量测试用例 - 不带 ICU
const cases = [
  // 各种常见内科诊断 - 不同合并症组合
  { zd: ['J44.100', 'J96.000'], ss: [], g: '1', a: 70, d: 14 }, // COPD+呼衰
  { zd: ['I63.900', 'E11.900', 'I10.x01'], ss: [], g: '1', a: 75, d: 20 }, // 脑卒中+糖尿病+高血压
  { zd: ['I50.900', 'I10.x01', 'E11.900'], ss: [], g: '1', a: 68, d: 12 }, // 心衰+高血压+糖尿病
  { zd: ['J18.100', 'J96.000', 'I10.x01'], ss: [], g: '1', a: 60, d: 15 }, // 肺炎+呼衰+高血压
  { zd: ['A41.900', 'R57.200'], ss: [], g: '1', a: 55, d: 20 }, // 败血症+休克
  { zd: ['N18.500', 'I10.x01'], ss: ['39.9500'], g: '1', a: 55, d: 5 }, // 慢性肾病+透析
  { zd: ['K72.905'], ss: [], g: '1', a: 50, d: 10 }, // 肝功能不全
  { zd: ['C34.900'], ss: [], g: '1', a: 60, d: 10 }, // 肺癌
  { zd: ['C34.900', 'J96.000'], ss: ['32.4900'], g: '1', a: 60, d: 20 }, // 肺癌+呼衰+肺手术
  { zd: ['C22.003'], ss: ['50.2200'], g: '1', a: 55, d: 15 }, // 肝癌+肝切除
  { zd: ['I25.100x001', 'E11.900'], ss: [], g: '1', a: 65, d: 8 }, // 冠心病+糖尿病
  { zd: ['F20.000'], ss: [], g: '1', a: 35, d: 30 }, // 精神分裂
  { zd: ['F20.000'], ss: [], g: '1', a: 35, d: 65 }, // 精神分裂 >60天
  { zd: ['G40.900'], ss: [], g: '1', a: 10, d: 7 }, // 癫痫 儿童
  { zd: ['G40.900'], ss: [], g: '1', a: 30, d: 7 }, // 癫痫 成人
  { zd: ['N18.500'], ss: ['39.9500'], g: '1', a: 50, d: 3 }, // 肾透析
  { zd: ['I21.001', 'I50.900'], ss: [], g: '1', a: 65, d: 10 }, // 急性心梗+心衰
  { zd: ['J96.000', 'J44.100'], ss: ['96.7100'], g: '1', a: 70, d: 15 }, // 呼衰+COPD+呼吸机
  { zd: ['K85.900', 'K72.905'], ss: [], g: '1', a: 45, d: 12 }, // 急性胰腺炎+肝功能不全
  { zd: ['I63.900'], ss: [], g: '1', a: 70, d: 65 }, // 脑卒中住>60天
];

console.log('=== 无ICU差异检测 ===\n');
let diffCount = 0;
for (const c of cases) {
  const chsR = groupWith(chs, c.zd, c.ss, c.g, c.a, c.d);
  const cnR = groupWith(cn, c.zd, c.ss, c.g, c.a, c.d);
  if (chsR.drg !== cnR.drg) {
    diffCount++;
    console.log(`⚡ 差异 #${diffCount}`);
    console.log(`   诊断: ${c.zd.join(', ')}`);
    console.log(`   手术: ${c.ss.join(', ') || '无'}`);
    console.log(`   性别=${c.g === '1' ? '男' : '女'} 年龄=${c.a} 天数=${c.d}`);
    console.log(`   CHS-DRG: ${chsR.status} → ${chsR.drg || '无'} (${chsR.messages?.join('; ')})`);
    console.log(`   CN-DRG:  ${cnR.status} → ${cnR.drg || '无'} (${cnR.messages?.join('; ')})`);
    console.log();
  }
}
if (diffCount === 0) {
  console.log('未发现无ICU差异，以上所有用例两个引擎结果一致。');
}
