<script setup>
/**
 * 组卷用的题目选择器（SPEC-010 E037/E038）。
 *
 * 只挑题与分值，不改题目本身；选中顺序就是 position 顺序。
 *
 * 内部保留一份本地选中态：props 是异步更新的，若每次都从 props 计算，
 * 同一 tick 内连续点两个复选框会丢掉前一次选择。
 */
import { computed, ref, watch } from 'vue'

import { DIFFICULTY_LABEL, QUESTION_TYPE_LABEL } from '@/utils/assessment'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  questions: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const local = ref(props.modelValue.map((item) => ({ ...item })))
watch(
  () => props.modelValue,
  (value) => {
    local.value = (value ?? []).map((item) => ({ ...item }))
  },
)

const selectedIds = computed(() => local.value.map((item) => item.question_id))


function push() {
  emit('update:modelValue', local.value.map((item) => ({ ...item })))
}

function toggle(questionId) {
  const index = local.value.findIndex((item) => item.question_id === questionId)
  if (index >= 0) {
    local.value.splice(index, 1)
  } else {
    local.value.push({ question_id: questionId, points: 5 })
  }
  push()
}

function setPoints(questionId, value) {
  const points = Math.max(1, Math.min(100, Number(value) || 1))
  local.value = local.value.map((item) =>
    item.question_id === questionId ? { ...item, points } : item,
  )
  push()
}

const totalPoints = computed(() =>
  local.value.reduce((sum, item) => sum + (Number(item.points) || 0), 0),
)

function stemOf(questionId) {
  return props.questions.find((question) => question.id === questionId)?.stem_md ?? `#${questionId}`
}
</script>

<template>
  <div class="picker">
    <p class="hint">
      已选 {{ local.length }} 题，合计 {{ totalPoints }} 分（1—30 题，每题 1—100 分）。
    </p>
    <ol v-if="local.length" class="chosen">
      <li v-for="item in local" :key="item.question_id">
        <span class="chosen__stem">{{ stemOf(item.question_id) }}</span>
        <label class="chosen__points">
          分值
          <input
            type="number"
            min="1"
            max="100"
            :value="item.points"
            @change="setPoints(item.question_id, $event.target.value)"
          />
        </label>
        <button class="link" type="button" @click="toggle(item.question_id)">移除</button>
      </li>
    </ol>
    <p v-else class="hint">还没有选题，从下面的题库里勾选。</p>

    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>选</th>
            <th>ID</th>
            <th>题型</th>
            <th>题干</th>
            <th>难度</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="question in questions" :key="question.id">
            <td>
              <input
                type="checkbox"
                :checked="selectedIds.includes(question.id)"
                :aria-label="`选择题目 ${question.id}`"
                @change="toggle(question.id)"
              />
            </td>
            <td>{{ question.id }}</td>
            <td>{{ QUESTION_TYPE_LABEL[question.type] ?? question.type }}</td>
            <td class="stem">{{ question.stem_md }}</td>
            <td>{{ DIFFICULTY_LABEL[question.difficulty] ?? question.difficulty }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="questions.length === 0" class="hint">题库里还没有已发布题目，请先到「题库」创建。</p>
  </div>
</template>

<style scoped>
.chosen {
  margin: 0 0 var(--space-3);
  padding: var(--space-3) var(--space-3) var(--space-3) var(--space-6);
  border: 1px dashed #c6d4ee;
  border-radius: var(--radius-sm);
}

.chosen li {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.chosen__stem {
  flex: 1;
}

.chosen__points {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  white-space: nowrap;
}

.chosen__points input {
  width: 4.5rem;
}

.stem {
  max-width: 26rem;
}
</style>
