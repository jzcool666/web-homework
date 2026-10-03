<script setup>
/** 管理员首页占位：只做账号、班级与入班关系入口，不默认获得教师班级教学数据。 */
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import ConceptHero from '@/components/home/ConceptHero.vue'
import HomeInfoSections from '@/components/home/HomeInfoSections.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const greeting = computed(() => `你好，${auth.user?.display_name ?? ''}`)
</script>

<template>
  <div class="home-page">
    <PageHeader eyebrow="管理空间" :title="greeting" description="管理账号、班级和入班关系。" />
    <ConceptHero
      title="从可靠的账号与班级关系开始。"
      lead="账号与班级的维护入口集中在这里。"
      cta-label="管理账号"
      :cta-to="{ name: 'admin-users' }"
    />
    <SectionCard title="管理入口">
      <div class="quick-links">
        <RouterLink class="quick-link" :to="{ name: 'admin-users' }"><AppIcon name="people" />账号管理<AppIcon name="arrow" :size="17" /></RouterLink>
        <RouterLink class="quick-link" :to="{ name: 'admin-classes' }"><AppIcon name="layers" />班级管理<AppIcon name="arrow" :size="17" /></RouterLink>
      </div>
    </SectionCard>
    <HomeInfoSections />
  </div>
</template>

<style scoped>
.quick-links { display: grid; gap: var(--space-3); }
.quick-link { display: flex; align-items: center; gap: var(--space-3); min-height: 3.3rem; padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); text-decoration: none; font-weight: 700; }
.quick-link svg:last-child { margin-left: auto; }
</style>
