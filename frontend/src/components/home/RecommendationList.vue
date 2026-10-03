<script setup>
import { RouterLink } from 'vue-router'
defineProps({ items: { type: Array, default: () => [] } })
</script>
<template>
  <p v-if="!items.length" class="hint">暂无推荐，先到课程中选择知识点学习。</p>
  <ul v-else class="overview-list">
    <li v-for="item in items" :key="`${item.kind}-${item.resource_id}`">
      <div>
        <strong>{{ item.title }}</strong
        ><small
          >{{
            item.score === null ? '基础路径' : `推荐优先级 ${item.score} / 100`
          }}
          · {{ (item.reasons ?? []).join('；') }}</small
        >
      </div>
      <RouterLink
        class="button button--secondary"
        :to="
          item.kind === 'knowledge'
            ? { name: 'student-knowledge', params: { id: item.knowledge_id } }
            : {
                name: 'student-practice',
                query: { knowledge_id: item.knowledge_id },
              }
        "
        >{{ item.kind === 'knowledge' ? '学习' : '练习' }}</RouterLink
      >
    </li>
  </ul>
</template>
