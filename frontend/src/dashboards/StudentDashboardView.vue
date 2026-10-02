<script setup>
/**
 * 学生首页占位：承接现有首页内容，真实数据化重做在 Issue #49。
 * 这里只做角色分发与 Hero 压缩，不新增任何统计区块。
 */
import { computed } from 'vue'

import ClassPanel from '@/components/home/ClassPanel.vue'
import ConceptHero from '@/components/home/ConceptHero.vue'
import HomeInfoSections from '@/components/home/HomeInfoSections.vue'
import StudentPreviewTodo from '@/components/StudentPreviewTodo.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const greeting = computed(() => `你好，${auth.user?.display_name ?? ''}`)
</script>

<template>
  <div class="home-page">
    <PageHeader eyebrow="学习空间" :title="greeting" description="从当前课堂出发，逐步理解时序逻辑。" />
    <ConceptHero
      title="从触发器开始，理解时序的节奏。"
      lead="课程内容围绕 D / JK 触发器、计数器、寄存器与状态转换展开。"
      cta-label="查看个人资料"
      :cta-to="{ name: 'profile' }"
    />
    <div class="home-grid">
      <ClassPanel role="student" />
      <StudentPreviewTodo />
    </div>
    <HomeInfoSections />
  </div>
</template>
