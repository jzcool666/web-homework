<script setup>
/**
 * 学生首页的预习待办（SPEC-008 E027）。
 *
 * 只读本班预习：先取本人有效班级，再按 class_id 拉预习列表；跨班由后端返回 404。
 * 标题与条目摘要均取自发布时冻结的快照。
 */
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { dueState, previewItemLabel } from '@/utils/lesson'

const previews = ref([])
const classId = ref(null)
const state = ref('loading')
const error = ref('')

const overdueCount = computed(
  () => previews.value.filter((preview) => dueState(preview.due_at).overdue).length,
)

async function load() {
  state.value = 'loading'
  error.value = ''
  try {
    const classes = await api.get('/classes?page_size=100')
    if (classes.length === 0) {
      state.value = 'no-class'
      return
    }
    classId.value = classes[0].id
    previews.value = await api.get(
      `/preview-assignments?class_id=${classId.value}&page_size=20`,
    )
    state.value = 'ready'
  } catch (err) {
    error.value = err.message
    state.value = 'error'
  }
}

onMounted(load)
</script>

<template>
  <SectionCard title="预习待办">
    <StatePanel v-if="state === 'loading'" kind="loading" title="正在读取预习任务" />
    <StatePanel v-else-if="state === 'error'" kind="error" title="预习任务暂时无法读取" :description="error" />
    <StatePanel
      v-else-if="state === 'no-class'"
      title="尚未加入班级"
      description="加入班级后，教师发布的预习会显示在这里。"
    />
    <StatePanel
      v-else-if="previews.length === 0"
      title="暂无预习任务"
      description="教师发布预习后，待办会出现在这里。"
    />
    <ul v-else class="previews">
      <li v-for="preview in previews" :key="preview.id">
        <div class="previews__head">
          <strong>{{ preview.plan_title || `预习 #${preview.id}` }} · {{ preview.items.length }} 项</strong>
          <StatusBadge :tone="dueState(preview.due_at).tone">
            {{ dueState(preview.due_at).text }}
          </StatusBadge>
        </div>
        <p class="previews__items">
          <span v-for="item in preview.items" :key="item.sort_order">
            {{ previewItemLabel(item) }}
          </span>
        </p>
      </li>
    </ul>
    <p v-if="state === 'ready' && overdueCount > 0" class="hint">
      有 {{ overdueCount }} 项已过截止时间，仍可查看内容。
    </p>
  </SectionCard>
</template>

<style scoped>
.previews {
  margin: 0;
  padding: 0;
  list-style: none;
}

.previews li {
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--color-border);
}

.previews li:last-child {
  border-bottom: 0;
}

.previews__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-2);
}

.previews__items {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}
</style>
