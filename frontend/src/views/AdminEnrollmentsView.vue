<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'

const props = defineProps({ id: { type: String, required: true } })

const classId = Number(props.id)
const schoolClass = ref(null)
const enrollments = ref([])
const loading = ref(false)
const listError = ref(null)
const students = ref([])
const selected = ref('')
const error = ref(null)
const notice = ref(null)

function studentName(studentId) {
  const found = students.value.find((s) => s.id === studentId)
  return found ? `${found.display_name}（${found.student_no}）` : `#${studentId}`
}

async function load() {
  loading.value = true
  listError.value = null
  try {
    const [classList, roster, studentList] = await Promise.all([
      api.get('/classes?page_size=100'),
      api.get(`/classes/${classId}/enrollments?page_size=100`),
      api.get('/users?role=student&page_size=100'),
    ])
    schoolClass.value = classList.find((c) => c.id === classId) ?? null
    enrollments.value = roster
    students.value = studentList
  } catch (err) {
    listError.value = err.message
  } finally {
    loading.value = false
  }
}

async function enroll(studentId, active) {
  error.value = null
  notice.value = null
  try {
    await api.put(`/classes/${classId}/enrollments`, {
      student_id: Number(studentId),
      active,
    })
    notice.value = active ? '已加入班级' : '已移出班级'
    selected.value = ''
    await load()
  } catch (err) {
    error.value = err.message
    await load()
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <PageHeader icon="people" :steps="['选择学生', '加入班级', '核对名单']" eyebrow="基础管理" title="班级名单" description="每名学生最多属于一个有效班级；要换班需先在原班级移出。" />
    <p class="hint">
      <RouterLink :to="{ name: 'admin-classes' }">← 返回班级管理</RouterLink>
      <template v-if="schoolClass"> · {{ schoolClass.name }}</template>
    </p>
    <SectionCard title="加入学生">
      <form class="admin-form" @submit.prevent="enroll(selected, true)">
        <div class="field">
          <label for="student_id">学生</label>
          <select id="student_id" v-model="selected" required>
            <option value="" disabled>请选择学生</option>
            <option v-for="student in students" :key="student.id" :value="student.id">
              {{ student.display_name }}（{{ student.student_no }}）
            </option>
          </select>
        </div>
        <div class="form-actions"><button class="primary" type="submit">加入班级</button></div>
      </form>
      <p v-if="notice" class="success">{{ notice }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </SectionCard>

    <SectionCard title="在班学生">
      <StatePanel v-if="loading" kind="loading" title="正在读取班级名单" />
      <StatePanel v-else-if="listError" kind="error" title="班级名单加载失败" :description="listError" />
      <StatePanel v-else-if="enrollments.length === 0" title="暂无学生" description="选择学生并加入班级后会显示在这里。" />
      <div v-else class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>学号</th>
            <th>姓名</th>
            <th>加入时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in enrollments" :key="`${item.class_id}-${item.student_id}`">
            <td>{{ item.student_id }}</td>
            <td>{{ studentName(item.student_id) }}</td>
            <td>{{ item.joined_at }}</td>
            <td>
              <button class="link" type="button" @click="enroll(item.student_id, !item.active)">
                {{ item.active ? '移出' : '恢复' }}
              </button>
              <StatusBadge v-if="!item.active" tone="danger">已移出</StatusBadge>
            </td>
          </tr>
        </tbody>
      </table>
      </div>
    </SectionCard>
  </div>
</template>
