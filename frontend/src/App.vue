<script setup>
import { RouterView } from 'vue-router'

import AppShell from '@/layouts/AppShell.vue'
import AuthLayout from '@/layouts/AuthLayout.vue'
</script>

<template>
  <AuthLayout v-if="$route.meta.authLayout"><RouterView /></AuthLayout>
  <AppShell v-else><RouterView /></AppShell>
</template>
