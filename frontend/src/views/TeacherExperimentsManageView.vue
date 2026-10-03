<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, resetCsrfToken } from '@/api/client'
import { readAll } from '@/api/pagination'
import { useAuthStore } from '@/stores/auth'
import ExperimentSequenceEditor from '@/components/experiment/ExperimentSequenceEditor.vue'
import CircuitPreview from '@/components/home/CircuitPreview.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { modelLabel, formatBits } from '@/utils/demo'
import { experimentDraft, experimentPayload, newExperimentDraft } from '@/utils/experimentDraft'
import { renderMarkdown } from '@/utils/markdown'

const auth = useAuthStore()
const experiments = ref([]), knowledge = ref([]), state = ref('loading'), loadError = ref('')
const selected = ref(null), form = ref(newExperimentDraft()), published = ref(false)
const search = ref(''), scope = ref('all'), error = ref(''), notice = ref(''), fields = ref({})
const saving = ref(false), loadingDetail = ref(false), conflict = ref(false)
const snapshot = ref(JSON.stringify(form.value)), titleInput = ref(null)
const isNew = computed(() => selected.value === null)
const readonly = computed(() => selected.value !== null && selected.value.owner_id !== auth.user?.id)
const locked = computed(() => saving.value || loadingDetail.value || readonly.value)
const dirty = computed(() => JSON.stringify(form.value) !== snapshot.value)
const ownCount = computed(() => experiments.value.filter(row => row.owner_id === auth.user?.id).length)
const filtered = computed(() => experiments.value.filter(row => (!search.value || row.title.toLowerCase().includes(search.value.trim().toLowerCase())) && (scope.value !== 'mine' || row.owner_id === auth.user?.id)))
const knowledgeLabel = id => knowledge.value.find(row => row.id === id)?.title ?? `知识点 #${id}`
const currentKnowledgeVisible = computed(() => knowledge.value.some(row => row.id === Number(form.value.knowledge_id)))

function confirmDiscard() { return !dirty.value || window.confirm('有未保存的修改。继续会放弃这些修改，确定继续吗？') }
function fill(row) {
  selected.value = row; form.value = experimentDraft(row); published.value = row.published
  snapshot.value = JSON.stringify(form.value); conflict.value = false; fields.value = {}
}
function startNew() {
  if (saving.value || loadingDetail.value || !confirmDiscard()) return
  selected.value = null; form.value = newExperimentDraft(knowledge.value[0]?.id ?? '')
  published.value = false; snapshot.value = JSON.stringify(form.value); conflict.value = false
  error.value = ''; notice.value = ''; fields.value = {}
  nextTick(() => titleInput.value?.focus())
}
async function selectExperiment(row) {
  if (saving.value || loadingDetail.value || !confirmDiscard()) return
  loadingDetail.value = true; error.value = ''; notice.value = ''
  try { fill(await api.get(`/experiments/${row.id}`)) }
  catch (err) { error.value = err.message }
  finally { loadingDetail.value = false }
}
async function load() {
  state.value = 'loading'; loadError.value = ''
  try {
    const [list, points] = await Promise.all([readAll('/experiments'), readAll('/knowledge-points')])
    experiments.value = list; knowledge.value = points
    if (list.length) await selectExperiment(list.find(row => row.owner_id === auth.user?.id) ?? list[0])
    else startNew()
    state.value = 'ready'
  } catch (err) { loadError.value = err.message; state.value = 'error' }
}
function changeType(type) {
  if (locked.value || form.value.input_sequence.length) return
  form.value.simulator_type = type
  if (['d', 'jk'].includes(type) && Number(form.value.initial_q) > 1) form.value.initial_q = 0
}
async function save(publish) {
  if (locked.value || conflict.value) return
  error.value = ''; notice.value = ''; fields.value = {}
  let payload
  try { payload = experimentPayload(form.value, publish) }
  catch (err) { error.value = err.message; fields.value = err.fields ?? {}; return }
  saving.value = true
  try {
    const row = isNew.value ? await api.post('/experiments', payload) : await api.patch(`/experiments/${selected.value.id}`, { version: selected.value.version, ...payload })
    experiments.value = [row, ...experiments.value.filter(item => item.id !== row.id)]
    fill(row)
    notice.value = row.published ? '实验已发布，学生可在实验中心查看。' : '草稿已保存，学生不可见。'
  } catch (err) {
    error.value = err.message; fields.value = err.details?.fields ?? {}
    if (err.code === 'CSRF_FAILED') {
      resetCsrfToken()
      error.value = '登录状态校验已更新，未保存内容已保留，请再次保存。'
    }
    if (err.status === 409) conflict.value = true
  } finally { saving.value = false }
}
async function reloadSelected() {
  if (!selected.value || !confirmDiscard()) return
  // The user explicitly replaces the draft; never advance its version silently.
  loadingDetail.value = true
  try { fill(await api.get(`/experiments/${selected.value.id}`)); error.value = ''; notice.value = '已载入服务器最新版本。' }
  catch (err) { error.value = err.message }
  finally { loadingDetail.value = false }
}
onMounted(load)
</script>

