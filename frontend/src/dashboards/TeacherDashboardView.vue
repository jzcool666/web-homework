<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '@/api/client'
import { readAll } from '@/api/pagination'
import { percent, recentAssessment } from '@/utils/overview'
import { useAuthStore } from '@/stores/auth'
import ConceptHero from '@/components/home/ConceptHero.vue'
import MetricCard from '@/components/ui/MetricCard.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
const auth = useAuthStore()
const classes = ref([]),
  classId = ref(''),
  data = ref({}),
  errors = ref({}),
  loading = ref(true),
  classError = ref('')
let revision = 0
const activeDemo = computed(() => data.value.demos?.find((row) => row.active))
const openAssessment = computed(() =>
  data.value.assessments?.find(
    (row) => row.kind !== 'practice' && row.effective_state === 'open',
  ),
)
const latest = computed(() => recentAssessment(data.value.assessments ?? []))
const latestStats = computed(() =>
  data.value.analytics?.assessments?.find((row) => row.id === latest.value?.id),
)
const quickActions = [
  { title: '课堂演示', route: 'teacher-classroom' },
  { title: '创建测评', route: 'teacher-assessments' },
  { title: '发起签到', route: 'teacher-attendance' },
  { title: '新建备课', route: 'teacher-lesson-plans' },
  { title: '查看学情', route: 'teacher-learning-analytics' },
  { title: '智能组卷', route: 'teacher-paper-generation' },
]
async function loadClass() {
  const current = ++revision
  data.value = {}
  errors.value = {}
  loading.value = true
  if (!classId.value) {
    loading.value = false
    return
  }
  const id = Number(classId.value)
  const requests = {
    demos: () => readAll(`/demo-sessions?class_id=${id}`),
    assessments: () => readAll(`/assessments?class_id=${id}`),
    enrollments: () => readAll(`/classes/${id}/enrollments`),
    warnings: () => readAll(`/warnings?class_id=${id}`),
  }
  const results = await Promise.allSettled(
    Object.values(requests).map((get) => get()),
  )
  if (current !== revision) return
  const next = {},
    failures = {}
  Object.keys(requests).forEach((key, index) => {
    const result = results[index]
    if (result.status === 'fulfilled') next[key] = result.value
    else failures[key] = result.reason.message
  })
  const assessment = recentAssessment(next.assessments ?? [])
  if (assessment) {
    try {
      next.analytics = await api.get(
        `/analytics/assessment?class_id=${id}&assessment_id=${assessment.id}`,
      )
    } catch (err) {
      failures.analytics = err.message
    }
  }
  if (current !== revision) return
  data.value = next
  errors.value = failures
  loading.value = false
}
onMounted(async () => {
  try {
    classes.value = (await readAll('/classes')).filter((row) => row.active)
    classId.value = classes.value[0]?.id ?? ''
    await loadClass()
  } catch (err) {
    classError.value = err.message
    loading.value = false
  }
})
</script>
<template>
  <div class="dashboard dashboard--teacher">
    <PageHeader
      eyebrow="教学空间"
      :title="`你好，${auth.user?.display_name ?? ''}`"
      description="围绕当前班级组织演示、测评与讲评。"
      ><template #actions
        ><div class="class-selector">
          <label for="dashboard-class">当前班级</label
          ><select id="dashboard-class" v-model="classId" @change="loadClass">
            <option value="">请选择班级</option>
            <option v-for="item in classes" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select>
        </div></template
      ></PageHeader
    >
    <ConceptHero
      title="让每一次状态变化，都有清楚的讲解。"
      cta-label="进入课堂"
      :cta-to="{ name: 'teacher-classroom', query: { class_id: classId } }"
    />
    <StatePanel
      v-if="classError"
      kind="error"
      title="班级读取失败"
      :description="classError"
    />
    <StatePanel v-else-if="loading" kind="loading" title="正在读取所选班级" />
    <StatePanel
      v-else-if="!classId"
      title="尚未选择任教班级"
      description="请先选择班级；暂无任教班级时联系管理员分配。"
    />
    <div v-else class="dashboard-primary">
      <SectionCard title="当前课堂"
        ><p
          v-if="errors.demos || errors.assessments"
          class="error"
          role="alert"
        >
          {{ errors.demos || errors.assessments }}
        </p>
        <template v-else
          ><h3>
            {{
              activeDemo?.experiment?.title ??
              openAssessment?.title ??
              '暂无进行中的课堂活动'
            }}
          </h3>
          <p class="hint">
            {{ classes.find((row) => row.id === Number(classId))?.name
            }}<template v-if="activeDemo">
              · 已执行 {{ activeDemo.state?.step_no ?? 0 }} 拍</template
            >
          </p>
          <div class="overview-actions">
            <RouterLink
              class="button button--primary"
              :to="
                activeDemo
                  ? { name: 'teacher-demo', params: { id: activeDemo.id } }
                  : { name: 'teacher-classroom', query: { class_id: classId } }
              "
              >{{ activeDemo ? '继续演示' : '进入课堂' }}</RouterLink
            ><RouterLink
              v-if="openAssessment"
              class="button button--secondary"
              :to="{
                name: 'teacher-assessment',
                params: { id: openAssessment.id },
              }"
              >查看进行中的测评</RouterLink
            >
          </div></template
        ></SectionCard
      ><SectionCard title="快捷操作"
        ><div class="quick-grid">
          <RouterLink
            v-for="item in quickActions"
            :key="item.route"
            :to="{ name: item.route, query: { class_id: classId } }"
            >{{ item.title }} <span aria-hidden="true">↗</span></RouterLink
          >
        </div></SectionCard
      >
    </div>
    <div v-if="!loading && classId" class="metric-grid">
      <MetricCard
        label="有效入班关系"
        :value="
          data.enrollments
            ? data.enrollments.filter((row) => row.active).length
            : null
        "
        note="所选班级 · 入班关系有效"
        icon="people"
      /><MetricCard
        label="最近测评提交"
        :value="
          latestStats
            ? `${latestStats.submitted_count} / ${latestStats.roster_count}`
            : null
        "
        :note="latest?.title ?? '尚无班级测评'"
        icon="check"
      /><MetricCard
        label="最近测评平均分"
        :value="
          latestStats?.mean_percent === null ||
          latestStats?.mean_percent === undefined
            ? null
            : `${latestStats.mean_percent} / 100`
        "
        note="百分制 · 已提交作答"
      />
    </div>
    <div v-if="!loading && classId" class="dashboard-secondary">
      <SectionCard title="知识点首答正确率"
        ><p
          v-if="errors.analytics || errors.assessments"
          class="error"
          role="alert"
        >
          {{ errors.analytics || errors.assessments }}
        </p>
        <p v-else-if="!data.analytics?.knowledge?.length" class="hint">
          暂无足够的首答统计数据。
        </p>
        <template v-else
          ><p class="hint">
            最近测评关联知识点 · {{ data.analytics.window.from }} 至
            {{ data.analytics.window.to }}（UTC）
          </p>
          <div
            v-for="row in data.analytics.knowledge"
            :key="row.knowledge_id"
            class="ratio-row"
          >
            <span>知识点 #{{ row.knowledge_id }}</span
            ><progress
              v-if="row.first_accuracy !== null"
              :value="row.first_accuracy"
              max="1"
              :aria-label="`知识点 ${row.knowledge_id} 首答正确率`"
            /><span>{{ percent(row.first_accuracy) }}</span>
          </div></template
        ></SectionCard
      ><SectionCard title="待关注事项"
        ><p v-if="errors.warnings" class="error" role="alert">
          {{ errors.warnings }}
        </p>
        <template v-else
          ><p>
            {{
              data.warnings?.length
                ? `最近预警批次有 ${data.warnings.filter((row) => ['medium', 'high'].includes(row.level)).length} 人需关注`
                : '尚未生成预警快照'
            }}
          </p>
          <p v-if="data.warnings?.length" class="hint">
            生成于 {{ data.warnings[0].generated_at }}，不是实时诊断。
          </p></template
        >
        <div class="overview-actions">
          <RouterLink
            class="button button--secondary"
            :to="{ name: 'teacher-warnings', query: { class_id: classId } }"
            >查看预警</RouterLink
          ><RouterLink
            class="button button--secondary"
            :to="{ name: 'teacher-assessments', query: { class_id: classId } }"
            >测评与讲评</RouterLink
          >
        </div></SectionCard
      >
    </div>
    <p v-if="errors.enrollments" class="error" role="alert">
      入班关系读取失败：{{ errors.enrollments }}
    </p>
  </div>
</template>
