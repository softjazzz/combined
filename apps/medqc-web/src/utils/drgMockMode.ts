const DRG_MOCK_MODE_KEY = 'medqc_drg_mock_mode'
const DRG_MOCK_MODE_EVENT = 'medqc:drg-mock-mode-changed'

function getDefaultMockMode(): boolean {
  return (import.meta as any).env?.VITE_USE_DRG_MOCK !== 'false'
}

export function isDrgMockModeEnabled(): boolean {
  if (typeof window === 'undefined') return getDefaultMockMode()
  try {
    const raw = window.localStorage.getItem(DRG_MOCK_MODE_KEY)
    if (raw === null) return getDefaultMockMode()
    return raw === 'true'
  } catch {
    return getDefaultMockMode()
  }
}

export function setDrgMockModeEnabled(enabled: boolean): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(DRG_MOCK_MODE_KEY, String(enabled))
  } catch {
    // no-op: storage unavailable
  }
  window.dispatchEvent(
    new CustomEvent(DRG_MOCK_MODE_EVENT, {
      detail: { enabled }
    })
  )
}

export function onDrgMockModeChange(callback: (enabled: boolean) => void): () => void {
  if (typeof window === 'undefined') return () => {}

  const customEventHandler = (event: Event) => {
    const detailEnabled = (event as CustomEvent<{ enabled?: boolean }>).detail?.enabled
    callback(typeof detailEnabled === 'boolean' ? detailEnabled : isDrgMockModeEnabled())
  }

  const storageEventHandler = (event: StorageEvent) => {
    if (event.key !== DRG_MOCK_MODE_KEY) return
    callback(event.newValue === 'true')
  }

  window.addEventListener(DRG_MOCK_MODE_EVENT, customEventHandler)
  window.addEventListener('storage', storageEventHandler)

  return () => {
    window.removeEventListener(DRG_MOCK_MODE_EVENT, customEventHandler)
    window.removeEventListener('storage', storageEventHandler)
  }
}
