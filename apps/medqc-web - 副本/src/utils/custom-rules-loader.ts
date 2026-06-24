const customRulesUrl = new URL('../../backend/app/data/custom_rules_33.json', import.meta.url).href

let customRulesPromise: Promise<any[]> | null = null

export async function loadCustomRules(): Promise<any[]> {
  if (!customRulesPromise) {
    customRulesPromise = fetch(customRulesUrl).then(async (response) => {
      if (!response.ok) {
        throw new Error(`加载自定义规则失败: HTTP ${response.status}`)
      }

      return response.json() as Promise<any[]>
    })
  }

  return customRulesPromise
}
