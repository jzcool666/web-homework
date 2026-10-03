<script setup>
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'

const auth = useAuthStore()
const router = useRouter()

const form = ref({ login_name: '', student_no: '', display_name: '', password: '' })
const error = ref(null)
const submitting = ref(false)

async function submit() {
  error.value = null
  submitting.value = true
  try {
    await auth.register({ ...form.value })
    router.push({ name: 'profile' })
  } catch (err) {
    error.value = err.message
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page page--narrow">
    <PageHeader eyebrow="创建账号" title="学生注册" description="公开注册只能创建学生账号；教师与管理员由管理员分配。" />

    <SectionCard>
    <form @submit.prevent="submit">
      <div class="field">
        <label for="login_name">登录名（4—32 位字母、数字或下划线）</label>
        <input id="login_name" v-model="form.login_name" autocomplete="username" required />
      </div>
      <div class="field">
        <label for="student_no">学号（6—20 位数字）</label>
        <input id="student_no" v-model="form.student_no" inputmode="numeric" required />
      </div>
      <div class="field">
        <label for="display_name">姓名</label>
        <input id="display_name" v-model="form.display_name" required />
      </div>
      <div class="field">
        <label for="password">密码（10—128 个字符）</label>
        <input
          id="password"
          v-model="form.password"
          type="password"
          autocomplete="new-password"
          required
        />
      </div>
      <button class="primary" type="submit" :disabled="submitting">注册并登录</button>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p class="hint">已有账号？<RouterLink :to="{ name: 'login' }">直接登录</RouterLink></p>
    </form>
    </SectionCard>
  </div>
</template>
