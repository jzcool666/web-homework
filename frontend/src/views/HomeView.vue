<script setup>
import { onMounted } from 'vue'

import HealthBadge from '@/components/HealthBadge.vue'
import { useHealthStore } from '@/stores/health'

const health = useHealthStore()

onMounted(() => {
  health.load()
})
</script>

<template>
  <main class="home">
    <h1>学海通数字逻辑课程学习系统</h1>
    <p class="subtitle">设计基线 1.0 · 工程骨架（SPEC-000）</p>
    <p class="note">
      本页只用于验证前后端连通与部署同源。课堂演示、随堂测、实验等内容由后续
      Spec 交付，当前版本不含任何业务功能。
    </p>

    <section class="panel">
      <h2>后端健康检查</h2>
      <HealthBadge />
      <button type="button" :disabled="health.loading" @click="health.load()">
        重新检查
      </button>
    </section>
  </main>
</template>

<style scoped>
.home {
  max-width: 44rem;
  margin: 3rem auto;
  padding: 0 1.5rem;
  line-height: 1.7;
}

h1 {
  font-size: 1.6rem;
  margin-bottom: 0.25rem;
}

.subtitle {
  color: #5f6368;
  margin-top: 0;
}

.note {
  color: #5f6368;
  font-size: 0.9rem;
}

.panel {
  margin-top: 2rem;
  padding: 1.25rem;
  border: 1px solid #dadce0;
  border-radius: 0.5rem;
}

.panel h2 {
  font-size: 1.1rem;
  margin-top: 0;
}

button {
  margin-top: 0.75rem;
  padding: 0.4rem 0.9rem;
  border: 1px solid #1a73e8;
  border-radius: 0.25rem;
  background: #fff;
  color: #1a73e8;
  cursor: pointer;
}

button:disabled {
  opacity: 0.5;
  cursor: default;
}
</style>