<template>
  <div class="experiment-management">
    <PageHeader icon="flask" eyebrow="教师空间" title="实验管理" description="准备实验说明与输入流程，发布后供学生逐拍预测，也可用于课堂演示。">
      <template #actions><RouterLink class="button button--secondary" :to="{ name: 'teacher-classroom' }"><AppIcon name="clock" :size="16" /> 前往课堂</RouterLink><button class="button button--primary" type="button" :disabled="state !== 'ready' || saving || loadingDetail" @click="startNew"><AppIcon name="flask" :size="16" /> 新建实验</button></template>
    </PageHeader>
    <StatePanel v-if="state === 'loading'" kind="loading" title="正在读取实验与知识点" />
    <div v-else-if="state === 'error'"><StatePanel kind="error" title="实验列表无法读取" :description="loadError" /><button type="button" class="button button--secondary" @click="load">重新读取</button></div>
    <template v-else>
      <div class="management-layout">
        <aside class="experiment-library">
          <div class="library-heading"><h2>实验库</h2><span>可见 {{ experiments.length }} · 本人 {{ ownCount }}</span></div>
          <label class="library-search"><AppIcon name="search" :size="16" /><input v-model="search" aria-label="搜索实验标题" placeholder="搜索实验标题" /></label>
          <div class="scope-tabs"><button type="button" :aria-pressed="scope === 'all'" @click="scope='all'">全部可见</button><button type="button" :aria-pressed="scope === 'mine'" @click="scope='mine'">我的实验</button></div>
          <p v-if="!filtered.length" class="library-empty">{{ experiments.length ? '没有匹配的实验。' : '暂无实验，创建你的第一个实验。' }}</p>
          <div v-else class="experiment-list">
            <button v-for="row in filtered" :key="row.id" type="button" class="experiment-item" :class="{ 'experiment-item--selected': selected?.id === row.id }" :aria-pressed="selected?.id === row.id" :disabled="saving || loadingDetail" @click="selectExperiment(row)">
              <div class="item-heading"><span>{{ modelLabel(row.simulator_type) }}</span><StatusBadge :tone="row.published ? 'success' : 'neutral'">{{ row.published ? '已发布' : '草稿' }}</StatusBadge></div>
              <strong>{{ row.title }}</strong><small>{{ knowledgeLabel(row.knowledge_id) }}</small>
              <div class="item-meta"><span>{{ row.owner_id === auth.user?.id ? '本人创建' : '其他教师 · 只读' }}</span><span>v{{ row.version }} · {{ row.checkpoints?.length ?? 0 }} 拍</span></div>
            </button>
          </div>
        </aside>

        <section class="experiment-form-panel" aria-label="实验编辑区">
          <header class="editor-heading"><div><span class="editor-kicker">{{ readonly ? '查看实验' : isNew ? '准备一份新实验' : '编辑实验' }}</span><h2>{{ selected?.title || '从一个清楚的实验目标开始' }}</h2><p>{{ isNew ? '填写说明，排好输入和时钟，先保存草稿或直接发布。' : `当前版本 v${selected.version} · ${published ? '学生可见' : '仅本人可见'}` }}</p></div><span class="editor-model">{{ modelLabel(form.simulator_type) }}</span></header>
          <p v-if="readonly" class="readonly-note">这是其他教师的已发布实验，可以查看内容；只有创建者可以修改。</p>
          <p v-if="loadingDetail" class="editor-notice" role="status">正在读取实验详情…</p>
          <p v-if="notice" class="editor-notice editor-notice--success" role="status">{{ notice }}</p>
          <div v-if="error" class="editor-error" role="alert"><strong>{{ error }}</strong><ul v-if="Object.keys(fields).length"><li v-for="(message,field) in fields" :key="field">{{ message }}</li></ul><p v-if="conflict">未保存内容已保留。重新载入最新版本会替换当前编辑内容。</p><button v-if="conflict" class="button button--secondary" type="button" :disabled="loadingDetail" @click="reloadSelected">重新载入最新版本</button></div>
          <form @submit.prevent="save(published)">
            <fieldset :disabled="locked" class="editor-fields">
              <div class="form-grid"><div class="field"><label for="experiment-title">实验标题</label><input id="experiment-title" ref="titleInput" v-model="form.title" maxlength="100" required placeholder="例如：模6计数器的回零与暂停" :aria-invalid="Boolean(fields.title)" /></div><div class="field"><label for="experiment-knowledge">关联知识点</label><select id="experiment-knowledge" v-model="form.knowledge_id" required :aria-invalid="Boolean(fields.knowledge_id)"><option disabled value="">请选择知识点</option><option v-if="form.knowledge_id && !currentKnowledgeVisible" :value="form.knowledge_id">知识点 #{{ form.knowledge_id }}（当前不可见）</option><option v-for="point in knowledge" :key="point.id" :value="point.id">{{ point.title }}</option></select></div></div>
              <p v-if="!knowledge.length" class="field-hint">暂时没有可选择的知识点，请先在课程内容中准备知识点。</p>
              <div class="configuration-card"><div class="configuration-fields"><div class="field"><label for="experiment-type">实验模型</label><select id="experiment-type" :value="form.simulator_type" :disabled="locked || form.input_sequence.length > 0" @change="changeType($event.target.value)"><option v-for="type in ['d','jk','counter','shift']" :key="type" :value="type">{{ modelLabel(type) }}</option></select><small v-if="form.input_sequence.length">更换模型前，先移除原输入序列。</small></div><div class="configuration-values"><div class="field"><label for="experiment-initial">初态 Q</label><input id="experiment-initial" v-model.number="form.initial_q" type="number" :min="0" :max="['d','jk'].includes(form.simulator_type) ? 1 : 15" step="1" required /><small v-if="Number.isInteger(form.initial_q)">二进制 {{ formatBits(form.initial_q,form.simulator_type) }}</small></div><div v-if="form.simulator_type === 'counter'" class="field"><label for="experiment-modulus">模数 M</label><input id="experiment-modulus" v-model.number="form.modulus" type="number" min="2" max="16" step="1" required /><small>取值2—16，允许设置无效初态作教学分析。</small></div></div></div><CircuitPreview :kind="form.simulator_type" /></div>
              <div class="field steps-field"><label for="experiment-steps">实验说明与步骤 <small>{{ form.steps_md.length }} / 10000</small></label><textarea id="experiment-steps" v-model="form.steps_md" rows="5" maxlength="10000" required placeholder="写清实验目的、操作步骤和需要观察的问题，可使用Markdown。" /></div>
              <details v-if="form.steps_md" class="steps-preview"><summary>预览实验说明</summary><div class="markdown-body" v-html="renderMarkdown(form.steps_md)" /></details>
              <ExperimentSequenceEditor v-model="form.input_sequence" :simulator-type="form.simulator_type" :disabled="locked" />
            </fieldset>
            <footer v-if="!readonly" class="editor-footer"><p>{{ dirty ? '有未保存的修改' : '内容与当前已保存版本一致' }}<small>发布后学生可见；已开始的课堂演示与历史提交保留原快照。</small></p><div><button type="button" class="button button--secondary" :disabled="locked || conflict" @click="save(false)">{{ published ? '撤回为草稿' : '保存草稿' }}</button><button type="button" class="button button--primary" :disabled="locked || conflict" @click="save(true)">{{ saving ? '正在保存…' : published ? '保存已发布实验' : '发布实验' }}</button></div></footer>
          </form>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.management-layout { display: grid; grid-template-columns: 270px minmax(0,1fr); gap: 22px; align-items: start; }.experiment-library { min-width: 0; padding: 18px; border: 1px solid var(--color-border); background: white; border-radius: 16px; }.library-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 15px; }.library-heading h2 { font-size: .93rem; color: #456184; margin: 0; }.library-heading>span { color: #91a2b9; font-size: .66rem; }.library-search { display: flex; align-items: center; gap: 8px; background: #f5f8fe; border: 1px solid #e6edf9; border-radius: 9px; padding: 8px 10px; color: #94a7c2; }.library-search input { width: 100%; min-width: 0; border: 0; background: none; padding: 0; font-size: .75rem; color: #58759e; }.scope-tabs { display: flex; gap: 6px; margin: 13px 0; }.scope-tabs button { padding: 5px 8px; font-size: .68rem; border: 0; border-radius: 6px; color: #96a6bd; background: #f7f9fd; }.scope-tabs button[aria-pressed=true] { color: #4f78d9; background: #edf3ff; }.library-empty { color: #98a6bb; font-size: .78rem; line-height: 1.8; padding: 16px 0; }.experiment-list { display: grid; gap: 11px; max-height: 700px; overflow-y: auto; }.experiment-item { text-align: left; background: white; border: 1px solid #e3ebf8; border-radius: 11px; padding: 13px; min-width: 0; }.experiment-item--selected { border-color: #91abe9; background: #f3f7ff; }.item-heading { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; }.item-heading>span { color: #859cbc; font-size: .65rem; }.experiment-item strong { display: block; color: #4b678e; font-size: .79rem; line-height: 1.6; overflow-wrap: anywhere; }.experiment-item>small { display: block; font-size: .66rem; color: #a1b0c5; margin-top: 6px; }.item-meta { display: flex; justify-content: space-between; gap: 7px; margin-top: 13px; padding-top: 9px; border-top: 1px solid #e4ecf8; font-size: .6rem; color: #9dacc2; }.experiment-form-panel { min-width: 0; border: 1px solid var(--color-border); background: white; border-radius: 18px; overflow: hidden; }.editor-heading { padding: 22px; display: flex; justify-content: space-between; gap: 12px; background: linear-gradient(115deg,#edf3ff,#fbfdff); border-bottom: 1px solid #e8eef8; }.editor-kicker { color: #7c9bd1; font-size: .7rem; }.editor-heading h2 { font-size: 1.13rem; color: #3a5985; margin: 8px 0; overflow-wrap: anywhere; }.editor-heading p { font-size: .74rem; color: #91a3bd; margin: 0; line-height: 1.8; }.editor-model { align-self: flex-start; padding: 5px 9px; border: 1px solid #d9e4fa; border-radius: 7px; background: white; color: #7d96bf; font-size: .62rem; white-space: nowrap; }.editor-fields { border: 0; min-width: 0; margin: 0; padding: 22px; display: grid; gap: 19px; }.form-grid { display: grid; grid-template-columns: minmax(0,1.3fr) minmax(0,1fr); gap: 16px; }.field { display: grid; gap: 8px; min-width: 0; }.field>label { font-size: .77rem; font-weight: 600; color: #6d85a9; }.field input,.field select,.field textarea { width: 100%; min-width: 0; border: 1px solid #dae5f5; border-radius: 8px; background: #fbfcff; color: #57729a; padding: 10px 12px; font-size: .8rem; }.field textarea { resize: vertical; line-height: 1.8; }.field small,.field-hint { color: #9cabc1; font-size: .63rem; line-height: 1.7; }.configuration-card { display: grid; grid-template-columns: 1fr 150px; gap: 18px; padding: 17px; border: 1px solid #e4ecf8; border-radius: 12px; background: #f9fbff; }.configuration-fields { display: grid; gap: 13px; }.configuration-values { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; }.configuration-card :deep(.circuit-preview) { align-self: center; padding: 6px; }.configuration-card :deep(figcaption) { font-size: .55rem; }.steps-field label { display: flex; justify-content: space-between; }.steps-preview summary { font-size: .74rem; color: #899fc0; cursor: pointer; }.steps-preview[open] summary { margin-bottom: 12px; }.steps-preview .markdown-body { font-size: .84rem; color: #657b9a; }.readonly-note,.editor-notice { font-size: .77rem; padding: 13px 18px; margin: 15px 22px 0; border-radius: 9px; background: #f1f5fb; color: #7890b2; }.editor-notice--success { color: #389d82; background: #eff9f5; }.editor-error { margin: 15px 22px 0; padding: 15px; background: #fff3f3; color: #b96970; font-size: .77rem; border-radius: 9px; line-height: 1.8; }.editor-error ul { padding-left: 19px; margin: 6px 0; }.editor-error p { margin: 8px 0; }.editor-footer { padding: 17px 22px; border-top: 1px solid #e5edf8; display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; background: #fcfdff; }.editor-footer p { font-size: .73rem; color: #7d95b9; margin: 0; }.editor-footer small { display: block; color: #a1afc3; font-size: .63rem; margin-top: 6px; line-height: 1.8; }.editor-footer>div { display: flex; gap: 8px; flex-wrap: wrap; }.editor-footer .button { font-size: .77rem; }
@media(max-width:1100px) { .management-layout { grid-template-columns: 220px minmax(0,1fr); gap: 16px; }.experiment-library { padding: 14px; }.editor-fields { padding: 17px; }.configuration-card { grid-template-columns: 1fr; }.configuration-card :deep(.circuit-preview) { display: none; }.form-grid { grid-template-columns: 1fr; } }
@media(max-width:760px) { .management-layout { grid-template-columns: 1fr; }.experiment-list { grid-template-columns: repeat(2,minmax(0,1fr)); max-height: 310px; }.editor-heading { padding: 18px; }.editor-heading h2 { font-size: 1rem; }.editor-fields { padding: 15px; }.editor-footer { padding: 15px; }.editor-model { font-size: .55rem; }.editor-notice,.readonly-note,.editor-error { margin-left: 15px; margin-right: 15px; } }
@media(max-width:420px) { .item-heading { align-items: flex-start; flex-direction: column; }.item-meta { flex-direction: column; gap: 3px; }.experiment-item { padding: 10px; }.editor-heading { flex-wrap: wrap; }.configuration-values { grid-template-columns: 1fr; }.editor-footer>div { width: 100%; }.editor-footer .button { flex: 1; } }
</style>
