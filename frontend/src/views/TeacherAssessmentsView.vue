<script setup>
import { initialClassId } from '@/utils/overview'
/**
 * 教师测评管理（SPEC-010，E037/E039 的课堂入口）。
 *
 * 只列本人任教班级的测评；草稿可改题，发布后题面与名单冻结。
 * 讲评、进度、结束与公开反馈在详情页。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api } from '@/api/client'
import QuestionPicker from '@/components/QuestionPicker.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { ASSESSMENT_STATE_LABEL, KIND_LABEL } from '@/utils/assessment'

const classes = ref([])
const classId = ref('')
const assessments = ref([])
const bank = ref([])
const loading = ref(false)
const listError = ref(null)
const error = ref(null)
const notice = ref(null)

const form = ref({ kind: 'quiz', title: '', items: [] })

const kindOptions = [
  { value: 'quiz', label: '随堂测' },
  { value: 'homework', label: '作业' },
  { value: 'exam', label: '考试' },
]

const totalPoints = computed(() =>
  form.value.items.reduce((sum, item) => sum + (Number(item.points) || 0), 0),
)

function stateTone(state) {
  if (state === 'open') return 'success'
  if (state === 'upcoming') return 'warning'
  return 'neutral'
}

async function loadBank() {
  bank.value = await api.get('/questions?page_size=100')
}

async function loadAssessments() {
  if (!classId.value) {
    assessments.value = []
    return
  }
  loading.value = true
  listError.value = null
  try {
    assessments.value = await api.get(`/assessments?class_id=${classId.value}&page_size=100`)
  } catch (err) {
    listError.value = err.message
  } finally {
    loading.value = false
  }
}

async function loadClasses() {
  classes.value = await api.get('/classes?page_size=100')
  if (!classId.value) classId.value = initialClassId(classes.value)
}

async function createDraft() {
  error.value = null
  notice.value = null
  if (form.value.items.length === 0) {
    error.value = '请先从题库勾选题目（1—30 题）'
    return
  }
  try {
    const draft = await api.post('/assessments', {
      class_id: Number(classId.value),
      kind: form.value.kind,
      title: form.value.title,
      items: form.value.items,
    })
    notice.value = `已创建草稿「${draft.title}」，共 ${draft.items.length} 题、${draft.total_score} 分`
    form.value = { kind: form.value.kind, title: '', items: [] }
    await loadAssessments()
  } catch (err) {
    error.value = err.message
  }
}

onMounted(async () => {
  try {
    await Promise.all([loadClasses(), loadBank()])
    await loadAssessments()
  } catch (err) {
    listError.value = err.message
  }
})
</script>

<template>
  <div class="page">
    <PageHeader icon="check" :steps="['填写测评信息', '选择题目与分值', '创建草稿并进入讲评']"
      eyebrow="测评"
      title="测评与讲评"
      description="发布时冻结题目版本、答案与名单；结束后可提前结束、公开反馈并查看统计。投屏统计只显示聚合结果，不含学生身份。"
    />

    <p v-if="notice" class="success">{{ notice }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <SectionCard title="选择班级">
      <div class="field">
        <label for="a_class">班级</label>
        <select id="a_class" v-model="classId" @change="loadAssessments">
          <option value="" disabled>请选择班级</option>
          <option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
      </div>
      <p v-if="classes.length === 0" class="hint">还没有任教的班级，请联系管理员分配。</p>
    </SectionCard>

    <SectionCard title="新建测评草稿">
      <form class="draft-form" @submit.prevent="createDraft">
        <div class="form-fields">
        <div class="field">
          <label for="a_kind">类型</label>
          <select id="a_kind" v-model="form.kind">
            <option v-for="option in kindOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </div>
        <div class="field">
          <label for="a_title">标题</label>
          <input id="a_title" v-model="form.title" maxlength="100" required />
        </div>
        </div>
        <QuestionPicker v-model="form.items" :questions="bank" />
        <div class="form-actions">
          <p class="hint">
        草稿总分 {{ totalPoints }}；发布前可以改题，发布后题目、答案与名单在一个事务里冻结。
          </p>
          <button class="primary" type="submit" :disabled="!classId">创建草稿</button>
        </div>
      </form>
    </SectionCard>

    <SectionCard title="我的测评">
      <StatePanel v-if="loading" kind="loading" title="正在读取测评" />
      <StatePanel v-else-if="listError" kind="error" title="测评列表加载失败" :description="listError" />
      <StatePanel
        v-else-if="assessments.length === 0"
        title="该班还没有测评"
        description="用上方表单创建草稿，再进入详情页发布。"
      />
      <div v-else class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>标题</th>
              <th>类型</th>
              <th>状态</th>
              <th>起止</th>
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
              <td class="window">
                {{ item.starts_at ?? '—' }} → {{ item.ends_at ?? '—' }}
              </td>
              <td>{{ item.total_score }}</td>
              <td>
                <StatusBadge :tone="item.feedback_released ? 'success' : 'warning'">
                  {{ item.feedback_released ? '已公开' : '未公开' }}
                </StatusBadge>
              </td>
              <td>
                <RouterLink :to="{ name: 'teacher-assessment', params: { id: item.id } }">
                  进入
                </RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>
  </div>
</template>

<style scoped>
.table-scroll td:first-child { min-width: 12rem; }
.draft-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-4);
}

.window {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  white-space: nowrap;
}
</style>
