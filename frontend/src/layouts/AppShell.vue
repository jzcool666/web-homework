<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import AppIcon from '@/components/ui/AppIcon.vue'
import QuickSearch from '@/components/ui/QuickSearch.vue'
import { groupedNavigationFor, navigationFor, roleLabels } from '@/navigation'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const drawerOpen = ref(false)
const sidebar = ref(null)
const menuButton = ref(null)
const items = computed(() => navigationFor(auth.user?.role))
const groups = computed(() => groupedNavigationFor(auth.user?.role))
const roleLabel = computed(() => roleLabels[auth.user?.role] ?? '课程空间')
const pageLabel = computed(() => {
  if (route.name === 'profile') return '个人资料'
  return items.value.find((item) => item.route === route.name || item.activeRoutes?.includes(route.name))?.label ?? '学习首页'
})

function isActive(item) {
  return item.route === route.name || item.activeRoutes?.includes(route.name)
}

watch(() => route.fullPath, () => { drawerOpen.value = false })
watch(drawerOpen, async open => {
  await nextTick()
  if (open) sidebar.value?.querySelector('a.nav-item')?.focus()
  else menuButton.value?.focus()
})
function drawerKey(event) {
  if (!drawerOpen.value) return
  if (event.key === 'Escape') { event.preventDefault(); drawerOpen.value = false }
  if (event.key !== 'Tab') return
  const links = [...sidebar.value.querySelectorAll('a.nav-item')]
  const first = links[0], last = links[links.length - 1]
  if (event.shiftKey && event.target === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && event.target === last) { event.preventDefault(); first?.focus() }
}

async function signOut() {
  try {
    await auth.logout()
  } finally {
    drawerOpen.value = false
    await router.push({ name: 'home' })
  }
}
</script>

<template>
  <div class="app-shell" :class="{ 'app-shell--guest': !auth.user }">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <header class="topbar">
      <div class="topbar__start">
        <button v-if="auth.user" ref="menuButton" class="icon-button topbar__menu" type="button" aria-label="打开导航" :aria-expanded="drawerOpen" aria-controls="app-sidebar" @click="drawerOpen = !drawerOpen">
          <AppIcon :name="drawerOpen ? 'close' : 'menu'" />
        </button>
        <RouterLink class="brand" :to="{ name: 'home' }" aria-label="学海通首页">
          <span class="brand__mark"><AppIcon name="book" :size="25" /></span>
          <span class="brand__name">学海通<span class="brand__divider">·</span><small>数字逻辑课程学习系统</small></span>
        </RouterLink>
      </div>
      <div class="topbar__end">
        <template v-if="auth.user">
          <QuickSearch />
          <span class="topbar__context">{{ roleLabel }} / {{ pageLabel }}</span>
          <RouterLink class="user-link" :to="{ name: 'profile' }">
            <span class="user-avatar">{{ auth.user.display_name?.slice(0, 1) || '用' }}</span>
            <span class="user-link__name">{{ auth.user.display_name }}</span>
          </RouterLink>
          <button class="text-button topbar__logout" type="button" @click="signOut">退出</button>
        </template>
        <template v-else>
          <RouterLink class="text-button" :to="{ name: 'login' }">登录</RouterLink>
          <RouterLink class="button button--primary" :to="{ name: 'register' }">学生注册</RouterLink>
        </template>
      </div>
    </header>

    <button v-if="auth.user && drawerOpen" class="sidebar-backdrop" type="button" aria-label="关闭导航" @click="drawerOpen = false"></button>
    <aside v-if="auth.user" id="app-sidebar" ref="sidebar" class="sidebar" :class="{ 'sidebar--open': drawerOpen }" aria-label="主导航" @keydown="drawerKey">
      <div class="sidebar__heading">{{ roleLabel }}</div>
      <nav class="sidebar__nav" aria-label="角色导航">
        <div v-for="(group, index) in groups" :key="group.label ?? `group-${index}`" class="nav-group">
          <div v-if="group.label" class="nav-group__label">{{ group.label }}</div>
          <template v-for="item in group.items" :key="item.label">
            <RouterLink
              v-if="item.route"
              class="nav-item"
              :class="{ 'nav-item--active': isActive(item) }"
              :to="{ name: item.route }"
              :aria-current="isActive(item) ? 'page' : undefined"
            >
              <AppIcon :name="item.icon" />
              <span>{{ item.label }}</span>
            </RouterLink>
            <span v-else class="nav-item nav-item--planned" :title="`${item.planned} 尚未实现`" aria-disabled="true">
              <AppIcon :name="item.icon" />
              <span>{{ item.label }}</span>
              <small>待开放</small>
            </span>
          </template>
        </div>
      </nav>
      <div class="sidebar__footer">
        <span class="sidebar__signal" aria-hidden="true"></span>
        时序逻辑 · 从每一拍开始
      </div>
    </aside>

    <main id="main-content" class="main-content" tabindex="-1">
      <div class="main-content__inner"><slot /></div>
    </main>
  </div>
</template>
