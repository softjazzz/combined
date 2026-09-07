import boy from '@/assets/avatar-icons/patient-icon-boy.png'
import elderMan from '@/assets/avatar-icons/patient-icon-elder-man.png'
import elderWoman from '@/assets/avatar-icons/patient-icon-elder-woman.png'
import girl from '@/assets/avatar-icons/patient-icon-girl.png'
import man from '@/assets/avatar-icons/patient-icon-man.png'
import woman from '@/assets/avatar-icons/patient-icon-woman.png'

// 列表与复核预览共用现有头像选择规则。
export function patientAvatarSrc(row: { patientSex?: string; patientAge?: number }): string {
  const age = Number(row.patientAge || 0)
  const female = /女|female|^f$/i.test(String(row.patientSex || '').trim())
  if (Number.isFinite(age) && age > 0 && age < 14) return female ? girl : boy
  if (Number.isFinite(age) && age >= 55) return female ? elderWoman : elderMan
  return female ? woman : man
}
