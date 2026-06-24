/**
 * 测试修复后的患者信息提取功能
 */

// 模拟从实际病历中提取患者信息的函数
function extractPatientInfoFromText(text) {
  const result = {}

  // 提取患者姓名
  const namePatterns = [
    /姓名[:：]\s*([^\s\n,，。]+)/,
    /患者\s*([^\s\n,，。]+)，/,
    /患者姓名[:：]\s*([^\s\n,，。]+)/,
    /病人\s*([^\s\n,，。]+)，/
  ]
  
  for (const pattern of namePatterns) {
    const match = text.match(pattern)
    if (match && match[1] && match[1].trim().length >= 2) {
      const extractedName = match[1].trim()
      if (/^[\u4e00-\u9fa5]{2,4}$/.test(extractedName)) {
        result.patientName = extractedName
        break
      }
    }
  }

  // 提取年龄
  const agePatterns = [
    /年龄[:：]\s*(\d+)[岁]?/,
    /(\d+)岁/,
    /，(\d+)岁，/,
    /患者[^，]*，[^，]*，(\d+)岁/
  ]
  
  for (const pattern of agePatterns) {
    const match = text.match(pattern)
    if (match && match[1]) {
      const extractedAge = parseInt(match[1])
      if (extractedAge > 0 && extractedAge < 150) {
        result.patientAge = extractedAge
        break
      }
    }
  }

  // 提取性别
  const genderPatterns = [
    /性别[:：]\s*([男女])/,
    /患者[^，]*，([男女])，/,
    /，([男女])性，/,
    /，([男女])，\d+岁/
  ]
  
  for (const pattern of genderPatterns) {
    const match = text.match(pattern)
    if (match && match[1]) {
      result.patientGender = match[1] === '男' ? '男' : '女'
      break
    }
  }

  // 提取科室
  const deptPatterns = [
    /科室[:：]\s*([^\s\n,，。]+)/,
    /入院科室[:：]\s*([^\s\n,，。]+)/,
    /([^\s]+科)\s*病程记录/,
    /([^\s]+科)\s*住院病历/
  ]
  
  for (const pattern of deptPatterns) {
    const match = text.match(pattern)
    if (match && match[1] && match[1].trim().length >= 2) {
      const extractedDept = match[1].trim()
      if (/科$/.test(extractedDept) || /部$/.test(extractedDept)) {
        result.department = extractedDept
        break
      }
    }
  }

  // 提取主要诊断
  const diagnosisPatterns = [
    /初步诊断[:：]\s*\d*\.?\s*([^\n\r]+)/,
    /入院诊断[:：]\s*\d*\.?\s*([^\n\r]+)/,
    /术前诊断[:：]\s*\d*\.?\s*([^\n\r]+)/,
    /主要诊断[:：]\s*([^\n\r]+)/
  ]
  
  for (const pattern of diagnosisPatterns) {
    const match = text.match(pattern)
    if (match && match[1] && match[1].trim().length >= 2) {
      result.primaryDiagnosis = match[1].trim()
      break
    }
  }

  return result
}

// 使用实际的病历文本进行测试
const realMedicalRecord = `=== 第1页 ===
首次病程记录
2025-03-30 01:08
患者张伟，性别男，年龄44岁，以"发现肛旁肿物疼痛2+天"为主诉于2025年03月29日 13:49入
院。 
本病例特点：
1. 患者为44岁男性，起病缓，病程短
2.发现肛旁肿物疼痛2+天
3.一般情况良好。有慢病病史"甲减"病史，现口服优甲乐（具体不详）。否认传染病史。否认
外伤史 ，有手术史2024-10-01行体外冲击波碎石术，否认输血史，无预防接种史，否认过敏史。
否认特殊病史。
4.体格检查：T36.3℃，P98次/分，R20次/分，BP147/95mmHg,身高170cm,体重75Kg。 截石位，肛
门居中，肛门2-3点位方向见一大小约4.0cm*3.0cm肿块，红肿明显，无破溃，扪及中央波动感，
皮温升高；指诊：肛管稍紧，肛直环3-4点位变硬，皮温高，触痛明显，肛管直肠下段未扪及肿
块，直肠粘膜无松弛，退出指套无血染。
5.暂无 
初步诊断：1.肛周脓肿
诊断依据：1.肛周脓肿：依据：患者张伟，性别男，年龄44岁，以"发现肛旁肿物疼痛2+天"为
主诉于2025年03月29日 13:49入院。查体： 截石位，肛门居中，肛门2-3点位方向见一大小约4.
0cm*3.0cm肿块，红肿明显，无破溃，扪及中央波动感，皮温升高；指诊：肛管稍紧，肛直环3-4
点位变硬，皮温高，触痛明显，肛管直肠下段未扪及肿块，直肠粘膜无松弛，退出指套无血染。

泸县人民医院
病 程 记 录
科室：外二科
姓名：张伟
年龄：44岁
性别：男
床号：54
住院号:350827
第(1)页`

console.log('🧪 测试修复后的患者信息提取功能')
console.log('=' .repeat(50))

const extracted = extractPatientInfoFromText(realMedicalRecord)

console.log('📊 提取结果:')
console.log(`  患者姓名: ${extracted.patientName || '未识别'}`)
console.log(`  性别: ${extracted.patientGender || '未识别'}`)
console.log(`  年龄: ${extracted.patientAge || '未识别'}`)
console.log(`  科室: ${extracted.department || '未识别'}`)
console.log(`  主要诊断: ${extracted.primaryDiagnosis || '未识别'}`)

// 验证结果
const expected = {
  patientName: '张伟',
  patientGender: '男',
  patientAge: 44,
  department: '外二科',
  primaryDiagnosis: '肛周脓肿'
}

console.log('\n✅ 验证结果:')
let allCorrect = true

Object.keys(expected).forEach(key => {
  const isCorrect = extracted[key] === expected[key]
  console.log(`  ${key}: ${isCorrect ? '✅' : '❌'} (期望: ${expected[key]}, 实际: ${extracted[key] || '未识别'})`)
  if (!isCorrect) allCorrect = false
})

console.log(`\n🎯 整体结果: ${allCorrect ? '🎉 全部正确!' : '❌ 需要进一步调试'}`)

if (allCorrect) {
  console.log('\n✨ 患者信息提取功能修复成功！')
  console.log('现在可以在前端界面中看到完整的患者基本信息了。')
} else {
  console.log('\n⚠️  部分信息提取仍有问题，需要进一步优化正则表达式。')
}
