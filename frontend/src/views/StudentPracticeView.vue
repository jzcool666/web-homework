<script setup>
/**
 * 学生习题训练（SPEC-009 E042）。
 *
 * 自练按知识点或难度从已发布题库出题；错题重练在错题本里按题重练。
 * 服务端会排除本班已发布但未公开反馈的班级测评用题，避免绕过反馈策略。
 */
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { api } from '@/api/client'
import { readAll } from '@/api/pagination'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { ASSESSMENT_STATE_LABEL, KIND_LABEL } from '@/utils/assessment'

const points = ref([])
const assessments = ref([])
const loading = ref(false)
const listError = ref(null)
const error = ref(null)
const notice = ref(null)
const route = useRoute()

const filter = ref({ knowledge_id: '', difficulty: '', count: 5 })

function stateTone(state) {
  if (state === 'open') return 'success'
  if (state === 'upcoming') return 'warning'
  return 'neutral'
}

async function load() {
  loading.value = true
  listError.value = null
  try {
    const [pointList, list] = await Promise.all([
      readAll('/knowledge-points'),
      readAll('/assessments'),
    ])
    points.value = pointList
    assessments.value = list
    // E042 要求必须给出过滤条件或错题题目，没有「任意题」模式；默认选第一个知识点
    if (!filter.value.knowledge_id && pointList.length > 0) {
      const requested = Number(route?.query?.knowledge_id)
      filter.value.knowledge_id = pointList.find(point => point.id === requested)?.id ?? pointList[0].id
    }
  } catch (err) {
    listError.value = err.message
  } finally {
    loading.value = false
  }
}

async function createPractice() {
  error.value = null
  notice.value = null
  if (!filter.value.knowledge_id && !filter.value.difficulty) {
    error.value = '请选择知识点或难度后再生成自练（接口不允许无条件出题）'
    return
  }
  const payload = { count: Number(filter.value.count) || 5 }
  if (filter.value.knowledge_id) payload.knowledge_ids = [Number(filter.value.knowledge_id)]
  if (filter.value.difficulty) payload.difficulty = Number(filter.value.difficulty)
  try {
    const practice = await api.post('/practice-sessions', payload)
    notice.value = `已生成自练「${practice.title}」，共 ${practice.items.length} 题`
    await load()
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <PageHeader
      eyebrow="学习与练习"
      title="习题训练"
      description="自练从已发布题库出题，提交后立即公布答案与解析；每次重练都会生成一份新的练习，不影响首答统计。"
    >
      <template #actions>
        <RouterLink class="button button--secondary" :to="{ name: 'student-mistakes' }">
          错题本
        </RouterLink>
      </template>
    </PageHeader>

    <p v-if="notice" class="success">{{ notice }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <SectionCard title="开始新的自练">
      <form class="practice-form form-fields" @submit.prevent="createPractice">
        <div class="field">
          <label for="p_knowledge">知识点</label>
          <select id="p_knowledge" v-model="filter.knowledge_id">
            <option value="">不限</option>
            <option v-for="point in points" :key="point.id" :value="point.id">
              {{ point.title }}
            </option>
          </select>
        </div>
        <div class="field">
          <label for="p_difficulty">难度</label>
          <select id="p_difficulty" v-model="filter.difficulty">
            <option value="">不限</option>
            <option value="1">基础</option>
            <option value="2">进阶</option>
            <option value="3">挑战</option>
          </select>
        </div>
        <div class="field">
          <label for="p_count">题目数量（1—20）</label>
          <input id="p_count" v-model.number="filter.count" type="number" min="1" max="20" />
        </div>
        <div class="form-actions"><button class="primary" type="submit">生成自练</button></div>
      </form>
      <p class="hint">
        自练必须指定知识点或难度之一（错题重练在错题本里按题发起）。可用题目不足时服务端返回 422
        并说明可用题数；本班已发布但尚未公开反馈的测评用题不会进入自练。
      </p>
    </SectionCard>

    <SectionCard title="我的练习与测评">
      <StatePanel v-if="loading" kind="loading" title="正在读取练习" />
      <StatePanel v-else-if="listError" kind="error" title="练习列表加载失败" :description="listError" />
      <StatePanel
        v-else-if="assessments.length === 0"
        title="还没有练习"
        description="用上方表单生成第一份自练，或先到错题本重练。"
      />
      <div v-else class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>标题</th>
              <th>类型</th>
              <th>状态</th>
              <th>总分</th>
              <th>反馈</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in assessments" :key="item.id">
              <td>{{ item.title }}</td>
              <td>{{ KIND_LABEL[item.kind] ?? item.kind }}</td>
              <td>
                <StatusBadge :tone="stateTone(item.effective_state)">
                  {{ ASSESSMENT_STATE_LABEL[item.effective_state] ?? item.effective_state }}
                </StatusBadge>
              </td>
              <td>{{ item.total_score }}</td>
              <td>
                <StatusBadge :tone="item.feedback_released ? 'success' : 'warning'">
                  {{ item.feedback_released ? '已公开' : '待公开' }}
                </StatusBadge>
              </td>
              <td class="row-actions">
                <RouterLink
                  v-if="item.effective_state !== 'upcoming'"
                  :to="{ name: 'student-assessment', params: { id: item.id } }"
                >
                  {{ item.my_submission_id ? '继续/查看' : '开始作答' }}
                </RouterLink>
                <span v-else class="hint">未开始</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>
  </div>
</template>

<style scoped>

.row-actions {
  white-space: nowrap;
}
</style>
