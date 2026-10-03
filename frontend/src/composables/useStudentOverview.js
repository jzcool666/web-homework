import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { readAll } from '@/api/pagination'
import { completion, continuePoint, recommendedPoints } from '@/utils/overview'

export function useStudentOverview() {
  const loading = ref(true)
  const data = ref({})
  const errors = ref({})
  let revision = 0
  async function load() {
    const current = ++revision
    loading.value = true
    const requests = {
      points: () => readAll('/knowledge-points'),
      chapters: () => readAll('/chapters'),
      progress: () => readAll('/me/learning-progress'),
      experiments: () => readAll('/experiments'),
      attempts: () => readAll('/me/experiment-attempts'),
      recommendations: () => api.get('/me/recommendations?limit=10'),
      assessments: () => readAll('/assessments'),
      classes: () => readAll('/classes'),
    }
    const results = await Promise.allSettled(
      Object.values(requests).map((get) => get()),
    )
    if (current !== revision) return
    const next = {},
      failures = {}
    Object.keys(requests).forEach((key, index) => {
      const result = results[index]
      if (result.status === 'fulfilled')
        next[key] =
          key === 'recommendations' ? result.value.items : result.value
      else failures[key] = result.reason.message
    })
    data.value = next
    errors.value = failures
    loading.value = false
  }
  const stats = computed(() =>
    completion(
      data.value.points ?? [],
      data.value.progress ?? [],
      data.value.experiments ?? [],
      data.value.attempts ?? [],
    ),
  )
  const learningReady = computed(
    () => data.value.points !== undefined && data.value.progress !== undefined,
  )
  const experimentReady = computed(
    () =>
      data.value.experiments !== undefined && data.value.attempts !== undefined,
  )
  const target = computed(() =>
    continuePoint(
      data.value.points ?? [],
      data.value.progress ?? [],
      data.value.recommendations ?? [],
      data.value.chapters ?? [],
    ),
  )
  const recommended = computed(() =>
    recommendedPoints(data.value.recommendations ?? []),
  )
  onMounted(load)
  return {
    data,
    errors,
    loading,
    stats,
    learningReady,
    experimentReady,
    target,
    recommended,
    load,
  }
}
