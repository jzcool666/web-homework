<script setup>
/**
 * 学生「我的课堂」（SPEC-012 E052/E053）。
 *
 * 只列出本班演示：进行中的一个置顶并可进入只读观看，历史演示可回看。
 * 学生未入班时说明缺少什么，不显示空的课堂数据。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import AppIcon from '@/components/ui/AppIcon.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { api } from '@/api/client'
import { modelLabel, risingCount } from '@/utils/demo'

const classes = ref([])
const demos = ref([])
const state = ref('loading')
const loadError = ref('')

const currentClass = computed(() => classes.value[0] ?? null)
const activeDemo = computed(() => demos.value.find((demo) => demo.active) ?? null)
const pastDemos = computed(() => demos.value.filter((demo) => !demo.active))

async function load() {
  state.value = 'loading'
  try {
    classes.value = await api.get('/classes?page_size=100')
    demos.value = currentClass.value
      ? await api.get(`/demo-sessions?class_id=${currentClass.value.id}&page_size=100`)
      : []
    state.value = 'ready'
  } catch (err) {
    loadError.value = err.message
    state.value = 'error'
  }
}

onMounted(load)
</script>

<template>
  <div class="demos-page">
    <PageHeader
      eyebrow="学习空间"
      title="我的课堂"
      description="跟随教师投屏的演示：只看当前状态与已执行的时序波形，预测未揭示时不会提前显示下一状态。"
    />

    <StatePanel v-if="state === 'loading'" kind="loading" title="正在读取本班演示" />
    <StatePanel v-else-if="state === 'error'" kind="error" title="演示列表无法读取" :description="loadError" />
    <StatePanel
      v-else-if="!currentClass"
      title="你当前尚未加入班级"
      description="请联系管理员分配班级。分配完成后，这里会显示本班的课堂演示。"
    />

    <template v-else>
      <SectionCard :title="`${currentClass.name} · 进行中的演示`">
        <div v-if="activeDemo" class="demo-row demo-row--active">
          <span class="demo-row__icon"><AppIcon name="clock" /></span>
          <div class="demo-row__body">
            <strong>{{ activeDemo.experiment?.title }}</strong>
            <small>
              {{ modelLabel(activeDemo.experiment?.simulator_type) }} ·
              已执行 {{ risingCount(activeDemo.history) }} 个有效上升沿 ·
              版本 {{ activeDemo.version }}
            </small>
          </div>
          <StatusBadge tone="success">进行中</StatusBadge>
          <RouterLink class="button button--primary" :to="{ name: 'student-demo', params: { id: activeDemo.id } }">
            进入观看
          </RouterLink>
        </div>
        <div v-else class="empty">
          本班当前没有进行中的演示。教师开始演示后，这里会自动出现入口。
        </div>
      </SectionCard>

      <SectionCard title="已结束的演示">
        <div v-if="pastDemos.length === 0" class="empty">还没有已结束的演示记录。</div>
        <div v-else class="demo-list">
          <div v-for="demo in pastDemos" :key="demo.id" class="demo-row">
            <span class="demo-row__icon"><AppIcon name="clock" /></span>
            <div class="demo-row__body">
              <strong>{{ demo.experiment?.title }}</strong>
              <small>
                {{ modelLabel(demo.experiment?.simulator_type) }} ·
                已执行 {{ risingCount(demo.history) }} 个有效上升沿 · {{ demo.last_updated }}
              </small>
            </div>
            <StatusBadge>已结束</StatusBadge>
            <RouterLink class="button button--secondary" :to="{ name: 'student-demo', params: { id: demo.id } }">
              回看
            </RouterLink>
          </div>
        </div>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.demos-page { width: 100%; }
.demos-page .section-card { margin-bottom: var(--space-4); }
.demo-list { display: grid; gap: var(--space-3); }
.demo-row { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); }
.demo-row--active { border-color: var(--color-primary); background: var(--color-primary-soft); }
.demo-row__icon { display: grid; place-items: center; width: 2.6rem; height: 2.6rem; border-radius: var(--radius-sm); color: var(--color-primary); background: #fff; }
.demo-row__body { display: grid; gap: 2px; margin-right: auto; }
.demo-row__body small { color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.empty { color: var(--color-text-secondary); }
</style>
