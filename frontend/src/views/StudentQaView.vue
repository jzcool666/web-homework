<script setup>
/**
 * 学生课程检索问答（SPEC-007 E061）。
 *
 * 只展示服务器返回的匹配片段与来源：语料是已发布的课程知识点与问答条目，
 * 这里不生成任何未核实的答案，也不把相似度说成正确率。
 * 没有可靠匹配时给出章节浏览入口，而不是编造解释。
 */
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'

import AppIcon from '@/components/ui/AppIcon.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { api } from '@/api/client'
import { formatSimilarity, matchSummary, sourceLabel } from '@/utils/qa'

const query = ref('')
const result = ref(null)
const error = ref(null)
const searching = ref(false)
const asked = ref('')

const matches = computed(() => result.value?.matches ?? [])
const tooShort = computed(() => query.value.trim().length < 2)

async function ask() {
  const text = query.value.trim()
  if (text.length < 2) {
    error.value = '请输入至少 2 个字符的问题'
    return
  }
  searching.value = true
  error.value = null
  try {
    result.value = await api.post('/qa/queries', { query: text })
    asked.value = text
  } catch (err) {
    result.value = null
    error.value = err.message
  } finally {
    searching.value = false
  }
}
</script>

<template>
  <div class="qa-page">
    <PageHeader icon="spark" :steps="['描述课程问题', '查看匹配', '核对知识来源']"
      eyebrow="学习空间"
      title="课程问答"
      description="在已发布的课程知识与问答语料中检索相近内容，返回来源摘要。它只做文本匹配，不生成未核实的答案。"
    />

    <SectionCard title="提问">
      <form class="ask" @submit.prevent="ask">
        <label class="sr-only" for="qa_query">问题</label>
        <input
          id="qa_query"
          v-model="query"
          maxlength="200"
          placeholder="例如：模 6 计数器数到 5 之后是什么？"
        />
        <button class="button button--primary" type="submit" :disabled="searching || tooShort">
          <AppIcon name="spark" :size="17" /> {{ searching ? '检索中…' : '检索' }}
        </button>
      </form>
      <p class="hint">查询 2—200 个字符；同一用户每分钟最多 20 次。</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </SectionCard>

    <SectionCard v-if="result" :title="`检索结果：${matchSummary(result.matched, matches.length)}`">
      <p class="meta">
        <StatusBadge :tone="result.matched ? 'success' : 'neutral'">
          {{ result.matched ? '有匹配' : '未匹配' }}
        </StatusBadge>
        <span class="hint">语料版本 {{ result.corpus_version }}</span>
      </p>
      <p class="hint">「{{ asked }}」</p>

      <StatePanel
        v-if="!result.matched"
        title="没有可靠匹配"
        description="课程语料里没有足够接近的内容。可以换个说法再试，或直接按章节浏览课程材料。"
      >
        <RouterLink class="button button--secondary" :to="{ name: 'student-learning' }">
          按章节浏览课程
        </RouterLink>
      </StatePanel>

      <ol v-else class="matches">
        <li v-for="match in matches" :key="match.knowledge_id">
          <div class="match-head">
            <RouterLink
              class="match-title"
              :to="{ name: 'student-knowledge', params: { id: match.knowledge_id } }"
            >
              {{ match.title }}
            </RouterLink>
            <span class="similarity">
              文本相似度 {{ formatSimilarity(match.similarity) }}
            </span>
          </div>
          <p class="excerpt">{{ match.excerpt }}</p>
          <p class="source">
            <a
              v-if="match.source_url"
              :href="match.source_url"
              target="_blank"
              rel="noopener noreferrer"
            >来源：{{ sourceLabel(match.source_url) }}</a>
            <span v-else>来源：课程知识点「{{ match.title }}」</span>
          </p>
        </li>
      </ol>

      <p v-if="result.matched" class="hint">
        相似度表示文本相近程度，<strong>不是</strong>答对的概率；请以课程材料为准。
      </p>
    </SectionCard>
  </div>
</template>

<style scoped>
.qa-page { width: 100%; }
.qa-page .section-card { margin-bottom: var(--space-4); }
.ask { display: flex; gap: var(--space-3); flex-wrap: wrap; }
.ask input { flex: 1 1 20rem; padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); font: inherit; }
.meta { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; margin-bottom: var(--space-2); }
.matches { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--space-3); }
.matches li { padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); }
.match-head { display: flex; align-items: baseline; gap: var(--space-3); flex-wrap: wrap; }
.match-title { font-weight: 700; color: var(--color-primary); text-decoration: none; }
.similarity { font-family: var(--font-mono); font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.excerpt { margin: var(--space-2) 0; font-size: var(--font-size-sm); line-height: 1.7; }
.source { margin: 0; font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.source a { color: var(--color-primary); }
.hint { color: var(--color-text-secondary); font-size: var(--font-size-sm); }
.error { color: var(--color-danger); }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
</style>
