<script setup>
import { useStudentOverview } from '@/composables/useStudentOverview'
import { percent } from '@/utils/overview'
import MetricCard from '@/components/ui/MetricCard.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import RecommendationList from '@/components/home/RecommendationList.vue'
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
</script>
<template>
  <div class="dashboard">
    <PageHeader
      eyebrow="学习提升"
      title="学习分析"
      description="查看当前课程完成情况与复习建议；完成标记是自报记录，不代表掌握程度。"
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
    <StatePanel v-if="loading" kind="loading" title="正在读取当前学习记录" />
    <template v-else
      ><div class="metric-grid">
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
          note="至少通过一次 · 按实验去重"
          icon="flask"
        /><MetricCard
          label="本次推荐知识点"
          :value="data.recommendations ? recommended.length : null"
          note="仅本次返回的推荐"
          icon="spark"
        />
      </div>
      <SectionCard title="当前完成情况"
        ><div
          v-for="row in [
            {
              title: '课程完成',
              value: learningReady ? stats.learningRatio : null,
            },
            {
              title: '实验通过',
              value: experimentReady ? stats.experimentRatio : null,
            },
          ]"
          :key="row.title"
          class="ratio-row"
        >
          <strong>{{ row.title }}</strong
          ><progress
            v-if="row.value !== null"
            :value="row.value"
            max="1"
            :aria-label="row.title"
          /><span>{{ percent(row.value) }}</span>
        </div>
        <p class="hint">
          只统计当前已发布内容。未发布内容的历史记录与重复实验尝试不增加分子。
        </p></SectionCard
      >
      <p v-for="(message, key) in errors" :key="key" class="error" role="alert">
        部分数据读取失败：{{ message }}
      </p>
      <SectionCard title="本次复习重点"
        ><RecommendationList :items="data.recommendations ?? []" />
        <p class="hint">
          推荐优先级用于安排复习顺序；基础路径没有分值。这里不提供学习时长、掌握度百分比或历史趋势。
        </p></SectionCard
      ></template
    >
  </div>
</template>
