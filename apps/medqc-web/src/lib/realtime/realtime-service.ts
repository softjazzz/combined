import { supabase } from '../backend-store'

export type RealtimeOperation = 'INSERT' | 'UPDATE' | 'DELETE'

export interface RealtimeEventPayload {
  schema?: string
  table: string
  new?: Record<string, unknown>
  old?: Record<string, unknown>
  [key: string]: unknown
}

export interface RealtimeEvent {
  type: RealtimeOperation
  timestamp: number
  payload: RealtimeEventPayload
}

type RealtimeListener = (event: RealtimeEvent) => void

class RealtimeService {
  private readonly listeners = new Map<string, Set<RealtimeListener>>()

  private connected = false

  private connecting = false

  private channel: { unsubscribe?: () => Promise<unknown> } | null = null

  get isConnected(): boolean {
    return this.connected
  }

  async reconnect(): Promise<void> {
    if (this.connected || this.connecting) {
      this.connected = true
      return
    }

    this.connecting = true
    try {
      await this.disconnect()
      const channel = supabase.channel('medqc-realtime')
      this.channel = channel as { unsubscribe?: () => Promise<unknown> }
      channel.subscribe?.(() => undefined)
      this.connected = true
    } finally {
      this.connecting = false
    }
  }

  addEventListener(table: string, listener: RealtimeListener): void {
    const normalizedTable = table.trim()
    if (!normalizedTable) {
      return
    }

    const existing = this.listeners.get(normalizedTable)
    if (existing) {
      existing.add(listener)
    } else {
      this.listeners.set(normalizedTable, new Set([listener]))
    }

    void this.reconnect()
  }

  removeEventListener(table: string, listener: RealtimeListener): void {
    const normalizedTable = table.trim()
    const existing = this.listeners.get(normalizedTable)
    if (!existing) {
      return
    }

    existing.delete(listener)
    if (existing.size === 0) {
      this.listeners.delete(normalizedTable)
    }
  }

  async disconnect(): Promise<void> {
    this.connected = false
    if (this.channel && typeof this.channel.unsubscribe === 'function') {
      await this.channel.unsubscribe()
    }
    this.channel = null
  }

  emit(table: string, event: RealtimeEvent): void {
    const listeners = this.listeners.get(table)
    if (!listeners || listeners.size === 0) {
      return
    }

    listeners.forEach((listener) => {
      listener({
        ...event,
        payload: {
          ...event.payload,
          table,
        },
      })
    })
  }
}

let realtimeServiceInstance: RealtimeService | null = null

export function getRealtimeService(): RealtimeService {
  if (!realtimeServiceInstance) {
    realtimeServiceInstance = new RealtimeService()
  }
  return realtimeServiceInstance
}
