<script setup>
/**
 * 学生「复习推荐」（SPEC-015 E065，只读）。
 *
 * 服务器用**本人**的错题、学习进度与实验表现排序并给出理由；页面只负责展示，
 * 不参与打分。两点必须在界面上说清楚：
 * - `score` 为 null 表示这条是基础路径、没有个性化信号，不等于 0 分；
 * - 推荐不含题目答案，正在测评且尚未公开反馈的题不会出现。
 * 推荐只给本人看，教师端没有入口（E065 的角色是 S）。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import {
  DEFAULT_LIMIT,
  KIND_TONE,
  kindLabel,
  linkLabel,
  itemLink,
  normalizeLimit,
  reasonsOf,
  scoreLabel,
  scoreTone,
  summarize,
} from '@/utils/recommendations'

const LIMIT_OPTIONS = [1, 3, 5, 10]

const data = ref(null)
const limit = ref(DEFAULT_LIMIT)
const loading = ref(false)
const error = ref(null)

const items = computed(() => data.value?.items ?? [])
const stats = computed(() => summarize(items.value))

async function load() {
  const value = normalizeLimit(limit.value)
  if (value === null) {
    error.value = '条数只能选 1—10'
    return
  }
  loading.value = true
  error.value = null
  try {
    data.value = await api.get(`/me/recommendations?limit=${value}`)
  } catch (err) {
    data.value = null
    error.value = err.message
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <PageHeader
      eyebrow="学习"
      title="复习推荐"
      description="按你自己的错题、学习进度与实验表现排序，每条都说明为什么推荐。推荐只基于你本人的记录，教师端没有这个入口；不含题目答案。"
    />

    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <SectionCard title="推荐条数">
      <div class="controls">
        <div class="field">
          <label for="r_limit">最多显示</label>
          <select id="r_limit" v-model.number="limit">
            <option v-for="value in LIMIT_OPTIONS" :key="value" :value="value">
              {{ value }} 条
            </option>
          </select>
        </div>
        <button class="primary" type="button" :disabled="loading" @click="load">
          {{ loading ? '读取中…' : '重新获取' }}
        </button>
      </div>
      <p v-if="data" class="hint">
        共 {{ stats.total }} 条：个性化 {{ stats.personalized }} 条、基础路径 {{ stats.basePath }} 条。
        候选不足时不会重复凑数。
      </p>
      <p v-if="data" class="hint">
        算法版本 {{ data.algorithm_version }}。
      </p>
    </SectionCard>

    <SectionCard title="推荐清单">
      <StatePanel v-if="loading" kind="loading" title="正在计算推荐" />
      <StatePanel
        v-else-if="data && items.length === 0"
        title="暂时没有可推荐的内容"
        description="课程还没有已发布的知识点，或本班测评尚未公开反馈。"
      />
      <StatePanel
        v-else-if="!data"
        title="尚未获取推荐"
        description="点击上方「重新获取」开始。"
      />
      <ol v-else class="recommendations">
        <li v-for="item in items" :key="`${item.kind}-${item.resource_id}`" class="card">
          <div class="card__head">
            <StatusBadge :tone="KIND_TONE[item.kind] ?? 'neutral'">
              {{ kindLabel(item.kind) }}
            </StatusBadge>
            <span class="card__title">{{ item.title }}</span>
            <StatusBadge :tone="scoreTone(item.score)">{{ scoreLabel(item.score) }}</StatusBadge>
          </div>
          <ul class="card__reasons">
            <li v-for="reason in reasonsOf(item)" :key="reason">{{ reason }}</li>
          </ul>
          <p class="card__meta">
            知识点 #{{ item.knowledge_id }}
            <RouterLink :to="itemLink(item)">{{ linkLabel(item) }}</RouterLink>
          </p>
        </li>
      </ol>
      <p v-if="data && items.length > 0" class="hint">
        正在测评且尚未公开反馈的题目不会进入推荐，避免提前看到对错；推荐也不返回题目答案。
      </p>
    </SectionCard>
  </div>
</template>

<style scoped>
.controls {
  display: flex;
  align-items: end;
  gap: var(--space-4);
}

.recommendations {
  margin: 0;
  padding-left: 1.2rem;
  display: grid;
  gap: var(--space-3);
}

.card {
  border: 1px solid var(--color-border, #d8dbe0);
  border-radius: var(--radius-md, 8px);
  padding: var(--space-3);
}

.card__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.card__title {
  font-weight: 600;
  flex: 1 1 12rem;
}

.card__reasons {
  margin: var(--space-2) 0 0;
  padding-left: 1.2rem;
  font-size: var(--font-size-sm);
}

.card__meta {
  margin: var(--space-2) 0 0;
  font-size: var(--font-size-xs);
  color: var(--color-text-muted, #5a6270);
}
</style>
