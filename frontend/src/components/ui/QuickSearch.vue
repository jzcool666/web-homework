<script setup>
import { computed, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { navigationFor } from '@/navigation'
import { readAll } from '@/api/pagination'
import AppIcon from './AppIcon.vue'
const auth = useAuthStore(),
  router = useRouter()
const query = ref(''),
  open = ref(false),
  points = ref([]),
  experiments = ref([]),
  state = ref('idle')
const results = computed(() => {
  const term = query.value.trim().toLocaleLowerCase()
  if (!term) return []
  const entries = navigationFor(auth.user?.role)
    .filter((row) => row.route)
    .map((row) => ({
      title: row.label,
      type: '页面',
      to: { name: row.route },
    }))
  if (auth.user?.role === 'student') {
    entries.push(
      ...points.value.map((row) => ({
        title: row.title,
        type: '知识点',
        to: { name: 'student-knowledge', params: { id: row.id } },
      })),
      ...experiments.value.map((row) => ({
        title: row.title,
        type: '实验',
        to: { name: 'student-experiment', params: { id: row.id } },
      })),
    )
  }
  return entries
    .filter((row) => row.title.toLocaleLowerCase().includes(term))
    .slice(0, 6)
})
async function activate() {
  open.value = true
  if (auth.user?.role !== 'student' || state.value !== 'idle') return
  state.value = 'loading'
  try {
    ;[points.value, experiments.value] = await Promise.all([
      readAll('/knowledge-points'),
      readAll('/experiments'),
    ])
    state.value = 'ready'
  } catch {
    state.value = 'error'
  }
}
function leave(event) {
  if (!event.currentTarget.contains(event.relatedTarget)) open.value = false
}
function go() {
  if (results.value.length) {
    router.push(results.value[0].to)
    open.value = false
  }
}
</script>
<template>
  <form
    class="quick-search"
    role="search"
    @submit.prevent="go"
    @focusout="leave"
    @keydown.esc="open = false"
  >
    <AppIcon name="search" :size="15" />
    <input
      v-model="query"
      aria-label="搜索页面、知识点或实验"
      placeholder="搜索课程、习题、实验…"
      autocomplete="off"
      @focus="activate"
      @input="open = true"
    />
    <div v-if="open && query.trim()" class="quick-search__results">
      <RouterLink
        v-for="row in results"
        :key="`${row.type}-${row.title}`"
        :to="row.to"
        @click="open = false"
        ><span>{{ row.title }}</span
        ><small>{{ row.type }}</small></RouterLink
      >
      <p v-if="!results.length">
        {{
          state === 'loading'
            ? '正在读取课程…'
            : '没有匹配结果，试试其他关键词。'
        }}
      </p>
      <p v-if="state === 'error'" role="alert">
        课程暂时无法搜索，仍可搜索页面入口。
      </p>
    </div>
  </form>
</template>
<style scoped>
.quick-search {
  position: relative;
  width: clamp(180px, 23vw, 310px);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  background: #f5f8fd;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text-secondary);
}
input {
  min-width: 0;
  width: 100%;
  border: 0;
  background: transparent;
  font-size: 12px;
  color: var(--color-text-primary);
  outline-offset: 5px;
}
.quick-search__results {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 8px);
  padding: 6px;
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 9px;
  box-shadow: var(--shadow-popover);
}
.quick-search__results a {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 9px;
  border-radius: 6px;
  text-decoration: none;
  font-size: 12px;
}
.quick-search__results a:hover {
  background: var(--color-primary-soft);
}
small {
  white-space: nowrap;
  color: var(--color-text-secondary);
  font-size: 10px;
}
p {
  font-size: 11px;
  padding: 8px;
  margin: 0;
}
@media (max-width: 1000px) {
  .quick-search {
    width: 200px;
  }
}
@media (max-width: 700px) {
  .quick-search {
    display: none;
  }
}
</style>
