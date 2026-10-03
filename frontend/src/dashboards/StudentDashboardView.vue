<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useStudentOverview } from '@/composables/useStudentOverview'
import { chapterCompletion } from '@/utils/learningInsights'
import StudentPreviewTodo from '@/components/StudentPreviewTodo.vue'
import RecommendationList from '@/components/home/RecommendationList.vue'
import CircuitPreview from '@/components/home/CircuitPreview.vue'
import TimingPreview from '@/components/home/TimingPreview.vue'
import ChapterProgress from '@/components/home/ChapterProgress.vue'
import MetricCard from '@/components/ui/MetricCard.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
const auth = useAuthStore()
const {
  data,
  errors,
  loading,
  stats,
  learningReady,
  experimentReady,
  target,
  recommended,
  load,
} = useStudentOverview()
const activities = computed(() =>
  (data.value.assessments ?? []).filter(
    (row) => row.kind !== 'practice' && row.effective_state === 'open',
  ),
)
const chapters = computed(() =>
  chapterCompletion(
    data.value.points ?? [],
    data.value.progress ?? [],
    data.value.chapters ?? [],
  ),
)
const preview = computed(
  () =>
    (data.value.experiments ?? []).find(
      (row) => row.knowledge_id === target.value?.id,
    ) ?? data.value.experiments?.[0],
)
const done = computed(
  () =>
    new Set(
      (data.value.progress ?? [])
        .filter((row) => row.completed)
        .map((row) => row.knowledge_id),
    ),
)
</script>
<template>
  <div class="dashboard dashboard--student">
    <PageHeader
      :title="`你好，${auth.user?.display_name ?? ''} 👋`"
      description="继续学习时序逻辑，把每一次状态变化弄明白。"
    >
      <template #actions
        ><button
          class="button button--secondary"
          type="button"
          :disabled="loading"
          @click="load"
        >
          刷新
        </button></template
      >
    </PageHeader>
    <StatePanel v-if="loading" kind="loading" title="正在读取学习与课堂信息" />
    <template v-else>
      <div class="student-home-layout">
        <div class="student-home-main">
          <SectionCard title="继续学习" class="continue-card">
            <p v-if="!learningReady" class="error" role="alert">
              {{ errors.points || errors.progress || '学习进度暂时无法读取' }}
            </p>
            <template v-else>
              <div class="continue-card__body">
                <div>
                  <h3>
                    {{
                      target?.title ??
                      (stats.knowledgeTotal
                        ? '当前课程已完成，继续复习巩固'
                        : '等待课程内容发布')
                    }}
                  </h3>
                  <p class="hint">
                    已完成 {{ stats.learned }} /
                    {{ stats.knowledgeTotal }} 个知识点 · 自报记录
                  </p>
                  <progress
                    v-if="stats.knowledgeTotal"
                    :value="stats.learned"
                    :max="stats.knowledgeTotal"
                    aria-label="当前知识点完成进度"
                  /><RouterLink
                    class="button button--primary"
                    :to="
                      target
                        ? {
                            name: 'student-knowledge',
                            params: { id: target.id },
                          }
                        : { name: 'student-learning' }
                    "
                    >{{ target ? '继续学习' : '浏览课程' }} →</RouterLink
                  >
                </div>
                <CircuitPreview v-if="preview" :kind="preview.simulator_type" />
              </div>
            </template>
          </SectionCard>
          <div class="metric-grid metric-grid--four">
            <MetricCard
              label="已完成知识点"
              :value="
                learningReady
                  ? `${stats.learned} / ${stats.knowledgeTotal}`
                  : null
              "
              note="当前已发布 · 自报"
              icon="book"
            />
            <MetricCard
              label="已开始练习"
              :value="
                data.assessments
                  ? data.assessments.filter(
                      (row) => row.kind === 'practice' && row.my_submission_id,
                    ).length
                  : null
              "
              note="已有作答记录的自练"
              icon="check"
            />
            <MetricCard
              label="已通过实验"
              :value="
                experimentReady
                  ? `${stats.passed} / ${stats.experimentTotal}`
                  : null
              "
              note="按实验去重"
              icon="flask"
            />
            <MetricCard
              label="本次推荐知识点"
              :value="data.recommendations ? recommended.length : null"
              note="仅本次返回"
              icon="spark"
            />
          </div>
          <SectionCard title="当前知识点">
            <p v-if="errors.points" class="error" role="alert">
              {{ errors.points }}
            </p>
            <p v-else-if="!data.points?.length" class="hint">
              当前没有已发布知识点。
            </p>
            <div v-else class="knowledge-tiles">
              <RouterLink
                v-for="point in data.points.slice(0, 4)"
                :key="point.id"
                :to="{ name: 'student-knowledge', params: { id: point.id } }"
                :class="{ 'knowledge-tile--current': point.id === target?.id }"
                ><svg viewBox="0 0 40 34" aria-hidden="true">
                  <path d="M2 10H11M2 24H11M29 10H38M29 24H38" />
                  <rect x="11" y="4" width="18" height="26" rx="3" />
                  <path d="m11 19 4 3-4 3" /></svg
                ><strong>{{ point.title }}</strong
                ><span>{{
                  errors.progress
                    ? '进度暂不可用'
                    : done.has(point.id)
                      ? '已完成'
                      : point.id === target?.id
                        ? '继续学习'
                        : '未完成'
                }}</span></RouterLink
              >
            </div>
          </SectionCard>
          <div class="ref-grid">
            <SectionCard title="复习建议"
              ><RecommendationList
                :items="(data.recommendations ?? []).slice(0, 2)"
              />
              <p v-if="errors.recommendations" class="error" role="alert">
                {{ errors.recommendations }}
              </p>
              <RouterLink :to="{ name: 'student-recommendations' }"
                >查看复习建议 →</RouterLink
              ></SectionCard
            ><SectionCard title="章节完成情况"
              ><ChapterProgress
                v-if="learningReady"
                :rows="chapters.slice(0, 4)"
              />
              <p v-else class="hint">完成记录暂不可用。</p>
              <p class="hint chapter-note">
                自报完成比例，不代表知识掌握程度。
              </p></SectionCard
            >
          </div>
        </div>
        <div class="student-home-side">
          <SectionCard title="时序逻辑概览" class="logic-overview"
            ><template v-if="preview"
              ><h3>{{ preview.title }}</h3>
              <CircuitPreview :kind="preview.simulator_type" />
              <h3 class="logic-overview__timing">输入时序采样</h3>
              <TimingPreview
                :kind="preview.simulator_type"
                :checkpoints="preview.checkpoints ?? []"
              /><RouterLink
                class="button button--primary"
                :to="{ name: 'student-experiment', params: { id: preview.id } }"
                >进入实验预测 →</RouterLink
              ></template
            >
            <p v-else class="hint">
              发布实验后，可在这里查看电路与输入采样。
            </p></SectionCard
          >
          <SectionCard title="当前课堂任务"
            ><p
              v-if="errors.classes || errors.assessments"
              class="error"
              role="alert"
            >
              {{ errors.classes || errors.assessments }}
            </p>
            <p v-else-if="!data.classes?.length" class="hint">
              尚未加入班级，请联系教师或管理员。
            </p>
            <template v-else
              ><p class="eyebrow">{{ data.classes[0].name }}</p>
              <ul v-if="activities.length" class="overview-list">
                <li v-for="item in activities.slice(0, 2)" :key="item.id">
                  <strong>{{ item.title }}</strong
                  ><RouterLink
                    :to="{
                      name: 'student-assessment',
                      params: { id: item.id },
                    }"
                    >{{
                      item.my_submission_id ? '继续 / 查看' : '开始作答'
                    }}</RouterLink
                  >
                </li>
              </ul>
              <p v-else class="hint">当前没有进行中的班级测评。</p></template
            >
            <div class="overview-actions">
              <RouterLink
                class="button button--secondary"
                :to="{ name: 'student-demos' }"
                >课堂演示</RouterLink
              ><RouterLink
                class="button button--secondary"
                :to="{ name: 'student-classroom' }"
                >签到与请假</RouterLink
              >
            </div></SectionCard
          >
        </div>
      </div>
      <StudentPreviewTodo />
      <p
        v-if="errors.experiments || errors.attempts"
        class="error"
        role="alert"
      >
        实验统计暂不可用：{{ errors.experiments || errors.attempts }}
      </p>
    </template>
  </div>
