/**
 * 本地测试 sichuan2024Grouper.js 分组引擎
 * 用法: node test_grouper.js
 */

// 加载分组引擎（CommonJS require 需要的是 exports，但模块用了 ESM export）
// 由 Codex 提取的模块最终代码会 export { CC, CCE, MCC, SS_VALID, group_record }
// 我们需要使用动态 import

async function main() {
  // 使用动态 import 加载 ESM 模块
  const grouper = await import('./apps/medqc-web/src/views/drg-grouper/sichuan2024Grouper.js')
  
  const { CC, CCE, MCC, SS_VALID, group_record } = grouper

  console.log('=== 分组引擎加载成功 ===')
  console.log(`CCE 编码数: ${Object.keys(CCE).length}`)
  console.log(`MCC 编码数: ${Object.keys(MCC).length}`)
  console.log(`CC  编码数: ${Object.keys(CC).length}`)
  console.log(`SS_VALID 编码数: ${Array.isArray(SS_VALID) ? SS_VALID.length : Object.keys(SS_VALID).length}`)

  // 预处理函数（和 drgGrouper.ts 中的逻辑一致）
  function getPrimaryCce(zdList) {
    const primary = zdList[0]
    if (!primary || !CCE.hasOwnProperty(primary)) return ''
    return String(CCE[primary] ?? '')
  }

  function collectComplications(zdList, cce) {
    const mccList = []
    const ccList = []
    for (const zd of zdList) {
      if (MCC.hasOwnProperty(zd) && (cce.length === 0 || String(MCC[zd]) !== cce)) {
        mccList.push(zd)
        continue
      }
      if (CC.hasOwnProperty(zd) && (cce.length === 0 || String(CC[zd]) !== cce)) {
        ccList.push(zd)
      }
    }
    return { mccList, ccList }
  }

  function collectValidProcedures(ssList) {
    if (!Array.isArray(SS_VALID)) return []
    return ssList.filter(ss => SS_VALID.includes(ss))
  }

  // 测试用例
  const testCases = [
    {
      name: '胆总管结石 (K80.501)',
      input: {
        gender: '2', age: 30,
        zdList: ['K80.501', 'K80.100x001', 'K83.109', 'K72.905', 'E11.900'],
        ssList: ['51.8803', '51.8701', '51.2300'],
      },
    },
    {
      name: '急性阑尾炎 (K35.800)',
      input: {
        gender: '1', age: 45,
        zdList: ['K35.800'],
        ssList: ['47.0100'],
      },
    },
    {
      name: '股骨颈骨折 (S72.000)',
      input: {
        gender: '2', age: 70,
        zdList: ['S72.000'],
        ssList: ['81.5100'],
      },
    },
  ]

  console.log('\n=== 分组测试 ===\n')

  for (const tc of testCases) {
    const { zdList, ssList, gender, age } = tc.input
    const cce = getPrimaryCce(zdList)
    const { mccList, ccList } = collectComplications(zdList, cce)
    const ssValidList = collectValidProcedures(ssList)

    const result = group_record({
      Index: 'TEST',
      gender,
      age: Number(age),
      ageDay: 0,
      weight: 0,
      dept: '',
      inHospitalTime: 15,
      leavingType: '1',
      zdList,
      ssList,
      remark: '',
      icu: '',
      cce,
      mccList,
      ccList,
      ssValidList,
    })

    console.log(`【${tc.name}】`)
    console.log(`  状态: ${result.status}`)
    console.log(`  MDC:  ${result.mdc}`)
    console.log(`  ADRG: ${result.adrg}`)
    console.log(`  DRG:  ${result.drg}`)
    if (result.messages) {
      console.log(`  消息: ${result.messages.join(' | ')}`)
    }
    console.log()
  }
}

main().catch(e => { console.error('ERROR:', e); process.exit(1) })
