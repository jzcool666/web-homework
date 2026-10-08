<script setup>
import { initialClassId } from '@/utils/overview'
/**
 * 教师学习预警（SPEC-004 E063/E064）。
 *
 * 只统计本人任教班级；跨班由后端按 404 拒绝。快照必须由教师显式生成，
 * 页面读取的是最近同窗口的完整批次，没有批次时显示空状态而不是假造数据。
 * 等级与分组各自标注口径：等级是项目规则分数档，分组只是班级内的相似性描述。
 */
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { dayStamp, defaultUtcWindow } from '@/utils/analytics'
import {
  CLUSTER_NOTE,
  FACTOR_LABELS,
  WARNING_NOTE,
  availableFactorsText,
  clusterText,
  factorText,
  levelText,
  levelTone,
  scoreText,
} from '@/utils/warnings'

const classes = ref([])
const classId = ref('')
const window = ref(defaultUtcWindow())
const warnings = ref([])
const batch = ref(null)
const loading = ref(false)
const generating = ref(false)
const listError = ref(null)

const factors = computed(() => Object.keys(FACTOR_LABELS))

const query = computed(() => {
  const params = new URLSearchParams({ class_id: String(classId.value) })
  if (window.value.from && window.value.to) {
    params.set('from', dayStamp(window.value.from))
    params.set('to', dayStamp(window.value.to))
  }
  return params.toString()
})

const hasUnclustered = computed(() => warnings.value.some((row) => row.cluster_label === null))

async function loadClasses() {
  classes.value = await api.get('/classes?page_size=100')
  if (!classId.value) classId.value = initialClassId(classes.value)
}

async function loadWarnings() {
  if (!classId.value) {
    warnings.value = []
    batch.value = null
    return
  }
  loading.value = true
  listError.value = null
  try {
    warnings.value = await api.get(`/warnings?${query.value}&page_size=100`)
    batch.value = warnings.value[0] ? { generated_at: warnings.value[0].generated_at } : null
  } catch (err) {
    listError.value = err.message
    warnings.value = []
    batch.value = null
  } finally {
    loading.value = false
  }
}

async function generateSnapshot() {
  if (!classId.value) return
  generating.value = true
  listError.value = null
  try {
    const payload = { class_id: Number(classId.value) }
    if (window.value.from && window.value.to) {
      payload.from = dayStamp(window.value.from)
      payload.to = dayStamp(window.value.to)
    }
    const result = await api.post('/warnings/generations', payload)
    warnings.value = result.students
    batch.value = {
      generated_at: result.generated_at,
      cluster_reason: result.cluster_reason,
      disclaimer: result.disclaimer,
    }
  } catch (err) {
    listError.value = err.message
  } finally {
    generating.value = false
  }
}

onMounted(async () => {
  try {
    await loadClasses()
    await loadWarnings()
  } catch (err) {
    listError.value = err.message
  }
})
</script>

<template>
  <div class="page">
    <PageHeader icon="chart" :steps="['选择班级与日期', '生成快照', '查看原因与建议']"
      eyebrow="学情"
      title="学习预警"
      description="按班级显式生成一次快照，查看每名学生的风险因素、证据与班级分组。快照不随数据自动更新。"
    />

    <SectionCard title="筛选与生成">
      <div class="filter-bar">
        <div class="field">
          <label for="w_class">班级</label>
          <select id="w_class" v-model="classId" @change="loadWarnings">
            <option value="" disabled>请选择班级</option>
            <option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </div>
        <div class="field">
          <label for="w_from">窗口起（UTC）</label>
          <input id="w_from" v-model="window.from" type="date" @change="loadWarnings" />
        </div>
        <div class="field">
          <label for="w_to">窗口止（UTC，不含）</label>
          <input id="w_to" v-model="window.to" type="date" @change="loadWarnings" />
        </div>
        <div class="filter-actions">
        <button class="button button--primary" type="button" :disabled="!classId || generating" @click="generateSnapshot">
          {{ generating ? '生成中…' : '生成快照' }}
        </button>
        <button class="button button--secondary" type="button" @click="loadWarnings">刷新</button>
        </div>
      </div>
      <p class="hint">{{ WARNING_NOTE }}</p>
      <p v-if="batch" class="hint">
        批次生成于 {{ batch.generated_at }}；当前读取的是该窗口最近一个完整批次。
      </p>
      <p v-if="classes.length === 0" class="hint">还没有任教的班级，请联系管理员分配。</p>
    </SectionCard>

    <p v-if="listError" class="error" role="alert">{{ listError }}</p>
    <StatePanel v-if="loading" kind="loading" title="正在读取预警批次" />

    <template v-else>
      <SectionCard title="预警名单">
        <StatePanel
          v-if="warnings.length === 0"
          title="该窗口还没有预警批次"
          description="点击「生成快照」按当前数据生成一批；之后再生成会保留为新批次。"
        />
        <div v-else class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>学生</th>
                <th>等级</th>
                <th>分数</th>
                <th v-for="name in factors" :key="name">{{ FACTOR_LABELS[name] }}风险</th>
                <th>可用因素</th>
                <th>分组</th>
                <th>证据</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in warnings" :key="row.student_id">
                <td>#{{ row.student_id }}</td>
                <td>
                  <StatusBadge :tone="levelTone(row.level)">{{ levelText(row.level) }}</StatusBadge>
                </td>
                <td>{{ scoreText(row.score) }}</td>
                <td v-for="name in factors" :key="name">{{ factorText(row.factors[name]) }}</td>
                <td>{{ availableFactorsText(row.available_factors) }}</td>
                <td>{{ clusterText(row.cluster_label) }}</td>
                <td>
                  <ul class="reasons">
                    <li v-for="reason in row.reasons" :key="reason">{{ reason }}</li>
                  </ul>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>

      <SectionCard v-if="warnings.length > 0" title="班级分组">
        <p class="basis">{{ CLUSTER_NOTE }}</p>
        <p v-if="batch && batch.cluster_reason" class="hint">{{ batch.cluster_reason }}</p>
        <p v-else-if="hasUnclustered" class="hint">
          本批中仍有三因素不齐全的学生，未参与分组。
        </p>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>


.basis {
  margin: 0 0 var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-left: 3px solid var(--color-primary);
  background: var(--color-grid-surface);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.reasons {
  margin: 0;
  padding-left: 1.1rem;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
</style>
