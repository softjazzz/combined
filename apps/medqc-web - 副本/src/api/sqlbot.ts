import { http } from '@/utils/http'

export type SQLBotDisplayMode = 'iframe' | 'disabled'

export interface SQLBotConfigResponse {
  enabled: boolean
  base_url?: string | null
  embed_url?: string | null
  app_id?: string | null
  display_mode: SQLBotDisplayMode
  message: string
}

export const sqlbotApi = {
  async getConfig(): Promise<SQLBotConfigResponse> {
    const response = await http.get<SQLBotConfigResponse>('/api/v1/sqlbot/config')
    return response.data
  },
}

export default sqlbotApi
