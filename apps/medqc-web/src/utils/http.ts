// @ts-nocheck
import axios from 'axios'

export const http = axios.create({
  baseURL: '',
  timeout: 30000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('medqc_access_token')
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

