<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const displayName = ref('')
const profileError = ref(null)
const profileOk = ref(null)

const passwordForm = ref({ current_password: '', new_password: '' })
const passwordError = ref(null)

onMounted(() => {
  if (auth.user) displayName.value = auth.user.display_name
})

async function saveProfile() {
  profileError.value = null
  profileOk.value = null
  try {
    await auth.updateProfile({ version: auth.user.version, display_name: displayName.value })
    profileOk.value = '资料已更新'
  } catch (err) {
    profileError.value = err.message
  }
}

async function changePassword() {
  passwordError.value = null
  try {
    await auth.updateProfile({
      version: auth.user.version,
      current_password: passwordForm.value.current_password,
      new_password: passwordForm.value.new_password,
    })
    // 改密码会作废全部会话，必须重新登录
    router.push({ name: 'login' })
  } catch (err) {
    passwordError.value = err.message
  }
}
</script>

<template>
  <main v-if="auth.user" class="page">
    <h1>个人资料</h1>
    <p class="hint">
      <span class="badge">{{ auth.user.role }}</span>
      {{ auth.user.login_name }}
      <template v-if="auth.user.student_no">· 学号 {{ auth.user.student_no }}</template>
    </p>

    <section class="card">
      <h2>基本资料</h2>
      <form @submit.prevent="saveProfile">
        <div class="field">
          <label for="display_name">姓名</label>
          <input id="display_name" v-model="displayName" required />
        </div>
        <button class="primary" type="submit">保存</button>
        <p v-if="profileOk" class="success">{{ profileOk }}</p>
        <p v-if="profileError" class="error" role="alert">{{ profileError }}</p>
      </form>
    </section>

    <section class="card">
      <h2>修改密码</h2>
      <p class="hint">修改成功后所有会话立即失效，需要用新密码重新登录。</p>
      <form @submit.prevent="changePassword">
        <div class="field">
          <label for="current_password">当前密码</label>
          <input id="current_password" v-model="passwordForm.current_password" type="password" required />
        </div>
        <div class="field">
          <label for="new_password">新密码（10—128 个字符）</label>
          <input id="new_password" v-model="passwordForm.new_password" type="password" required />
        </div>
        <button class="primary" type="submit">修改密码</button>
        <p v-if="passwordError" class="error" role="alert">{{ passwordError }}</p>
      </form>
    </section>
  </main>
</template>
