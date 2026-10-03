<script setup>
import { onBeforeUnmount, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { readAll } from '@/api/pagination'
import { useAuthStore } from '@/stores/auth'
import AppIcon from './AppIcon.vue'
const auth = useAuthStore()
const open = ref(false), loading = ref(false), error = ref(''), activities = ref([])
let revision = 0
onBeforeUnmount(() => { revision++ })
async function toggle() {
  open.value = !open.value
  if (!open.value) return
  const current = ++revision
  loading.value = true; error.value = ''; activities.value = []
  try {
    const classes = (await readAll('/classes')).filter(row => row.active)
    if (!classes.length) return
    const teacher = auth.user?.role === 'teacher'
    const rows = teacher
      ? (await Promise.all(classes.map(row => readAll(`/assessments?class_id=${row.id}`)))).flat()
      : await readAll('/assessments')
    if (current !== revision) return
    activities.value = rows.filter(row => row.kind !== 'practice' && ['open', 'upcoming'].includes(row.effective_state))
      .map(row => ({
        id: row.id,
        title: row.title,
        className: classes.find(item => item.id === row.class_id)?.name,
        label: row.effective_state === 'open' ? '进行中' : '即将开始',
        to: { name: teacher ? 'teacher-assessment' : 'student-assessment', params: { id: row.id } },
      }))
  } catch (err) { if (current === revision) error.value = err.message }
  finally { if (current === revision) loading.value = false }
}
function leave(event) { if (!event.currentTarget.contains(event.relatedTarget)) open.value = false }
</script>
<template>
  <div class="classroom-updates" @focusout="leave" @keydown.esc="open = false">
    <button class="updates-button" type="button" aria-label="课堂动态" :aria-expanded="open" aria-controls="classroom-updates-panel" @click="toggle"><AppIcon name="bell" :size="20" /></button>
    <section v-if="open" id="classroom-updates-panel" class="updates-panel" aria-label="课堂动态列表">
      <h2>课堂动态</h2><p v-if="loading">正在读取本班活动…</p><p v-else-if="error" role="alert">{{ error }}</p>
      <ul v-else-if="activities.length"><li v-for="item in activities" :key="item.id"><RouterLink :to="item.to" @click="open = false"><div><strong>{{ item.title }}</strong><span v-if="item.className">{{ item.className }}</span></div><small>{{ item.label }}</small></RouterLink></li></ul>
      <p v-else>当前没有进行中或即将开始的班级测评。</p>
    </section>
  </div>
</template>
<style scoped>
.classroom-updates { position: relative; }
.updates-button { display: grid; place-items: center; width: 36px; height: 36px; border: 0; border-radius: 8px; background: transparent; color: #314773; }
.updates-button:hover { background: var(--color-primary-soft); }
.updates-panel { position: absolute; top: 46px; right: 0; width: min(320px, calc(100vw - 24px)); padding: 16px; border: 1px solid var(--color-border); border-radius: 12px; background: white; box-shadow: var(--shadow-popover); }
h2 { font-size: 14px; margin: 0 0 12px; } p { margin: 0; font-size: 12px; color: var(--color-text-secondary); }
ul { list-style: none; margin: 0; padding: 0; max-height: 280px; overflow-y: auto; } a { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; text-decoration: none; border-top: 1px solid var(--color-border); font-size: 12px; } a > div { min-width: 0; } a strong { overflow-wrap: anywhere; } a span { display: block; margin-top: 4px; font-size: 10px; color: var(--color-text-secondary); } small { white-space: nowrap; color: var(--color-primary); }
@media (max-width: 520px) { .updates-panel { position: fixed; top: 70px; left: 12px; right: 12px; width: auto; } }
</style>
