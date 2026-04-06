<template>
  <div id="app">
    <AppNavbar v-if="auth.isAuthenticated" />
    <div class="app-body" v-if="auth.isAuthenticated">
      <AppSidebar />
      <main class="main-content">
        <router-view />
      </main>
    </div>
    <router-view v-else />
    <ConflictResolver
      v-if="activeConflict"
      :conflict="activeConflict.conflict"
      :queue-item-id="activeConflict.queueItemId"
      :request-url="activeConflict.request.url"
      :request-method="activeConflict.request.method"
      @resolved="sync.resolveConflict()"
      @discarded="sync.resolveConflict()"
    />
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useSyncManager } from '@/services/syncManager'
import AppNavbar from '@/components/layout/AppNavbar.vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import ConflictResolver from '@/components/ConflictResolver.vue'

const auth = useAuthStore()
auth.loadFromStorage()

const sync = useSyncManager()
const { activeConflict } = sync
</script>

<style>
@import '@/assets/main.css';
.app-body { display: flex; min-height: calc(100vh - 56px); }
.main-content { flex: 1; padding: 0; overflow-y: auto; }
</style>