<script setup>
/**
 * 学生状态表识别（SPEC-017 E069/E070）。
 *
 * 上传规定格式的状态表图片，得到状态序列与次态转换供人工核对。
 * 结果只是辅助信息：页面固定标注「需人工核对」，实验判分仍由后端重算。
 */
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import {
  FORMAT_NOTE,
  REVIEW_NOTE,
  bitText,
  confidenceText,
  errorHint,
  statusText,
  transitionText,
} from '@/utils/recognition'

const classes = ref([])
const classId = ref('')
const file = ref(null)
const fileInput = ref(null)
const task = ref(null)
const uploading = ref(false)
const error = ref(null)
const listError = ref(null)

const result = computed(() => task.value?.result ?? null)
const failure = computed(() => task.value?.error ?? null)

function onFileChange(event) {
  file.value = event.target.files?.[0] ?? null
}

async function loadClasses() {
  classes.value = await api.get('/classes?page_size=100')
  if (!classId.value && classes.value.length > 0) classId.value = classes.value[0].id
}

async function submit() {
  error.value = null
  if (!file.value) {
    error.value = '请先选择一张状态表图片（PNG 或 JPEG）'
    return
  }
  uploading.value = true
  try {
    const form = new FormData()
    form.append('image', file.value)
    form.append('class_id', String(classId.value))
    form.append('kind', 'state_table')
    task.value = await api.postForm('/recognition-tasks', form)
  } catch (err) {
    error.value = err.message
    task.value = null
  } finally {
    uploading.value = false
  }
}

function reset() {
  task.value = null
  file.value = null
  error.value = null
  if (fileInput.value) fileInput.value.value = ''
}

onMounted(async () => {
  try {
    await loadClasses()
  } catch (err) {
    listError.value = err.message
  }
})
</script>

<template>
  <div class="page">
    <PageHeader icon="network" :steps="['上传规定格式', '等待识别', '人工核对次态']"
      eyebrow="实验"
      title="状态表识别"
      description="上传规定格式的时序状态表图片，系统读出状态序列与次态转换，供你与手工推导核对。"
    />

    <SectionCard title="上传">
      <div class="filters">
        <div class="field">
          <label for="r_class">班级</label>
          <select id="r_class" v-model="classId">
            <option value="" disabled>请选择班级</option>
            <option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </div>
        <div class="field">
          <label for="r_image">状态表图片（PNG / JPEG，≤20MiB）</label>
          <input id="r_image" ref="fileInput" type="file" accept="image/png,image/jpeg" @change="onFileChange" />
        </div>
        <button class="button button--primary" type="button" :disabled="uploading || !classId" @click="submit">
          {{ uploading ? '识别中…' : '开始识别' }}
        </button>
        <button class="button button--secondary" type="button" @click="reset">清空</button>
      </div>
      <p class="hint">{{ FORMAT_NOTE }}</p>
      <p v-if="classes.length === 0" class="hint">还没有分配班级，请联系教师或管理员。</p>
      <p v-if="listError" class="error" role="alert">{{ listError }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </SectionCard>

    <template v-if="task">
      <SectionCard title="识别结果">
        <div class="summary">
          <StatusBadge :tone="task.status === 'done' ? 'success' : 'danger'">
            {{ statusText(task.status) }}
          </StatusBadge>
          <span v-if="result">置信度：<strong>{{ confidenceText(result.confidence) }}</strong></span>
          <span v-if="result">规模：{{ result.rows }} 行 × {{ result.cols }} 列</span>
        </div>
        <p class="basis">{{ REVIEW_NOTE }}</p>

        <StatePanel
          v-if="failure"
          kind="error"
          :title="errorHint(failure.code)"
          :description="failure.message"
        />
        <template v-else-if="result">
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>拍</th>
                  <th>Q3Q2Q1Q0</th>
                  <th>值</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="state in result.states" :key="state.row">
                  <td>{{ state.row + 1 }}</td>
                  <td class="mono">{{ bitText(state.value) }}</td>
                  <td>{{ state.value }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <h3 class="subtitle">次态转换</h3>
          <ul class="transitions">
            <li v-for="(item, index) in result.transitions" :key="index" class="mono">
              {{ transitionText(item) }}
            </li>
          </ul>
        </template>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: 0 var(--space-4);
  align-items: end;
  margin-bottom: var(--space-3);
}

.filters button {
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

.subtitle {
  margin: var(--space-4) 0 var(--space-2);
  font-size: var(--font-size-base);
}

.transitions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
  list-style: none;
  padding: 0;
  margin: 0;
}

.mono {
  font-family: var(--font-mono);
}
</style>
