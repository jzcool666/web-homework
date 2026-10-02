<script setup>
/** 未登录访客的首页：只介绍已开放内容，不展示任何用户数据。 */
import ConceptHero from '@/components/home/ConceptHero.vue'
import ClassPanel from '@/components/home/ClassPanel.vue'
import HomeInfoSections from '@/components/home/HomeInfoSections.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
</script>

<template>
  <div class="home-page">
    <PageHeader eyebrow="学海通" title="把时序逻辑学清楚" description="面向教师课堂的数字逻辑学习系统。当前开放课程学习、课堂演示、习题训练与考勤。" />
    <ConceptHero
      title="从触发器开始，理解时序的节奏。"
      lead="课程内容围绕 D / JK 触发器、计数器、寄存器与状态转换展开。"
      cta-label="登录学习空间"
      :cta-to="{ name: 'login' }"
    />
    <ClassPanel guest />
    <HomeInfoSections />
  </div>
</template>
