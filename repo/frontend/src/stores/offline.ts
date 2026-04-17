import { defineStore } from 'pinia'
import { ref } from 'vue'
import { initEncryption, clearEncryption, getQueueLength, clearRetryQueue, clearCache } from '@/services/offlineCache'

export const useOfflineStore = defineStore('offline', () => {
  const isEncryptionReady = ref(false)
  const pendingWrites = ref(0)

  async function setupEncryption(password: string, saltB64: string): Promise<void> {
    await initEncryption(password, saltB64)
    isEncryptionReady.value = true
  }

  async function teardownEncryption(): Promise<void> {
    clearEncryption()
    isEncryptionReady.value = false
  }

  async function refreshPendingCount(): Promise<void> {
    try {
      pendingWrites.value = await getQueueLength()
    } catch {
      pendingWrites.value = 0
    }
  }

  async function clearAll(): Promise<void> {
    await clearRetryQueue()
    await clearCache()
    pendingWrites.value = 0
  }

  return {
    isEncryptionReady,
    pendingWrites,
    setupEncryption,
    teardownEncryption,
    refreshPendingCount,
    clearAll,
  }
})
