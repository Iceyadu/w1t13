import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { addToRetryQueue, cacheResponse, getCached } from '@/services/offlineCache'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL
    ? `${import.meta.env.VITE_API_BASE_URL}/api/v1`
    : '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Auth token interceptor
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('harborview_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // Add idempotency key for write operations if not present
  if (['post', 'put', 'patch'].includes(config.method?.toLowerCase() || '')) {
    if (!config.headers['Idempotency-Key']) {
      config.headers['Idempotency-Key'] = crypto.randomUUID()
    }
  }
  return config
})

// Response interceptor: cache GETs, handle offline writes
api.interceptors.response.use(
  async (response) => {
    // Cache successful GET responses
    if (response.config.method?.toLowerCase() === 'get' && response.config.url) {
      try {
        await cacheResponse(response.config.url, response.data)
      } catch {
        // Encryption not initialized yet — skip caching
      }
    }
    return response
  },
  async (error: AxiosError) => {
    // 401 — redirect to login
    if (error.response?.status === 401) {
      localStorage.removeItem('harborview_token')
      localStorage.removeItem('harborview_user')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }

    // Network error (offline) — handle differently for reads vs writes
    if (!error.response && error.config) {
      const method = error.config.method?.toLowerCase() || ''

      if (method === 'get' && error.config.url) {
        // Serve from cache for GET requests
        try {
          const cached = await getCached(error.config.url)
          if (cached !== null) {
            return { data: cached, status: 200, statusText: 'OK (cached)', headers: {}, config: error.config }
          }
        } catch {
          // Cache unavailable
        }
      }

      if (['post', 'put', 'patch', 'delete'].includes(method)) {
        const idempotencyKey = (error.config.headers as Record<string, string>)?.['Idempotency-Key'] || crypto.randomUUID()
        try {
          // Handle FormData (multipart) vs JSON
          let queueData: unknown = null
          const rawContentType =
          error.config.headers?.['Content-Type'] ?? error.config.headers?.['content-type']
        
          const contentType =
            typeof rawContentType === 'string'
              ? rawContentType
              : Array.isArray(rawContentType)
                ? rawContentType.join('; ')
                : ''
          if (error.config.data instanceof FormData) {
            // Convert FormData to a serializable object; store files as blobs separately
            const obj: Record<string, string> = {}
            const fileEntries: Array<{ key: string; file: File }> = []
            ;(error.config.data as FormData).forEach((value, key) => {
              if (value instanceof File) {
                fileEntries.push({ key, file: value })
              } else if (typeof value === 'string') {
                obj[key] = value
              }
            })
            queueData = { _formData: true, fields: obj, _hasBlobs: fileEntries.length > 0 }

            const { storeBlobForQueue } = await import('@/services/offlineCache')
            const queueId = await addToRetryQueue({
              method: method.toUpperCase(),
              url: error.config.url || '',
              data: queueData,
              headers: {
                'Content-Type': 'multipart/form-data',
                'Idempotency-Key': idempotencyKey,
                'If-Match': (error.config.headers as Record<string, string>)?.['If-Match'] || '',
              },
              idempotencyKey,
            })

            for (const entry of fileEntries) {
              await storeBlobForQueue(queueId, entry.key, entry.file)
            }

            return {
              data: { _queued: true, _message: 'Saved offline. Will sync when connection is restored.' },
              status: 202,
              statusText: 'Queued Offline',
              headers: {},
              config: error.config,
            }
          } else if (typeof error.config.data === 'string') {
            try { queueData = JSON.parse(error.config.data) } catch { queueData = error.config.data }
          } else {
            queueData = error.config.data
          }

          await addToRetryQueue({
            method: method.toUpperCase(),
            url: error.config.url || '',
            data: queueData,
            headers: {
              'Content-Type': contentType.includes('multipart') ? 'multipart/form-data' : 'application/json',
              'Idempotency-Key': idempotencyKey,
              'If-Match': (error.config.headers as Record<string, string>)?.['If-Match'] || '',
            },
            idempotencyKey,
          })
          return {
            data: { _queued: true, _message: 'Saved offline. Will sync when connection is restored.' },
            status: 202,
            statusText: 'Queued Offline',
            headers: {},
            config: error.config,
          }
        } catch { /* queue failed */ }
      }
    }

    return Promise.reject(error)
  }
)

export default api
