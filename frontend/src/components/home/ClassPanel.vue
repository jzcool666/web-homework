<script setup>
/**
 * 首页的班级面板：只读 /classes 的真实结果，按角色给出不同的空态文案。
 * 未登录时（guest）不请求接口，只提示登录。
 */
import { computed, onMounted, ref } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { api } from '@/api/client'

const props = defineProps({
  guest: { type: Boolean, default: false },
  role: { type: String, default: 'student' },
  title: { type: String, default: '当前课堂' },
})

const classes = ref([])
const state = ref('idle')
const error = ref('')

const isStudent = computed(() => props.role === 'student')

async function load() {
  state.value = 'loading'
  try {
    classes.value = await api.get('/classes?page_size=100')
    state.value = 'ready'
  } catch (err) {
    error.value = err.message
    state.value = 'error'
  }
}

onMounted(() => {
  if (!props.guest) load()
})
</script>

<template>
  <SectionCard :title="title">
    <StatePanel v-if="guest" title="登录后查看班级" description="学生与教师使用同一登录入口；公开注册只创建学生账号。" />
    <StatePanel v-else-if="state === 'loading'" kind="loading" title="正在读取班级信息" />
    <StatePanel v-else-if="state === 'error'" kind="error" title="班级信息暂时无法读取" :description="error" />
    <StatePanel
      v-else-if="classes.length === 0"
      :title="isStudent ? '你当前尚未加入班级' : '当前没有任教班级'"
      description="请联系管理员分配班级。分配完成后，这里会显示你的课堂入口。"
    />
    <div v-else class="class-list">
      <div v-for="schoolClass in classes" :key="schoolClass.id" class="class-row">
        <span class="class-row__icon"><AppIcon name="book" /></span>
        <div><strong>{{ schoolClass.name }}</strong><small>课程学习、课堂演示、习题训练、实验与考勤已开放</small></div>
        <StatusBadge :tone="schoolClass.active ? 'neutral' : 'warning'">{{ schoolClass.active ? '已分配' : '班级已停用' }}</StatusBadge>
      </div>
    </div>
  </SectionCard>
</template>

<style scoped>
.class-list { display: grid; gap: var(--space-3); }
.class-row { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); }
.class-row__icon { display: grid; place-items: center; width: 2.7rem; height: 2.7rem; border-radius: var(--radius-sm); color: var(--color-primary); background: var(--color-primary-soft); }
.class-row div { display: grid; }
.class-row small { color: var(--color-text-secondary); }
.class-row .status-badge { margin-left: auto; }
</style>
