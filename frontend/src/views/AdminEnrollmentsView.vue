<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api } from '@/api/client'

const props = defineProps({ id: { type: String, required: true } })

const classId = Number(props.id)
const schoolClass = ref(null)
const enrollments = ref([])
const students = ref([])
const selected = ref('')
const error = ref(null)
const notice = ref(null)

function studentName(studentId) {
  const found = students.value.find((s) => s.id === studentId)
  return found ? `${found.display_name}（${found.student_no}）` : `#${studentId}`
}

async function load() {
  error.value = null
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
    error.value = err.message
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
  <main class="page">
    <h1>班级名单</h1>
    <p class="hint">
      <RouterLink :to="{ name: 'admin-classes' }">← 返回班级管理</RouterLink>
      <template v-if="schoolClass"> · {{ schoolClass.name }}</template>
    </p>
    <p class="hint">每名学生最多属于一个有效班级；要换班需先在原班级移出。</p>

    <section class="card">
      <h2>加入学生</h2>
      <form @submit.prevent="enroll(selected, true)">
        <div class="field">
          <label for="student_id">学生</label>
          <select id="student_id" v-model="selected" required>
            <option value="" disabled>请选择学生</option>
            <option v-for="student in students" :key="student.id" :value="student.id">
              {{ student.display_name }}（{{ student.student_no }}）
            </option>
          </select>
        </div>
        <button class="primary" type="submit">加入班级</button>
      </form>
      <p v-if="notice" class="success">{{ notice }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </section>

    <section class="card">
      <h2>在班学生</h2>
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
              <span v-if="!item.active" class="badge off">已移出</span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>
