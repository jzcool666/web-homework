<script setup>
import { RouterLink } from 'vue-router'
defineProps({ item: { type: Object, default: null } })
</script>
<template>
  <div class="review-spotlight">
    <svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="32" fill="#eaf0ff"/><path d="M32 11v6" stroke="#4269df" stroke-width="3"/><circle cx="32" cy="9" r="3" fill="#789afa"/><rect x="12" y="18" width="40" height="30" rx="13" fill="#c6d8ff"/><rect x="17" y="22" width="30" height="21" rx="9" fill="#f9fbff"/><circle cx="25" cy="31" r="3" fill="#4269df"/><circle cx="39" cy="31" r="3" fill="#4269df"/><path d="M26 38q6 4 12 0" fill="none" stroke="#4269df" stroke-width="2"/><path d="M20 49h24l5 9H15z" fill="#adc6fc"/></svg>
    <div><h3>{{ item ? `建议复习 ${item.title}` : '从一个知识点开始学习' }}</h3>
      <p>{{ item ? (item.reasons ?? []).join('；') || '按课程先修顺序巩固本节内容。' : '先阅读概念，再用习题和逐拍实验验证自己的理解。' }}</p>
      <RouterLink class="button button--secondary" :to="item ? item.kind === 'knowledge' ? { name: 'student-knowledge', params: { id: item.knowledge_id } } : { name: 'student-practice', query: { knowledge_id: item.knowledge_id } } : { name: 'student-learning' }">{{ item ? '开始复习' : '浏览课程' }} →</RouterLink>
    </div>
  </div>
</template>
<style scoped>
.review-spotlight { display: flex; gap: 12px; padding: 14px; border-radius: 9px; background: linear-gradient(120deg, #f1f5ff, #fafcff); align-items: flex-start; }
.review-spotlight > div { min-width: 0; overflow-wrap: anywhere; }
svg { width: 48px; height: 48px; flex: none; } h3 { font-size: 13px; line-height: 1.5; margin: 0 0 7px; } p { font-size: 11px; line-height: 1.8; color: var(--color-text-secondary); margin: 0 0 12px; }
.button { font-size: 11px; min-height: 29px; padding: 5px 10px; }
</style>
