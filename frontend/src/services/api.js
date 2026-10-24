import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,   // send cookies
  timeout: 15000,
})

// Global response interceptor — redirect to login on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      // Dispatch a custom event so AuthContext can react
      window.dispatchEvent(new CustomEvent('pb:unauthorized'))
    }
    return Promise.reject(err)
  }
)

export default api

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const authApi = {
  status: () => api.get('/auth/status'),
  login: (username, password) => api.post('/auth/login', { username, password }),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
  setup: (username, password) => api.post('/auth/setup', { username, password }),
}

// ─── System ───────────────────────────────────────────────────────────────────

export const systemApi = {
  health: () => api.get('/system/health'),
  dashboardStats: () => api.get('/system/dashboard-stats'),
  schedulerStatus: () => api.get('/system/scheduler-status'),
  storageStats: () => api.get('/system/storage-stats'),
  cleanup: () => api.post('/system/cleanup'),
  logs: (limit = 20) => api.get('/system/logs', { params: { limit } }),
  shutdown: () => api.post('/system/shutdown'),
}

// ─── Sources ──────────────────────────────────────────────────────────────────

export const sourcesApi = {
  list: () => api.get('/sources'),
  create: (data) => api.post('/sources', data),
  get: (id) => api.get(`/sources/${id}`),
  update: (id, data) => api.put(`/sources/${id}`, data),
  delete: (id) => api.delete(`/sources/${id}`),
  testUrl: (url) => api.post('/sources/test-url', { url }),
  testSource: (id) => api.post(`/sources/${id}/test`),
  refresh: (id) => api.post(`/sources/${id}/refresh`),
  refreshAll: () => api.post('/sources/refresh-all'),
  seedDefaults: () => api.post('/sources/seed-defaults'),
}

// ─── Articles ─────────────────────────────────────────────────────────────────

export const articlesApi = {
  list: (params) => api.get('/articles', { params }),
  get: (id) => api.get(`/articles/${id}`),
  related: (id) => api.get(`/articles/${id}/related`),
  update: (id, data) => api.patch(`/articles/${id}`, data),
  categories: () => api.get('/articles/categories'),
}

// ─── Drafts & Post Studio ─────────────────────────────────────────────────────

export const draftsApi = {
  list: (params) => api.get('/drafts', { params }),
  create: (data) => api.post('/drafts', data),
  get: (id) => api.get(`/drafts/${id}`),
  update: (id, data) => api.put(`/drafts/${id}`, data),
  approve: (id) => api.post(`/drafts/${id}/approve`),
  preview: (data) => api.post('/drafts/preview', data),
  universalTemplate: () => api.get('/drafts/templates/universal-custom'),
  uploadUniversalTemplate: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/drafts/templates/universal-custom/upload', form)
  },
  removeUniversalTemplate: () => api.delete('/drafts/templates/universal-custom'),
  delete: (id) => api.delete(`/drafts/${id}`),
  markPublished: (id, platformPostId) =>
    api.post(`/drafts/${id}/mark-published`, null, { params: { platform_post_id: platformPostId } }),
  getImageUrl: (id) => `/api/drafts/${id}/image`,
}

// ─── Publishing & Meta API ───────────────────────────────────────────────────

export const publishingApi = {
  status: () => api.get('/publishing/status'),
  publish: (draftId) => api.post(`/publishing/${draftId}`),
  history: (limit = 50) => api.get('/publishing/history', { params: { limit } }),
}



