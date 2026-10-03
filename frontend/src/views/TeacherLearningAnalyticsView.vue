<script setup>
import { initialClassId } from '@/utils/overview'
/**
 * 教师学情分析：学习进度与资源访问统计（SPEC-006 E056）。
 *
 * 两个面板各自标注口径：进度是「当前快照近似」，资源访问是「UTC 自然日去重」，
 * 时间窗只过滤资源事件。学生不能访问班级统计，因此这个页面只在教师导航里接通。
 * 导出与页面使用同一查询串，保证 CSV 与屏幕上的 JSON 是同一筛选、同一结果。
 */
import { computed, onMounted, ref } from 'vue'

import { API_BASE, api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import {
  PROGRESS_BASIS_NOTE,
  RESOURCE_WINDOW_NOTE,
  STATS_TIMEZONE_NOTE,
  analyticsQuery,
  defaultUtcWindow,
  rateText,
} from '@/utils/analytics'

const classes = ref([])
const chapters = ref([])
const classId = ref('')
const chapterId = ref('')
const window = ref(defaultUtcWindow())
const stats = ref(null)
const loading = ref(false)
const listError = ref(null)

const query = computed(() =>
  analyticsQuery({
    classId: classId.value,
    from: window.value.from,
    to: window.value.to,
    chapterId: chapterId.value,
  }),
)
const csvHref = computed(() => `${API_BASE}/analytics/learning?${query.value}&format=csv`)
const students = computed(() => stats.value?.students ?? [])
const resources = computed(() => stats.value?.resources ?? [])
const hasPublished = computed(() => (stats.value?.published_knowledge_count ?? 0) > 0)

function rateTone(rate) {
  if (rate === null || rate === undefined) return 'neutral'
  if (rate >= 0.8) return 'success'
  if (rate >= 0.5) return 'warning'
  return 'danger'
}

async function loadOptions() {
  const [classList, chapterList] = await Promise.all([
    api.get('/classes?page_size=100'),
    api.get('/chapters?page_size=100'),
  ])
  classes.value = classList
  chapters.value = chapterList
  if (!classId.value) classId.value = initialClassId(classList)
}

async function loadStats() {
  if (!classId.value) {
    stats.value = null
    return
  }
  loading.value = true
  listError.value = null
  try {
    stats.value = await api.get(`/analytics/learning?${query.value}`)
  } catch (err) {
    listError.value = err.message
    stats.value = null
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    await loadOptions()
    await loadStats()
  } catch (err) {
    listError.value = err.message
  }
})
</script>

<template>
  <div class="page">
    <PageHeader icon="chart"
      eyebrow="学情"
      title="学情分析"
      description="按班级查看学习进度快照与资源访问分布。两个面板的口径不同，页面分别标注，导出 CSV 与屏幕上的筛选条件一致。"
    />

    <SectionCard title="筛选">
      <div class="filters">
        <div class="field">
          <label for="a_class">班级</label>
          <select id="a_class" v-model="classId" @change="loadStats">
            <option value="" disabled>请选择班级</option>
            <option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </div>
        <div class="field">
          <label for="a_from">窗口起（UTC 日）</label>
          <input id="a_from" v-model="window.from" type="date" @change="loadStats" />
        </div>
        <div class="field">
          <label for="a_to">窗口止（UTC 日，不含）</label>
          <input id="a_to" v-model="window.to" type="date" @change="loadStats" />
        </div>
        <div class="field">
          <label for="a_chapter">章节</label>
          <select id="a_chapter" v-model="chapterId" @change="loadStats">
            <option value="">全部章节</option>
            <option v-for="item in chapters" :key="item.id" :value="item.id">{{ item.title }}</option>
          </select>
        </div>
        <button class="button button--secondary" type="button" @click="loadStats">刷新</button>
        <a class="button button--secondary" :href="csvHref">导出 CSV</a>
      </div>
      <p class="hint">{{ STATS_TIMEZONE_NOTE }}</p>
      <p v-if="stats" class="hint">
        当前窗口 {{ stats.window.from }} → {{ stats.window.to }}
      </p>
      <p v-if="classes.length === 0" class="hint">还没有任教的班级，请联系管理员分配。</p>
    </SectionCard>

    <p v-if="listError" class="error" role="alert">{{ listError }}</p>
    <StatePanel v-if="loading" kind="loading" title="正在统计" />

    <template v-else-if="stats">
      <SectionCard title="学习进度快照">
        <p class="basis">{{ PROGRESS_BASIS_NOTE }}</p>
        <div class="summary">
          <span>已发布知识点（分母）：<strong>{{ stats.published_knowledge_count }}</strong></span>
          <StatusBadge tone="neutral">{{ stats.progress_basis }}</StatusBadge>
        </div>

        <StatePanel
          v-if="students.length === 0"
          title="该班当前没有在册学生"
          description="学生加入班级并开始标记完成后，这里会显示每个人的完成情况。"
        />
        <template v-else>
          <StatePanel
            v-if="!hasPublished"
            title="当前没有已发布知识点"
            description="分母为 0，完成率显示为「无已发布知识点」而不是 0%。"
          />
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>学生</th>
                  <th>已完成知识点</th>
                  <th>完成率</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in students" :key="row.student_id">
                  <td>#{{ row.student_id }}</td>
                  <td>{{ row.completed_count }}</td>
                  <td>
                    <StatusBadge :tone="rateTone(row.completion_rate)">
                      {{ rateText(row.completion_rate) }}
                    </StatusBadge>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="hint">进度名单只含当前有效在册学生；已退班学生的历史活动仍计入下方资源统计。</p>
        </template>
      </SectionCard>

      <SectionCard title="资源访问时间窗">
        <p class="basis">{{ RESOURCE_WINDOW_NOTE }}</p>
        <StatePanel
          v-if="resources.length === 0"
          title="该时间窗内没有资源访问记录"
          description="调整窗口或章节后重试；学生打开或下载资料后会产生去重事件。"
        />
        <div v-else class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>资料</th>
                <th>去重人数</th>
                <th>去重事件</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in resources" :key="row.resource_id">
                <td>#{{ row.resource_id }}</td>
                <td>{{ row.unique_students }}</td>
                <td>{{ row.dedup_events }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 0 var(--space-4);
  align-items: end;
  margin-bottom: var(--space-3);
}

.filters button,
.filters a {
  justify-self: start;
}

.basis {
  margin: 0 0 var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-left: 3px solid var(--color-primary);
  background: var(--color-grid-surface);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.summary {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}
</style>
