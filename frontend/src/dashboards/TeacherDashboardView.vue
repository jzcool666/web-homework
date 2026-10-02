<script setup>
/**
 * 教师首页占位：承接现有首页内容，真实数据化重做在 Issue #49。
 * 不伪造最近备课或进行中的课堂。
 */
import { computed } from 'vue'

import ClassPanel from '@/components/home/ClassPanel.vue'
import ConceptHero from '@/components/home/ConceptHero.vue'
import HomeInfoSections from '@/components/home/HomeInfoSections.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const greeting = computed(() => `你好，${auth.user?.display_name ?? ''}`)
</script>

<template>
  <div class="home-page">
    <PageHeader eyebrow="教学空间" :title="greeting" description="围绕备课、演示与讲评组织课堂。" />
    <ConceptHero
      title="让每一次状态变化，都有清楚的讲解。"
      lead="课堂演示、题库与讲评围绕当前任教班级展开。"
      cta-label="查看个人资料"
      :cta-to="{ name: 'profile' }"
    />
    <div class="home-grid">
      <ClassPanel role="teacher" />
    </div>
    <HomeInfoSections />
  </div>
</template>
