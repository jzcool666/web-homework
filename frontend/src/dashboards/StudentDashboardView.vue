<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useStudentOverview } from '@/composables/useStudentOverview'
import StudentPreviewTodo from '@/components/StudentPreviewTodo.vue'
import ConceptHero from '@/components/home/ConceptHero.vue'
import RecommendationList from '@/components/home/RecommendationList.vue'
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
</script>
<template>
  <div class="dashboard dashboard--student">
    <PageHeader
      eyebrow="学习空间"
      :title="`你好，${auth.user?.display_name ?? ''}`"
      description="先完成课堂任务，再沿着知识点继续学习。"
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
    <ConceptHero
      title="理解每一拍，连接每一个知识点。"
      lead="触发器、计数器与寄存器，从状态预测开始。"
      cta-label="浏览课程"
      :cta-to="{ name: 'student-learning' }"
    />
    <StatePanel v-if="loading" kind="loading" title="正在读取学习与课堂信息" />
    <div v-else class="dashboard-primary">
      <SectionCard title="当前课堂任务">
        <p
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
                class="button button--primary"
                :to="{ name: 'student-assessment', params: { id: item.id } }"
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
            >查看课堂演示</RouterLink
          ><RouterLink
            class="button button--secondary"
            :to="{ name: 'student-classroom' }"
            >签到与请假</RouterLink
          >
        </div>
      </SectionCard>
      <SectionCard title="继续学习"
        ><p v-if="!learningReady" class="error" role="alert">
          {{ errors.points || errors.progress || '学习进度暂时无法读取' }}
        </p>
        <template v-else
          ><h3>
            {{
              target?.title ??
              (stats.knowledgeTotal
                ? '已完成当前课程，继续复习巩固'
                : '等待课程内容发布')
            }}
          </h3>
          <p class="hint">
            当前已完成 {{ stats.learned }} / {{ stats.knowledgeTotal }} 个知识点
            · 自报完成记录
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
                ? { name: 'student-knowledge', params: { id: target.id } }
                : { name: 'student-learning' }
            "
            >{{ target ? '继续学习' : '浏览课程' }}</RouterLink
          ></template
        ></SectionCard
      >
    </div>
    <div v-if="!loading" class="metric-grid">
      <MetricCard
        label="已完成知识点"
        :value="
          learningReady ? `${stats.learned} / ${stats.knowledgeTotal}` : null
        "
        note="当前已发布内容 · 自报"
        icon="book"
      /><MetricCard
        label="已通过实验"
        :value="
          experimentReady ? `${stats.passed} / ${stats.experimentTotal}` : null
        "
        note="按实验去重 · 当前已发布"
        icon="flask"
      /><MetricCard
        label="本次推荐知识点"
        :value="data.recommendations ? recommended.length : null"
        note="仅统计本次返回，不是全部待复习数"
        icon="spark"
      />
    </div>
    <div class="dashboard-secondary">
      <SectionCard title="本次复习推荐"
        ><StatePanel v-if="loading" kind="loading" title="正在读取推荐" /><p v-else-if="errors.recommendations" class="error" role="alert">
          {{ errors.recommendations }}
        </p>
        <RecommendationList
          v-else
          :items="(data.recommendations ?? []).slice(0, 3)"
        /><RouterLink :to="{ name: 'student-recommendations' }"
          >查看完整推荐说明 →</RouterLink
        ></SectionCard
      ><StudentPreviewTodo />
    </div>
    <p v-if="errors.experiments || errors.attempts" class="error" role="alert">
      实验统计暂不可用：{{ errors.experiments || errors.attempts }}
    </p>
  </div>
</template>