</template>
<style scoped>
.student-home-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(260px, 1fr);
  gap: 14px;
  align-items: start;
}
.student-home-main,
.student-home-side {
  display: grid;
  gap: 14px;
  min-width: 0;
}
.continue-card {
  background: linear-gradient(100deg, #f1f6ff, #fff 75%);
  border-left: 4px solid #86afff;
}
.continue-card__body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px;
  gap: 18px;
  align-items: center;
}
.continue-card h3 {
  font-size: 18px;
}
.continue-card .circuit-preview {
  border: 0;
  padding: 0;
  background: transparent;
}
.metric-grid--four {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.metric-grid--four :deep(.metric-card) {
  display: block;
  padding: 12px;
}
.metric-grid--four :deep(.metric-card__icon) {
  display: none;
}
.metric-grid--four :deep(strong) {
  font-size: 20px;
}
.knowledge-tiles {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.knowledge-tiles a {
  display: grid;
  justify-items: center;
  gap: 9px;
  padding: 14px 8px;
  border: 1px solid var(--color-border);
  border-radius: 9px;
  text-decoration: none;
  text-align: center;
  font-size: 11px;
  color: var(--color-text-primary);
}
.knowledge-tiles svg {
  width: 36px;
  height: 32px;
  stroke: #537ac5;
  stroke-width: 1.2;
  fill: none;
}
.knowledge-tiles strong {
  font-size: 11px;
  line-height: 1.5;
}
.knowledge-tiles span {
  font-size: 10px;
  border-radius: 5px;
  background: #eff3fa;
  color: var(--color-text-secondary);
  padding: 3px 6px;
}
.knowledge-tiles a.knowledge-tile--current {
  background: #f2f6ff;
  border-color: #6790ff;
}
.knowledge-tile--current span {
  background: var(--color-primary);
  color: white;
}
.logic-overview > .circuit-preview {
  max-width: none;
}
.logic-overview__timing {
  margin-top: 20px;
}
.logic-overview > .button {
  margin-top: 20px;
  width: 100%;
}
.chapter-note {
  margin: 14px 0 0;
  font-size: 10px;
}
@media (max-width: 1100px) {
  .student-home-layout {
    grid-template-columns: 1fr;
  }
  .student-home-side {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 620px) {
  .student-home-main,
  .student-home-side {
    display: contents;
  }
  .student-home-side > .section-card:not(.logic-overview) {
    order: -2;
  }
  .continue-card {
    order: -1;
  }
  .metric-grid--four,
  .knowledge-tiles {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .continue-card__body {
    grid-template-columns: minmax(0, 1fr) 95px;
    gap: 8px;
  }
  .continue-card h3 {
    font-size: 16px;
  }
  .student-home-side > .logic-overview {
    order: 2;
  }
}
</style>
