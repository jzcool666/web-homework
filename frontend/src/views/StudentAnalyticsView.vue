<script setup>
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useStudentOverview } from '@/composables/useStudentOverview'
import { chapterCompletion, attemptActivity } from '@/utils/learningInsights'
import MetricCard from '@/components/ui/MetricCard.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import RecommendationList from '@/components/home/RecommendationList.vue'
import ChapterProgress from '@/components/home/ChapterProgress.vue'
import ActivityChart from '@/components/home/ActivityChart.vue'
const {
  data,
  errors,
  loading,
  stats,
  learningReady,
  experimentReady,
  recommended,
  load,
} = useStudentOverview()
const activeTab = ref('overview')
const tabs = [
  { id: 'overview', title: '完成概览' },
  { id: 'chapters', title: '章节进度' },
  { id: 'practice', title: '习题分析' },
  { id: 'experiments', title: '实验记录' },
  { id: 'review', title: '复习建议' },
]
const chapters = computed(() =>
  chapterCompletion(
    data.value.points ?? [],
    data.value.progress ?? [],
    data.value.chapters ?? [],
  ),
)
const activity = computed(() => attemptActivity(data.value.attempts ?? []))
function tabKey(event) {
  const index = tabs.findIndex((tab) => tab.id === activeTab.value)
  const next =
    event.key === 'ArrowRight'
      ? (index + 1) % tabs.length
      : event.key === 'ArrowLeft'
        ? (index + tabs.length - 1) % tabs.length
        : event.key === 'Home'
          ? 0
          : event.key === 'End'
            ? tabs.length - 1
            : -1
  if (next < 0) return
  event.preventDefault()
  activeTab.value = tabs[next].id
  event.currentTarget.querySelectorAll('button')[next]?.focus()
}
</script>
<template>
  <div class="dashboard analytics-page">
    <PageHeader
      title="学习分析"
      description="查看自己的学习记录，找到下一步值得复习的内容。"
      ><template #actions
        ><button
          class="button button--secondary"
          type="button"
          :disabled="loading"
          @click="load"
        >
          刷新
        </button></template
      ></PageHeader
    >
    <nav
      class="tabs"
      role="tablist"
      aria-label="学习分析内容"
      @keydown="tabKey"
    >
      <button
        v-for="tab in tabs"
        :id="`analysis-tab-${tab.id}`"
        :key="tab.id"
        role="tab"
        type="button"
        :aria-selected="activeTab === tab.id"
        :aria-controls="`analysis-panel-${tab.id}`"
        :tabindex="activeTab === tab.id ? 0 : -1"
        @click="activeTab = tab.id"
      >
        {{ tab.title }}
      </button>
    </nav>
    <StatePanel v-if="loading" kind="loading" title="正在读取当前学习记录" />
    <template v-else>
      <div class="metric-grid analytics-metrics">
        <MetricCard
          label="知识点完成"
          :value="
            learningReady ? `${stats.learned} / ${stats.knowledgeTotal}` : null
          "
          note="当前已发布 · 自报"
          icon="book"
        /><MetricCard
          label="实验通过"
          :value="
            experimentReady
              ? `${stats.passed} / ${stats.experimentTotal}`
              : null
          "
          note="至少通过一次 · 去重"
          icon="flask"
        /><MetricCard
          label="本次推荐知识点"
          :value="data.recommendations ? recommended.length : null"
          note="仅本次返回"
          icon="spark"
        /><MetricCard
          label="累计实验提交"
          :value="data.attempts ? data.attempts.length : null"
          note="每次尝试各计一次"
          icon="check"
        />
      </div>
      <p v-for="(message, key) in errors" :key="key" class="error" role="alert">
        部分数据读取失败：{{ message }}
      </p>
      <section
        v-show="activeTab === 'overview'"
        id="analysis-panel-overview"
        role="tabpanel"
        aria-labelledby="analysis-tab-overview"
        class="ref-grid"
      >
        <SectionCard title="章节完成情况"
          ><ChapterProgress
            v-if="learningReady && !errors.chapters"
            :rows="chapters"
          />
          <p v-else class="hint">章节完成情况暂不可用。</p>
          <p class="hint chart-note">
            按当前已发布知识点统计，自报完成不代表掌握程度。
          </p></SectionCard
        >
        <SectionCard title="近 7 天实验活动"
          ><ActivityChart v-if="data.attempts" :rows="activity" />
          <p v-else class="hint">实验活动暂不可用。</p></SectionCard
        >
        <SectionCard title="本次复习重点"
          ><RecommendationList
            :items="(data.recommendations ?? []).slice(0, 3)"
          /><RouterLink :to="{ name: 'student-recommendations' }"
            >查看完整复习建议 →</RouterLink
          ></SectionCard
        >
        <SectionCard title="学习建议"
          ><div class="study-advice">
            <span class="study-advice__icon">✦</span>
            <div>
              <h3>
                {{
                  recommended.length
                    ? '沿着推荐知识点，逐个巩固'
                    : '从课程目录开始，按章节复习'
                }}
              </h3>
              <ol>
                <li>阅读知识点，理解电路与状态变化。</li>
                <li>完成习题训练，在提交后核对解析。</li>
                <li>进入实验中心，逐拍预测并验证结果。</li>
              </ol>
              <RouterLink
                class="button button--secondary"
                :to="{ name: 'student-learning' }"
                >返回课程学习 →</RouterLink
              >
            </div>
          </div></SectionCard
        >
      </section>
      <section
        v-show="activeTab === 'chapters'"
        id="analysis-panel-chapters"
        role="tabpanel"
        aria-labelledby="analysis-tab-chapters"
      >
        <SectionCard title="章节进度"
          ><ChapterProgress v-if="learningReady" :rows="chapters" />
          <p class="hint chart-note">
            完成记录为自报；历史撤回知识点不计入当前比例。
          </p></SectionCard
        >
      </section>
      <section
        v-show="activeTab === 'practice'" id="analysis-panel-practice" role="tabpanel" aria-labelledby="analysis-tab-practice"
      >
        <SectionCard title="我的习题记录">
          <p class="hint">练习和班级测评分别保留作答记录；答案与得分以服务端结果页为准。</p>
          <ul v-if="data.assessments?.some(row => row.my_submission_id)" class="overview-list">
            <li v-for="row in data.assessments.filter(row => row.my_submission_id)" :key="row.id"><div><strong>{{ row.title }}</strong><small>{{ row.kind === 'practice' ? '自主练习' : '班级测评' }}</small></div><RouterLink class="button button--secondary" :to="{ name: 'student-assessment', params: { id: row.id } }">继续 / 查看</RouterLink></li>
          </ul>
          <p v-else class="chart-empty">暂无已开始的作答记录。</p>
          <RouterLink class="button button--primary" :to="{ name: 'student-practice' }">开始习题训练 →</RouterLink>
        </SectionCard>
      </section>
      <section
        v-show="activeTab === 'experiments'"
        id="analysis-panel-experiments"
        role="tabpanel"
        aria-labelledby="analysis-tab-experiments"
      >
        <SectionCard title="实验活动"
          ><ActivityChart v-if="data.attempts" :rows="activity" />
          <p v-else class="hint">实验活动暂不可用。</p>
          <RouterLink
            class="button button--secondary"
            :to="{ name: 'student-attempts' }"
            >查看逐次提交记录</RouterLink
          ></SectionCard
        >
      </section>
      <section
        v-show="activeTab === 'review'"
        id="analysis-panel-review"
        role="tabpanel"
        aria-labelledby="analysis-tab-review"
      >
        <SectionCard title="本次复习建议"
          ><RecommendationList :items="data.recommendations ?? []" />
          <p class="hint chart-note">
            推荐优先级用于安排复习顺序；基础路径没有分值。
          </p></SectionCard
        >
      </section>
    </template>
  </div>
</template>
<style scoped>
.analytics-metrics {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.analytics-metrics :deep(.metric-card) {
  align-items: flex-start;
}
.chart-note {
  margin: 14px 0 0;
  font-size: 10px;
}
.study-advice {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 0;
}
.study-advice__icon {
  display: grid;
  place-items: center;
  flex: none;
  width: 36px;
  height: 36px;
  background: #fff4da;
  color: #d9972f;
  border-radius: 50%;
  font-size: 23px;
}
.study-advice h3 {
  font-size: 14px;
}
.study-advice ol {
  color: var(--color-text-secondary);
  padding-left: 17px;
  line-height: 2;
  font-size: 12px;
}
@media (max-width: 620px) {
  .analytics-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
