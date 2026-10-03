import { ref } from 'vue'
import { defineStore } from 'pinia'

export const HEALTH_PATH = '/api/v1/health'

/**
 * E000 健康状态。骨架阶段只用于验证前后端连通与部署同源，
 * 不承载任何业务状态。
 */
export const useHealthStore = defineStore('health', () => {
  const status = ref('unknown') // unknown | ok | unavailable
  const version = ref(null)
  const reason = ref(null)
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      const response = await fetch(HEALTH_PATH)
      const body = await response.json()
      if (response.ok) {
        status.value = 'ok'
        version.value = body?.data?.version ?? null
        reason.value = null
      } else {
        status.value = 'unavailable'
        version.value = null
        reason.value =
          body?.error?.details?.reason ?? body?.error?.message ?? '服务暂时不可用'
      }
    } catch {
      status.value = 'unavailable'
      version.value = null
      reason.value = '无法连接到后端服务'
    } finally {
      loading.value = false
    }
  }

  return { status, version, reason, loading, load }
})
