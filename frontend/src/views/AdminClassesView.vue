<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'

const classes = ref([])
const loading = ref(false)
const listError = ref(null)
const teachers = ref([])
const error = ref(null)
const notice = ref(null)
const form = ref({ name: '', teacher_id: '' })

async function load() {
  loading.value = true
  listError.value = null
  try {
    const [classList, teacherList] = await Promise.all([
      api.get('/classes?page_size=100'),
      api.get('/users?role=teacher&active=true&page_size=100'),
    ])
    classes.value = classList
    teachers.value = teacherList
  } catch (err) {
    listError.value = err.message
  } finally {
    loading.value = false
  }
}

async function createClass() {
  error.value = null
  notice.value = null
  try {
    await api.post('/classes', {
      name: form.value.name,
      teacher_id: Number(form.value.teacher_id),
    })
    notice.value = `已创建班级 ${form.value.name}`
    form.value = { name: '', teacher_id: '' }
    await load()
  } catch (err) {
    error.value = err.message
  }
}

/** 换教师后权限立即变化：旧教师马上失去该班对象访问权。 */
async function changeTeacher(schoolClass, teacherId) {
  error.value = null
  try {
    await api.patch(`/classes/${schoolClass.id}`, {
      version: schoolClass.version,
      teacher_id: Number(teacherId),
    })
    await load()
  } catch (err) {
    error.value = err.message
    await load()
  }
}

async function toggleActive(schoolClass) {
  error.value = null
  try {
    await api.patch(`/classes/${schoolClass.id}`, {
      version: schoolClass.version,
      active: !schoolClass.active,
    })
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
    <PageHeader eyebrow="基础管理" title="班级管理" description="每个班级一名任课教师。更换教师后，教学数据权限立即随之变化。" />

    <SectionCard title="新建班级">
      <form class="admin-form" @submit.prevent="createClass">
        <div class="field">
          <label for="class_name">班级名称</label>
          <input id="class_name" v-model="form.name" required />
        </div>
        <div class="field">
          <label for="class_teacher">任课教师</label>
          <select id="class_teacher" v-model="form.teacher_id" required>
            <option value="" disabled>请选择教师</option>
            <option v-for="teacher in teachers" :key="teacher.id" :value="teacher.id">
              {{ teacher.display_name }}（{{ teacher.login_name }}）
            </option>
          </select>
        </div>
        <button class="primary" type="submit">创建</button>
        <p v-if="teachers.length === 0" class="hint">还没有教师账号，请先在「账号管理」中创建。</p>
      </form>
    </SectionCard>

    <p v-if="notice" class="success">{{ notice }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <SectionCard title="班级列表">
      <StatePanel v-if="loading" kind="loading" title="正在读取班级" />
      <StatePanel v-else-if="listError" kind="error" title="班级列表加载失败" :description="listError" />
      <StatePanel v-else-if="classes.length === 0" title="暂无班级" description="创建班级后会显示在这里。" />
      <div v-else class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>名称</th>
            <th>任课教师</th>
            <th>状态</th>
            <th>名单</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="schoolClass in classes" :key="schoolClass.id">
            <td>{{ schoolClass.id }}</td>
            <td>{{ schoolClass.name }}</td>
            <td>
              <select :value="schoolClass.teacher_id" @change="changeTeacher(schoolClass, $event.target.value)">
                <option v-for="teacher in teachers" :key="teacher.id" :value="teacher.id">
                  {{ teacher.display_name }}
                </option>
              </select>
            </td>
            <td>
              <StatusBadge :tone="schoolClass.active ? 'success' : 'danger'">
                {{ schoolClass.active ? '有效' : '已停用' }}
              </StatusBadge>
            </td>
            <td>
              <RouterLink
                :to="{ name: 'admin-enrollments', params: { id: schoolClass.id } }"
              >
                管理名单
              </RouterLink>
            </td>
            <td>
              <button class="link" type="button" @click="toggleActive(schoolClass)">
                {{ schoolClass.active ? '停用' : '启用' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      </div>
    </SectionCard>
  </div>
</template>
