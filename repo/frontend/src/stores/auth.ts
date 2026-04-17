import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'
import { useOfflineStore } from '@/stores/offline'

interface AuthUser {
  id: string
  username: string
  role: string
  canary_enabled: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(sessionStorage.getItem('harborview_token') || localStorage.getItem('harborview_token'))
  const refreshToken = ref<string | null>(sessionStorage.getItem('harborview_refresh') || localStorage.getItem('harborview_refresh'))
  const user = ref<AuthUser | null>(JSON.parse(sessionStorage.getItem('harborview_user') || localStorage.getItem('harborview_user') || 'null'))
  const isAuthenticated = computed(() => !!token.value)

  async function login(username: string, password: string): Promise<void> {
    const resp = await api.post('/auth/login', { username, password })
    token.value = resp.data.access_token
    refreshToken.value = resp.data.refresh_token
    user.value = resp.data.user
    sessionStorage.setItem('harborview_token', resp.data.access_token)
    sessionStorage.setItem('harborview_refresh', resp.data.refresh_token)
    sessionStorage.setItem('harborview_user', JSON.stringify(resp.data.user))
    localStorage.removeItem('harborview_token')
    localStorage.removeItem('harborview_refresh')
    localStorage.removeItem('harborview_user')
    // Initialize offline encryption with a per-user random salt (stored in localStorage).
    // The derived key is kept in-memory only and re-derived on each login.
    const offlineStore = useOfflineStore()
    const { getOrCreateUserSalt } = await import('@/services/offlineCache')
    const saltB64 = getOrCreateUserSalt(resp.data.user.id)
    await offlineStore.setupEncryption(password, saltB64)
  }

  async function logout() {
    if (refreshToken.value) {
      try {
        await api.post('/auth/logout', { refresh_token: refreshToken.value })
      } catch {
        // Best-effort token revocation; still clear local session.
      }
    }
    token.value = null
    refreshToken.value = null
    user.value = null
    sessionStorage.removeItem('harborview_token')
    sessionStorage.removeItem('harborview_refresh')
    sessionStorage.removeItem('harborview_user')
    localStorage.removeItem('harborview_token')
    localStorage.removeItem('harborview_refresh')
    localStorage.removeItem('harborview_user')
    const offlineStore = useOfflineStore()
    offlineStore.teardownEncryption()
    offlineStore.clearAll()
  }

  function loadFromStorage() {
    token.value = sessionStorage.getItem('harborview_token') || localStorage.getItem('harborview_token')
    refreshToken.value = sessionStorage.getItem('harborview_refresh') || localStorage.getItem('harborview_refresh')
    const stored = sessionStorage.getItem('harborview_user') || localStorage.getItem('harborview_user')
    user.value = stored ? JSON.parse(stored) : null
    if (token.value) sessionStorage.setItem('harborview_token', token.value)
    if (refreshToken.value) sessionStorage.setItem('harborview_refresh', refreshToken.value)
    if (user.value) sessionStorage.setItem('harborview_user', JSON.stringify(user.value))
    localStorage.removeItem('harborview_token')
    localStorage.removeItem('harborview_refresh')
    localStorage.removeItem('harborview_user')
    // Offline encryption key is in-memory only and re-derived on next login.
  }

  function hasRole(...roles: string[]): boolean {
    return !!user.value && roles.includes(user.value.role)
  }

  return { token, refreshToken, user, isAuthenticated, login, logout, loadFromStorage, hasRole }
})
