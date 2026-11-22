// @ts-nocheck
import { STANDARD_REQUEST_TIMEOUT_MS } from '@/config/requestTimeouts'
import axios from 'axios'
import { clinicalSourceForRequest } from './clinical-source'
import { getAccessToken } from '@/utils/auth-token'
import { attachTraceIdToError, ensureTraceHeaders, extractTraceIdFromResponse } from '@/utils/trace'

export const http = axios.create({
  baseURL: '',
  timeout: STANDARD_REQUEST_TIMEOUT_MS,
})

http.interceptors.request.use((config) => {
  const source = clinicalSourceForRequest(config.url, config.method)
  if (source) {
    config.headers = config.headers || {}
    config.headers['X-Clinical-Source'] = source
  }
  const token = getAccessToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  const { headers } = ensureTraceHeaders(config.headers as Record<string, unknown>)
  config.headers = headers
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const traceId = extractTraceIdFromResponse(error?.response) || extractTraceIdFromResponse(error)
    attachTraceIdToError(error, traceId)
    return Promise.reject(error)
  },
)
