<script setup>
import { onMounted, ref } from 'vue'

import { api } from '@/api/client'

const users = ref([])
const error = ref(null)
const notice = ref(null)
const form = ref({ login_name: '', display_name: '', student_no: '', password: '', role: 'teacher' })

async function load() {
  error.value = null
  try {
    const data = await api.get('/users?page_size=100')
    users.value = data
  } catch (err) {
    error.value = err.message
  }
}

async function createUser() {
  error.value = null
  notice.value = null
  const payload = {
    login_name: form.value.login_name,
    display_name: form.value.display_name,
    password: form.value.password,
    role: form.value.role,
  }
  if (form.value.role === 'student') payload.student_no = form.value.student_no
  try {
    await api.post('/users', payload)
    notice.value = `已创建 ${payload.login_name}`
    form.value = { login_name: '', display_name: '', student_no: '', password: '', role: 'teacher' }
    await load()
  } catch (err) {
    error.value = err.message
  }
}

async function changeRole(user, role) {
  error.value = null
  try {
    await api.patch(`/users/${user.id}`, { version: user.version, role })
    await load()
  } catch (err) {
    error.value = err.message
    await load()
  }
}

async function toggleActive(user) {
  error.value = null
  try {
    await api.patch(`/users/${user.id}`, { version: user.version, active: !user.active })
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
    <h1>账号管理</h1>
    <p class="hint">管理员创建教师与学生账号，并可停用或调整角色。最后一名有效管理员不能被停用或降级。</p>

    <section class="card">
      <h2>新建账号</h2>
      <form @submit.prevent="createUser">
        <div class="field">
          <label for="new_login_name">登录名</label>
          <input id="new_login_name" v-model="form.login_name" required />
        </div>
        <div class="field">
          <label for="new_display_name">姓名</label>
          <input id="new_display_name" v-model="form.display_name" required />
        </div>
        <div class="field">
          <label for="new_role">角色</label>
          <select id="new_role" v-model="form.role">
            <option value="teacher">教师</option>
            <option value="student">学生</option>
            <option value="admin">管理员</option>
          </select>
        </div>
        <div v-if="form.role === 'student'" class="field">
          <label for="new_student_no">学号（6—20 位数字）</label>
          <input id="new_student_no" v-model="form.student_no" required />
        </div>
        <div class="field">
          <label for="new_password">初始密码（10—128 个字符）</label>
          <input id="new_password" v-model="form.password" type="password" required />
        </div>
        <button class="primary" type="submit">创建</button>
      </form>
    </section>

    <p v-if="notice" class="success">{{ notice }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <section class="card">
      <h2>账号列表</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>登录名</th>
            <th>姓名</th>
            <th>角色</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td>{{ user.id }}</td>
            <td>{{ user.login_name }}</td>
            <td>{{ user.display_name }}</td>
            <td>
              <select :value="user.role" @change="changeRole(user, $event.target.value)">
                <option value="student">学生</option>
                <option value="teacher">教师</option>
                <option value="admin">管理员</option>
              </select>
            </td>
            <td>
              <span class="badge" :class="{ off: !user.active }">
                {{ user.active ? '有效' : '已停用' }}
              </span>
            </td>
            <td>
              <button class="link" type="button" @click="toggleActive(user)">
                {{ user.active ? '停用' : '启用' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>
