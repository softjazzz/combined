import type { DOMWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'

// 日期选择器在打开面板后通过回车提交键入值。
export async function setDatePickerValue(input: DOMWrapper<Element>, value: string) {
  await input.trigger('mousedown')
  await input.setValue(value)
  const enter = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
  Object.defineProperty(enter, 'which', { value: 13 })
  input.element.dispatchEvent(enter)
  await nextTick()
}
