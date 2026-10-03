<script setup>
import { RouterView } from 'vue-router'

import AppShell from '@/layouts/AppShell.vue'
import AuthLayout from '@/layouts/AuthLayout.vue'
import PresentationLayout from '@/layouts/PresentationLayout.vue'
</script>

<template>
  <AuthLayout v-if="$route.meta.authLayout"><RouterView /></AuthLayout>
  <PresentationLayout v-else-if="$route.meta.presentationLayout"><RouterView /></PresentationLayout>
  <AppShell v-else><RouterView /></AppShell>
</template>
