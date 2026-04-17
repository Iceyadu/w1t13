import Dexie, { type Table } from 'dexie'

interface CachedRecord {
  key: string
  data: string // encrypted JSON string
  iv: string   // base64 encoded IV
  cachedAt: number
}

interface RetryQueueRecord {
  id?: number
  queueId: string
  method: string
  url: string
  data: string // encrypted JSON
  iv: string
  headers: string // encrypted JSON
  headersIv: string
  idempotencyKey: string
  createdAt: number
  retryCount: number
}

interface SyncMetadataRecord {
  key: string
  value: string
  updatedAt: number
}

interface BlobRecord {
  id?: number
  queueId: string
  fieldName: string
  blob: Blob
  filename: string
  contentType: string
}

class OfflineDatabase extends Dexie {
  cached_records!: Table<CachedRecord, string>
  retry_queue!: Table<RetryQueueRecord, number>
  sync_metadata!: Table<SyncMetadataRecord, string>
  blob_store!: Table<BlobRecord, number>

  constructor() {
    super('HarborViewOfflineDB')
    this.version(3).stores({
      cached_records: 'key',
      retry_queue: '++id, queueId, createdAt',
      sync_metadata: 'key',
      blob_store: '++id, queueId',
    })
  }
}

const db = new OfflineDatabase()

// --- Encryption helpers using Web Crypto API (AES-256-GCM) ---

let _cryptoKey: CryptoKey | null = null

/**
 * Returns the persisted per-user random salt (base64), creating and storing one if absent.
 * The salt is non-sensitive and is kept in localStorage so key derivation is stable across
 * sessions for the same user on the same device.
 */
export function getOrCreateUserSalt(userId: string): string {
  const storageKey = `harborview_salt_${userId}`
  const existing = localStorage.getItem(storageKey)
  if (existing) return existing
  const saltBytes = crypto.getRandomValues(new Uint8Array(16))
  const saltB64 = btoa(String.fromCharCode(...saltBytes))
  localStorage.setItem(storageKey, saltB64)
  return saltB64
}

export async function initEncryption(password: string, saltB64: string): Promise<void> {
  const enc = new TextEncoder()
  const keyMaterial = await crypto.subtle.importKey(
    'raw', enc.encode(password), 'PBKDF2', false, ['deriveKey']
  )
  const saltBytes = Uint8Array.from(atob(saltB64), c => c.charCodeAt(0))
  _cryptoKey = await crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: saltBytes, iterations: 100000, hash: 'SHA-256' },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  )
}

export function clearEncryption(): void {
  _cryptoKey = null
}

function getKey(): CryptoKey {
  if (!_cryptoKey) throw new Error('Encryption not initialized. Call initEncryption first.')
  return _cryptoKey
}

async function encrypt(plaintext: string): Promise<{ ciphertext: string; iv: string }> {
  const key = getKey()
  const enc = new TextEncoder()
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const encrypted = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv }, key, enc.encode(plaintext)
  )
  return {
    ciphertext: btoa(String.fromCharCode(...new Uint8Array(encrypted))),
    iv: btoa(String.fromCharCode(...iv)),
  }
}

async function decrypt(ciphertext: string, ivB64: string): Promise<string> {
  const key = getKey()
  const iv = Uint8Array.from(atob(ivB64), c => c.charCodeAt(0))
  const data = Uint8Array.from(atob(ciphertext), c => c.charCodeAt(0))
  const decrypted = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv }, key, data
  )
  return new TextDecoder().decode(decrypted)
}

// --- Cached records (encrypted GET responses) ---

export async function cacheResponse(key: string, data: unknown): Promise<void> {
  const json = JSON.stringify(data)
  const { ciphertext, iv } = await encrypt(json)
  await db.cached_records.put({ key, data: ciphertext, iv, cachedAt: Date.now() })
}

export async function getCached<T = unknown>(key: string): Promise<T | null> {
  const record = await db.cached_records.get(key)
  if (!record) return null
  try {
    const json = await decrypt(record.data, record.iv)
    return JSON.parse(json) as T
  } catch {
    return null
  }
}

export async function clearCache(): Promise<void> {
  await db.cached_records.clear()
}

// --- Retry queue (encrypted pending writes) ---

export async function addToRetryQueue(request: {
  method: string
  url: string
  data?: unknown
  headers?: Record<string, string>
  idempotencyKey: string
}): Promise<string> {
  const queueId = crypto.randomUUID()
  const { ciphertext: dataEnc, iv: dataIv } = await encrypt(JSON.stringify(request.data ?? null))
  const { ciphertext: headersEnc, iv: headersIv } = await encrypt(JSON.stringify(request.headers ?? {}))
  await db.retry_queue.add({
    queueId,
    method: request.method,
    url: request.url,
    data: dataEnc,
    iv: dataIv,
    headers: headersEnc,
    headersIv,
    idempotencyKey: request.idempotencyKey,
    createdAt: Date.now(),
    retryCount: 0,
  })
  return queueId
}

export async function getRetryQueue(): Promise<Array<{
  id: number
  queueId: string
  method: string
  url: string
  data: unknown
  headers: Record<string, string>
  idempotencyKey: string
  createdAt: number
  retryCount: number
}>> {
  const records = await db.retry_queue.orderBy('createdAt').toArray()
  const results = []
  for (const r of records) {
    try {
      const dataJson = await decrypt(r.data, r.iv)
      const headersJson = await decrypt(r.headers, r.headersIv)
      results.push({
        id: r.id!,
        queueId: r.queueId,
        method: r.method,
        url: r.url,
        data: JSON.parse(dataJson),
        headers: JSON.parse(headersJson),
        idempotencyKey: r.idempotencyKey,
        createdAt: r.createdAt,
        retryCount: r.retryCount,
      })
    } catch {
      // Skip records that can't be decrypted (e.g., key changed)
    }
  }
  return results
}

export async function removeFromRetryQueue(id: number): Promise<void> {
  await db.retry_queue.delete(id)
}

export async function incrementRetryCount(id: number): Promise<void> {
  const current = await db.retry_queue.get(id)
  await db.retry_queue.update(id, { retryCount: (current?.retryCount ?? 0) + 1 })
}

export async function clearRetryQueue(): Promise<void> {
  await db.retry_queue.clear()
}

export async function getQueueLength(): Promise<number> {
  return db.retry_queue.count()
}

// --- Sync metadata ---

export async function setSyncMetadata(key: string, value: string): Promise<void> {
  await db.sync_metadata.put({ key, value, updatedAt: Date.now() })
}

export async function getSyncMetadata(key: string): Promise<string | null> {
  const record = await db.sync_metadata.get(key)
  return record?.value ?? null
}

// --- Blob store (file attachments for offline queue) ---

export async function storeBlobForQueue(queueId: string, fieldName: string, file: File): Promise<void> {
  await db.blob_store.add({
    queueId,
    fieldName,
    blob: file,
    filename: file.name,
    contentType: file.type,
  })
}

export async function getBlobsForQueue(queueId: string): Promise<BlobRecord[]> {
  return db.blob_store.where('queueId').equals(queueId).toArray()
}

export async function removeBlobsForQueue(queueId: string): Promise<void> {
  await db.blob_store.where('queueId').equals(queueId).delete()
}

export { db }
